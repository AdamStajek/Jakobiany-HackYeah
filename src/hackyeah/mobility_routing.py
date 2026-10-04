"""Driving routes and timetable-based Kraków transit with pedestrian access legs."""

import json
import os
import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from hackyeah import models as m
from hackyeah.city_routing import facts_for, get_graph, length, plan_city_route, resolve
from hackyeah.mobility_data import (
    download,
    ensure_data,
    parking_points,
    realtime_updates,
    source,
)

WARSAW = ZoneInfo("Europe/Warsaw")
BEDNARSKI = "node/288615790"
KIKA = "node/2255629846"
SYNTHETIC_ROUTE_WARNING = "Przebieg tras Pomnik Wojciecha Bednarskiego → Kinokawiarnia Kika oparto na sieci dróg OSM; dane o niedogodnościach są syntetyczne i służą wyłącznie do demo."


def uncertain(summary):
    return m.Assessment(status="uncertain", summary=summary, reasons=[])


def segment(mode, coordinates, instruction, distance=None, **metadata):
    now = datetime.now(UTC)
    if len(coordinates) == 1:
        coordinates = coordinates * 2
    return m.RouteSegment(
        id=uuid4().hex,
        mode=mode,
        instruction=instruction,
        geometry=m.LineString(type="LineString", coordinates=coordinates),
        distance_m=distance
        if distance is not None
        else sum(
            length(a, b) for a, b in zip(coordinates, coordinates[1:], strict=False)
        ),
        assessment=uncertain("Dostępność tego odcinka nie została potwierdzona."),
        facts=facts_for({}, f"{mode}/{uuid4().hex}", now, now),
        barriers=[],
        rest_points=[],
        **metadata,
    )


def combined_route(segments, mode, duration, parking=None):
    coordinates = []
    for item in segments:
        points = item.geometry.coordinates
        coordinates.extend(
            points[1:] if coordinates and coordinates[-1] == points[0] else points
        )
    assessment = uncertain(
        "Sprawdź dostępność dojść, przystanków i pojazdu."
        if mode == "transit"
        else "Trasa samochodowa; warunki dojazdu wymagają sprawdzenia."
    )
    if any(s.assessment.status == "does_not_meet_requirements" for s in segments):
        assessment = m.Assessment(
            status="does_not_meet_requirements",
            summary="Co najmniej jedno dojście nie spełnia wszystkich potrzeb.",
            reasons=[r for s in segments for r in s.assessment.reasons],
        )
    return m.Route(
        id=uuid4().hex,
        mode=mode,
        distance_m=sum(s.distance_m for s in segments),
        estimated_duration_s=duration,
        assessment=assessment,
        geometry=m.LineString(type="LineString", coordinates=coordinates),
        segments=segments,
        facts=[f for s in segments for f in s.facts],
        computed_at=datetime.now(UTC),
        parking=parking,
    )


def bednarski_kika_demo(request, graph):
    if not (
        isinstance(request.origin, m.PlaceReference)
        and isinstance(request.destination, m.PlaceReference)
        and request.origin.place_id == BEDNARSKI
        and request.destination.place_id == KIKA
    ):
        return None
    now = datetime.now(UTC)
    source = m.Source(
        type="other",
        label="Syntetyczny scenariusz demonstracyjny",
        url=None,
        license=None,
        retrieved_at=now,
    )

    def demo_facts(identifier, *, steps=0, rest_known=True):
        values = {
            "steps_count": steps,
            "steps_present": steps > 0,
            "threshold_height_cm": 0,
            "kerb_height_cm": 0,
            "raised_kerb": False,
            "ramp_available": steps == 0,
            "surface": "paved",
            "smoothness": "good",
            "lighting_available": True,
        }
        facts = []
        for attribute, value in values.items():
            facts.append(
                m.Fact(
                    id=f"synthetic/{identifier}/{attribute}",
                    attribute=attribute,
                    value=value,
                    unit="count"
                    if attribute == "steps_count"
                    else "cm"
                    if attribute.endswith("_cm")
                    else None,
                    status="confirmed",
                    confidence_score=100,
                    confidence_level="certain",
                    confidence_calculated_at=now,
                    confidence_percent=100,
                    observed_at=now,
                    updated_at=now,
                    valid_until=None,
                    sources=[source],
                    unconfirmed_reason=None,
                )
            )
        if not rest_known:
            facts.append(
                m.Fact(
                    id=f"synthetic/{identifier}/rest_area_available",
                    attribute="rest_area_available",
                    value=None,
                    unit=None,
                    status="unconfirmed",
                    confidence_percent=None,
                    observed_at=None,
                    updated_at=now,
                    valid_until=None,
                    sources=[],
                    unconfirmed_reason="missing",
                )
            )
        return facts

    empty_constraints = m.Constraints.model_validate(
        {field: None for field in m.Constraints.model_fields}
    )
    fastest = plan_city_route(
        request.model_copy(update={"constraints": empty_constraints}),
        graph,
        fastest=True,
    )
    step_free = empty_constraints.model_copy(
        update={"max_steps": 0, "require_step_free_access": True}
    )
    constrained = plan_city_route(
        request.model_copy(update={"constraints": step_free}), graph
    )
    if not fastest.routes or not constrained.routes:
        return None

    short = fastest.routes[0]
    stair_segments = [
        index
        for index, segment in enumerate(short.segments)
        if "schody" in segment.instruction.casefold()
    ]
    if not stair_segments:
        return None
    stair_index = max(
        stair_segments, key=lambda index: short.segments[index].distance_m
    )
    for index, segment in enumerate(short.segments):
        steps = 24 if index == stair_index else 0
        segment.id = f"bednarski-kika-stairs-{index}"
        segment.facts = demo_facts(segment.id, steps=steps)
        segment.assessment = m.Assessment(
            status="does_not_meet_requirements" if steps else "meets_requirements",
            summary="Syntetyczne dane: schody, 24 stopnie."
            if steps
            else "Brak zarejestrowanych niedogodności.",
            reasons=[
                m.AssessmentReason(
                    code="SYNTHETIC_STAIRS",
                    message="Schody: 24 stopnie.",
                    fact_ids=[f"synthetic/{segment.id}/steps_count"],
                )
            ]
            if steps
            else [],
        )
    short.id = "demo-bednarski-kika-stairs"
    short.variant = "fastest"
    short.facts = [fact for segment in short.segments for fact in segment.facts]
    short.assessment = m.Assessment(
        status="does_not_meet_requirements",
        summary="Krótszy wariant prowadzi prawdziwymi drogami i obejmuje schody.",
        reasons=[
            reason
            for segment in short.segments
            for reason in segment.assessment.reasons
        ],
    )

    long = constrained.routes[0]
    gap_index = len(long.segments) // 2
    for index, segment in enumerate(long.segments):
        rest_known = index != gap_index
        segment.id = f"bednarski-kika-detour-{index}"
        segment.facts = demo_facts(segment.id, rest_known=rest_known)
        segment.assessment = m.Assessment(
            status="meets_requirements" if rest_known else "uncertain",
            summary="Brak zarejestrowanych niedogodności."
            if rest_known
            else "Nie potwierdzono obecności miejsca odpoczynku.",
            reasons=[]
            if rest_known
            else [
                m.AssessmentReason(
                    code="SYNTHETIC_MISSING_REST_AREA",
                    message="Niepewność: brak potwierdzenia miejsca odpoczynku.",
                    fact_ids=[f"synthetic/{segment.id}/rest_area_available"],
                )
            ],
        )
    long.id = "demo-bednarski-kika-detour"
    long.variant = "constrained"
    long.facts = [fact for segment in long.segments for fact in segment.facts]
    long.assessment = m.Assessment(
        status="uncertain",
        summary="Dłuższy wariant omija schody; nie potwierdzono miejsca odpoczynku.",
        reasons=[
            reason for segment in long.segments for reason in segment.assessment.reasons
        ],
    )

    return m.RoutePlanResponse(
        routes=[
            short,
            long,
        ],
        warnings=[SYNTHETIC_ROUTE_WARNING],
        attribution=[*fastest.attribution, source],
    )


def endpoints(request):
    return resolve(request.origin), resolve(request.destination)


def empty(message, warnings=None, attribution=None):
    return m.RoutePlanResponse(
        routes=[], warnings=[*(warnings or []), message], attribution=attribution or []
    )


def driving(start, finish):
    base = os.getenv("OSRM_URL", "https://router.project-osrm.org").rstrip("/")
    points = f"{start[0]},{start[1]};{finish[0]},{finish[1]}"
    try:
        body = json.loads(
            download(
                f"{base}/route/v1/driving/{points}?overview=full&geometries=geojson&steps=true&radiuses=100;100"
            )
        )
    except HTTPError as exc:
        if exc.code == 400:
            return None
        raise
    if body.get("code") != "Ok" or not body.get("routes"):
        return None
    return body


def plan_car(request):
    start, finish = endpoints(request)
    if start is None or finish is None:
        return empty("Nie znaleziono wskazanego miejsca.")
    now = datetime.now(UTC)
    attribution = [
        m.Source(
            type="osm",
            label="OSRM / © OpenStreetMap contributors",
            url="https://www.openstreetmap.org/copyright",
            license="ODbL",
            retrieved_at=now,
        )
    ]
    warnings = [
        "Czas jazdy nie uwzględnia bieżących korków. Sprawdź oznakowanie i ograniczenia wjazdu."
    ]
    parking = None
    candidates = [None]
    if request.accessible_parking:
        try:
            items, parking_warnings, parking_source = parking_points()
        except (OSError, ValueError, KeyError):
            return empty(
                "Mapa miejsc parkingowych OZN jest chwilowo niedostępna. Spróbuj ponownie."
            )
        warnings.extend(parking_warnings)
        attribution.append(parking_source)
        candidates = sorted(
            (
                p
                for p in items
                if length(finish, (p.location.lon, p.location.lat)) <= 1000
            ),
            key=lambda p: length(finish, (p.location.lon, p.location.lat)),
        )[:8]
        if not candidates:
            return empty(
                "Brak miejsc parkingowych OZN na miejskiej mapie w promieniu 1 km od celu.",
                warnings,
                attribution,
            )
    for candidate in candidates:
        target = (
            (candidate.location.lon, candidate.location.lat) if candidate else finish
        )
        try:
            result = driving(start, target)
        except (OSError, ValueError, KeyError):
            return empty(
                "Usługa wyznaczania trasy samochodowej jest chwilowo niedostępna.",
                warnings,
                attribution,
            )
        if result:
            parking = candidate
            break
    else:
        return empty(
            "Nie znaleziono dojazdu drogowego do wskazanego celu lub parkingu.",
            warnings,
            attribution,
        )
    route = result["routes"][0]
    modifiers = {
        "left": "w lewo",
        "right": "w prawo",
        "slight left": "lekko w lewo",
        "slight right": "lekko w prawo",
        "sharp left": "ostro w lewo",
        "sharp right": "ostro w prawo",
        "uturn": "zawróć",
        "straight": "prosto",
    }
    segments = []
    for leg in route["legs"]:
        for step in leg["steps"]:
            maneuver = step["maneuver"]
            kind = maneuver["type"]
            instruction = "Jedź"
            if kind == "arrive":
                instruction = (
                    f"Dojeżdżasz do parkingu: {parking.name}."
                    if parking
                    else "Dojeżdżasz do celu."
                )
            elif kind in {"roundabout", "rotary"}:
                instruction = f"Na rondzie wybierz zjazd {maneuver.get('exit', '')}."
            else:
                if kind == "depart":
                    instruction = "Rozpocznij jazdę"
                elif kind in {"turn", "end of road", "fork"}:
                    instruction = "Skręć"
                instruction += " " + modifiers.get(maneuver.get("modifier"), "prosto")
                if step.get("name"):
                    instruction += f" — {step['name']}"
            segments.append(
                segment(
                    "car",
                    step["geometry"]["coordinates"],
                    instruction,
                    step["distance"],
                )
            )
    if not segments:
        segments = [
            segment(
                "car",
                route["geometry"]["coordinates"],
                "Jedź do celu.",
                route["distance"],
            )
        ]
    if parking:
        gap = round(length(finish, (parking.location.lon, parking.location.lat)))
        warnings.append(
            f"Wybrany parking: {parking.name}, około {gap} m w linii prostej od celu. Trasa kończy się przy parkingu. Brak danych o zajętości miejsc."
        )
    if any(w.get("distance", 0) > 15 for w in result.get("waypoints", [])):
        warnings.append(
            "Początek lub koniec dojazdu przesunięto do najbliższej dostępnej drogi."
        )
    return m.RoutePlanResponse(
        routes=[combined_route(segments, "car", route["duration"], parking)],
        warnings=warnings,
        attribution=attribution,
    )


def active_services(db, day):
    date = day.strftime("%Y%m%d")
    active = {
        service
        for service, weekdays in db.execute(
            "SELECT service,weekdays FROM calendar WHERE start<=? AND end>=?",
            (date, date),
        )
        if weekdays[day.weekday()] == "1"
    }
    for service, kind in db.execute(
        "SELECT service,type FROM exceptions WHERE date=?", (date,)
    ):
        if kind == 1:
            active.add(service)
        elif kind == 2:
            active.discard(service)
    return active


@dataclass(frozen=True)
class Connection:
    trip: str
    sequence: int
    a: str
    b: str
    departure: float
    arrival: float
    pickup: int
    dropoff: int
    line: str
    headsign: str
    shape: str
    wheelchair: int
    delay: int | None
    service_day: str
    target_sequence: int = 0
    start_distance: float | None = None
    end_distance: float | None = None


def trip_connections(rows, midnight, update, day):
    """Propagate RT delays, including early running; NO_DATA clears propagation."""
    if update and update.trip.start_date and update.trip.start_date != day:
        update = None
    if update and update.trip.schedule_relationship in (3, 7):
        return []  # canceled or deleted
    by_sequence = (
        {
            s.stop_sequence: s
            for s in update.stop_time_update
            if s.HasField("stop_sequence")
        }
        if update
        else {}
    )
    by_stop = (
        {s.stop_id: s for s in update.stop_time_update if s.stop_id} if update else {}
    )
    delay = update.delay if update and update.HasField("delay") else None
    events = {}
    skipped = set()
    # Connections overlap at stops; process each stop once in sequence order.
    stops = [(r["sequence"], r["a"], r["departure"], "departure") for r in rows]
    stops += [(r["target_sequence"], r["b"], r["arrival"], "arrival") for r in rows]
    for sequence, stop, scheduled, kind in sorted(
        stops, key=lambda s: (s[0], s[3] == "departure")
    ):
        s = by_sequence.get(sequence) or by_stop.get(stop.split(":", 1)[1])
        if s:
            if s.schedule_relationship == 1:
                skipped.add(sequence)
            elif s.schedule_relationship == 2:
                delay = None
            event = getattr(s, kind)
            if s.schedule_relationship != 2:
                if (
                    kind == "departure"
                    and not (event.HasField("time") or event.HasField("delay"))
                    and s.arrival.HasField("delay")
                ):
                    delay = s.arrival.delay
                if event.HasField("time"):
                    delay = int(event.time - (midnight + scheduled))
                elif event.HasField("delay"):
                    delay = event.delay
        events[stop, kind, sequence] = (midnight + scheduled + (delay or 0), delay)
    connections = []
    for r in rows:
        dep, dep_delay = events[r["a"], "departure", r["sequence"]]
        arr, _ = events[r["b"], "arrival", r["target_sequence"]]
        if arr < dep:
            continue
        connections.append(
            Connection(
                trip=r["trip"],
                sequence=r["sequence"],
                target_sequence=r["target_sequence"],
                a=r["a"],
                b=r["b"],
                departure=dep,
                arrival=arr,
                pickup=1 if r["sequence"] in skipped else r["pickup"],
                dropoff=1 if r["target_sequence"] in skipped else r["dropoff"],
                line=r["line"],
                headsign=r["headsign"],
                shape=r["shape"],
                wheelchair=r["wheelchair"],
                delay=dep_delay,
                service_day=day,
                start_distance=r["start_distance"],
                end_distance=r["end_distance"],
            )
        )
    return connections


def connections_for(db, departure, updates):
    now = departure.timestamp()
    connections = []
    day = departure.astimezone(WARSAW).date()
    for offset in (-1, 0, 1):
        service_date = day + timedelta(days=offset)
        # GTFS defines service times from local noon minus 12 elapsed hours (DST-safe).
        noon = datetime.combine(
            service_date, datetime.min.time().replace(hour=12), WARSAW
        )
        midnight = noon.timestamp() - 12 * 3600
        active = active_services(db, service_date)
        if not active:
            continue
        placeholders = ",".join("?" for _ in active)
        query = f"""SELECT c.*,t.headsign,t.shape,t.wheelchair,t.service,r.line
                   FROM connections c JOIN trips t ON c.trip=t.id JOIN routes r ON t.route=r.id
                   WHERE t.service IN ({placeholders}) AND c.trip IN (SELECT trip FROM connections WHERE departure BETWEEN ? AND ?) ORDER BY c.trip,c.sequence"""
        trips = defaultdict(list)
        for row in db.execute(
            query,
            (*sorted(active), now - midnight - 3600, now - midnight + 6 * 3600 + 3600),
        ):
            if row["service"] in active:
                trips[row["trip"]].append(row)
        for trip, rows in trips.items():
            connections.extend(
                trip_connections(
                    rows, midnight, updates.get(trip), service_date.strftime("%Y%m%d")
                )
            )
    return sorted(
        (c for c in connections if now <= c.departure <= now + 6 * 3600),
        key=lambda c: c.departure,
    )


@dataclass(frozen=True)
class Journey:
    time: float
    previous: "Journey | None"
    leg: object


def transfer_pairs(stops, db):
    grid = defaultdict(list)
    for stop in stops.values():
        key = (int(stop["lon"] * 714), int(stop["lat"] * 1112))
        grid[key].append(stop)
    pairs = defaultdict(dict)
    # ponytail: only nearby platforms (180 m); wider transfers need explicit GTFS links.
    for a in stops.values():
        x, y = int(a["lon"] * 714), int(a["lat"] * 1112)
        name = re.sub(r"\s+\d{2}$", "", a["name"])
        for gx in range(x - 2, x + 3):
            for gy in range(y - 2, y + 3):
                for b in grid.get((gx, gy), []):
                    if a["id"] == b["id"]:
                        continue
                    meters = length((a["lon"], a["lat"]), (b["lon"], b["lat"]))
                    same_station = (
                        a["parent"] and a["parent"] == b["parent"]
                    ) or name == re.sub(r"\s+\d{2}$", "", b["name"])
                    if meters <= 40 or (same_station and meters <= 180):
                        pairs[a["id"]][b["id"]] = max(90, meters / 0.8)
    for a, b, kind, minimum in db.execute("SELECT * FROM transfers"):
        if kind == 3:
            pairs[a].pop(b, None)
        elif a in stops and b in stops and a != b:
            pairs[a][b] = max(
                90,
                minimum,
                length(
                    (stops[a]["lon"], stops[a]["lat"]),
                    (stops[b]["lon"], stops[b]["lat"]),
                )
                / 0.8,
            )
    return pairs


def scan_connections(connections, initial, transfers, stops, step_free=False):
    """Earliest-arrival connection scan; persistent paths survive later label updates."""
    reached = dict(initial)
    aboard = {}
    for c in connections:
        if step_free and c.wheelchair == 2:
            continue
        trip = (c.trip, c.service_day)
        onboard = aboard.get(trip)
        if onboard and (
            not isinstance(onboard.leg, Connection)
            or onboard.leg.b != c.a
            or onboard.time > c.departure
        ):
            onboard = None
        board = reached.get(c.a)
        may_board = (
            board
            and c.pickup == 0
            and (not step_free or stops[c.a]["wheelchair"] != 2)
            and board.time + 30 <= c.departure
        )
        if onboard is None and not may_board:
            continue
        previous = onboard if onboard else board
        if previous is None:
            continue
        journey = Journey(c.arrival, previous, c)
        aboard[trip] = journey
        if c.dropoff != 0 or (step_free and stops[c.b]["wheelchair"] == 2):
            continue
        if c.b not in reached or c.arrival < reached[c.b].time:
            reached[c.b] = journey
        for b, duration in transfers.get(c.b, {}).items():
            if step_free and stops[b]["wheelchair"] == 2:
                continue
            at = c.arrival + duration
            if b not in reached or at < reached[b].time:
                reached[b] = Journey(at, journey, (c.b, b, duration))
    return reached


def shape_geometry(db, connections, stops):
    first, last = connections[0], connections[-1]
    start = (stops[first.a]["lon"], stops[first.a]["lat"])
    finish = (stops[last.b]["lon"], stops[last.b]["lat"])
    rows = db.execute(
        "SELECT lon,lat,distance FROM shapes WHERE id=? ORDER BY sequence",
        (first.shape,),
    ).fetchall()
    points = [(r[0], r[1]) for r in rows]
    if points:
        if (
            first.start_distance is not None
            and last.end_distance is not None
            and all(r[2] is not None for r in rows)
        ):
            middle = [
                (r[0], r[1])
                for r in rows
                if first.start_distance <= r[2] <= last.end_distance
            ]
        else:
            a = min(range(len(points)), key=lambda i: length(start, points[i]))
            b = min(range(a, len(points)), key=lambda i: length(finish, points[i]))
            middle = points[a : b + 1]
        return [start, *middle, finish], False
    return [start, *[(stops[c.b]["lon"], stops[c.b]["lat"]) for c in connections]], True


def walk_leg(request, graph, start, finish):
    return plan_city_route(
        request.model_copy(
            update={
                "origin": m.Coordinates(lon=start[0], lat=start[1]),
                "destination": m.Coordinates(lon=finish[0], lat=finish[1]),
                "mode": "walk",
                "accessible_parking": False,
            }
        ),
        graph,
    )


def nearby_walks(request, graph, stops, point, arriving):
    candidates = sorted(
        (
            s
            for s in stops.values()
            if length(point, (s["lon"], s["lat"])) <= 900
            and not (
                request.constraints
                and request.constraints.require_step_free_access
                and s["wheelchair"] == 2
            )
        ),
        key=lambda s: length(point, (s["lon"], s["lat"])),
    )[:6]
    result = {}
    for stop in candidates:
        location = (stop["lon"], stop["lat"])
        leg = walk_leg(
            request,
            graph,
            location if arriving else point,
            point if arriving else location,
        )
        if leg.routes:
            result[stop["id"]] = leg
    return result


def plan_transit(request):
    start, finish = endpoints(request)
    if start is None or finish is None:
        return empty("Nie znaleziono wskazanego miejsca.")
    try:
        path, warnings = ensure_data("schedule")
    except (OSError, ValueError):
        return empty(
            "Nie udało się pobrać rozkładu ZTP. Spróbuj ponownie lub wybierz trasę pieszą."
        )
    departure = request.departure_at or datetime.now(UTC)
    if abs((departure - datetime.now(UTC)).total_seconds()) <= 300:
        updates, rt_warnings = realtime_updates()
        warnings.extend(rt_warnings)
    else:
        updates = {}
        warnings.append(
            "Wybrano inny czas wyjazdu; trasa korzysta z rozkładu, bez bieżących opóźnień."
        )
    graph = get_graph()
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        retrieved = datetime.fromisoformat(
            db.execute(
                "SELECT value FROM metadata WHERE key='retrieved_at'"
            ).fetchone()[0]
        )
        attribution = [source("schedule", retrieved)]
        stops = {s["id"]: dict(s) for s in db.execute("SELECT * FROM stops")}
        access = nearby_walks(request, graph, stops, start, False)
        egress = nearby_walks(request, graph, stops, finish, True)
        if not access or not egress:
            return empty(
                "Brak dostępnego dojścia do przystanku w promieniu 900 m od początku lub celu.",
                warnings,
                attribution,
            )
        initial = {
            stop: Journey(
                departure.timestamp() + (leg.routes[0].estimated_duration_s or 0),
                None,
                leg,
            )
            for stop, leg in access.items()
        }
        connections = connections_for(db, departure, updates)
        if not connections:
            return empty(
                "Brak kursów w rozkładzie na wybrany dzień i najbliższe 6 godzin.",
                warnings,
                attribution,
            )
        transfers = transfer_pairs(stops, db)
        verified_transfers = {}
        # Verify only transfers used by a candidate; reroute if pedestrian access is slower or blocked.
        for _attempt in range(12):
            reached = scan_connections(
                connections,
                initial,
                transfers,
                stops,
                bool(
                    request.constraints and request.constraints.require_step_free_access
                ),
            )
            choices = [
                (reached[s].time + (leg.routes[0].estimated_duration_s or 0), s)
                for s, leg in egress.items()
                if s in reached and reached[s].previous is not None
            ]
            if not choices:
                return empty(
                    "Nie znaleziono połączenia komunikacją w najbliższych 6 godzinach. Zmień czas wyjazdu lub wybierz trasę pieszą.",
                    warnings,
                    attribution,
                )
            arrival, stop = min(choices)
            journey = reached[stop]
            legs = []
            while journey:
                legs.append(journey.leg)
                journey = journey.previous
            legs.reverse()
            changed = False
            for leg in legs:
                if not isinstance(leg, tuple):
                    continue
                a, b, reserved = leg
                if (a, b) not in verified_transfers:
                    verified_transfers[a, b] = walk_leg(
                        request,
                        graph,
                        (stops[a]["lon"], stops[a]["lat"]),
                        (stops[b]["lon"], stops[b]["lat"]),
                    )
                foot = verified_transfers[a, b]
                if not foot.routes:
                    transfers[a].pop(b, None)
                    changed = True
                elif (foot.routes[0].estimated_duration_s or 0) + 30 > reserved:
                    transfers[a][b] = (foot.routes[0].estimated_duration_s or 0) + 30
                    changed = True
            if not changed:
                break
        else:
            return empty(
                "Nie udało się potwierdzić dojść przy przesiadkach. Zmień czas wyjazdu lub wybierz trasę pieszą.",
                warnings,
                attribution,
            )
        segments = []
        transit_group = []

        def flush_transit():
            if not transit_group:
                return
            first, last = transit_group[0], transit_group[-1]
            geometry, approximate = shape_geometry(db, transit_group, stops)
            if approximate:
                warnings.append(
                    "Brak geometrii przejazdu w rozkładzie; odcinek komunikacji pokazano przez przystanki."
                )
            a, b = stops[first.a]["name"], stops[last.b]["name"]
            segments.append(
                segment(
                    "transit",
                    geometry,
                    f"Linia {first.line} → {first.headsign or b}. Wsiądź: {a}; wysiądź: {b}.",
                    line=first.line,
                    from_stop=a,
                    to_stop=b,
                    departure_at=datetime.fromtimestamp(first.departure, UTC),
                    arrival_at=datetime.fromtimestamp(last.arrival, UTC),
                    delay_s=first.delay,
                )
            )
            if first.delay is None:
                warnings.append(
                    f"Linia {first.line}: brak aktualnej prognozy tego kursu; podano czas rozkładowy."
                )
            transit_group.clear()

        for leg in legs:
            if isinstance(leg, Connection):
                if transit_group and (leg.trip, leg.service_day) != (
                    transit_group[-1].trip,
                    transit_group[-1].service_day,
                ):
                    flush_transit()
                transit_group.append(leg)
                continue
            flush_transit()
            if isinstance(leg, m.RoutePlanResponse):
                segments.extend(
                    leg.routes[0].segments
                    or [
                        segment(
                            "walk",
                            leg.routes[0].geometry.coordinates,
                            "Podejdź do przystanku.",
                            leg.routes[0].distance_m,
                        )
                    ]
                )
                warnings.extend(leg.warnings)
                attribution.extend(leg.attribution)
            else:
                a, b, reserved = leg
                foot = verified_transfers[a, b]
                segments.extend(foot.routes[0].segments)
                warnings.extend(foot.warnings)
                attribution.extend(foot.attribution)
        flush_transit()
        final = egress[stop]
        segments.extend(
            final.routes[0].segments
            or [
                segment(
                    "walk",
                    final.routes[0].geometry.coordinates,
                    "Podejdź do celu.",
                    final.routes[0].distance_m,
                )
            ]
        )
        warnings.extend(final.warnings)
        attribution.extend(final.attribution)
        warnings.append(
            "Dostępność przystanków i pojazdów zależy od danych rozkładowych; brak informacji nie potwierdza dostępu bez stopni."
        )
        return m.RoutePlanResponse(
            routes=[
                combined_route(segments, "transit", arrival - departure.timestamp())
            ],
            warnings=list(dict.fromkeys(warnings)),
            attribution=list({s.url: s for s in attribution}.values()),
        )


def plan_mobility_route(request):
    if request.mode == "walk":
        graph = get_graph()
        demo = bednarski_kika_demo(request, graph)
        if demo is not None:
            return demo
        response = plan_city_route(request, graph)
        if not response.routes:
            return response
        fastest = plan_city_route(request, graph, fastest=True)
        for route in response.routes:
            route.variant = "constrained"
        for route in fastest.routes:
            route.variant = "fastest"
            known = set()
            for segment in route.segments:
                for fact in segment.facts:
                    value = fact.value
                    description = None
                    if (
                        fact.attribute == "steps_count"
                        and isinstance(value, (int, float))
                        and value > 0
                    ):
                        description = f"Schody: {value:g} stopni."
                    elif fact.attribute == "steps_present" and value is True:
                        description = "Na trasie występują schody."
                    elif fact.attribute == "surface" and value in {
                        "gravel",
                        "cobblestone",
                        "ground",
                        "other",
                    }:
                        surface = {
                            "gravel": "żwir",
                            "cobblestone": "bruk",
                            "ground": "grunt",
                            "other": "inna",
                        }[value]
                        description = (
                            f"Nierówna lub nieutwardzona nawierzchnia: {surface}."
                        )
                    elif (
                        fact.attribute == "slope_percent"
                        and isinstance(value, (int, float))
                        and value > 0
                    ):
                        description = f"Nachylenie odcinka: {value:g}%."
                    elif fact.attribute == "lighting_available" and value is False:
                        description = "Odcinek bez oświetlenia."
                    if description and description not in known:
                        known.add(description)
                        route.assessment.reasons.append(
                            m.AssessmentReason(
                                code="OSM_INCONVENIENCE",
                                message=description + " Dane OSM wymagają weryfikacji.",
                                fact_ids=[fact.id],
                            )
                        )
            route.assessment.summary = "Najszybsza trasa piesza; sprawdź niedogodności względem swoich potrzeb."
        response.routes.extend(fastest.routes)
        response.warnings.extend(
            f"Najszybsza trasa: {warning}"
            for warning in fastest.warnings
            if warning not in response.warnings
        )
        return response
    try:
        return plan_car(request) if request.mode == "car" else plan_transit(request)
    except HTTPException:
        raise
    except (OSError, sqlite3.Error, ValueError, KeyError):
        return empty(
            "Dane wybranego środka transportu są chwilowo niedostępne. Spróbuj ponownie."
        )
