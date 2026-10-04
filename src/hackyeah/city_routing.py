"""Profile-aware A* on the imported city pedestrian network, with explicit OSM uncertainty."""

import json
import math
import os
import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from heapq import heappop, heappush
from itertools import count
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from hackyeah import models as m
from hackyeah.database import database_path
from hackyeah.route_data import SMOOTHNESS, SURFACES, extract_facts, height_cm

# Metric projection is local to Kraków; no topology is inferred from line crossings.
X_SCALE = 111_195 * math.cos(math.radians(50.06))
Y_SCALE = 111_195
ATTRIBUTE_NAMES = {
    "steps_count": "liczba stopni",
    "steps_present": "schody",
    "surface": "nawierzchnia",
    "smoothness": "nierówności nawierzchni",
    "lighting_available": "oświetlenie",
    "kerb_height_cm": "wysokość krawężnika",
    "threshold_height_cm": "wysokość progu",
    "entrance_width_cm": "szerokość przejścia",
    "slope_percent": "nachylenie",
}
CELL = 100
SNAP_LIMIT = 100


def xy(point):
    return point[0] * X_SCALE, point[1] * Y_SCALE


def length(a, b):
    x1, y1 = xy(a)
    x2, y2 = xy(b)
    return math.hypot(x2 - x1, y2 - y1)


def cell(point):
    x, y = xy(point)
    return math.floor(x / CELL), math.floor(y / CELL)


def values(tags) -> dict[m.Attribute, Any]:
    result: dict[m.Attribute, Any] = {
        "steps_count": int(tags["step_count"])
        if tags.get("step_count", "").isdigit()
        else None,
        "steps_present": True
        if tags.get("highway") == "steps" or tags.get("barrier") == "step"
        else None,
        "kerb_height_cm": height_cm(
            tags.get("kerb:height")
            or (tags.get("height") if tags.get("barrier") == "kerb" else None)
        ),
        "raised_kerb": True
        if tags.get("kerb") == "raised"
        else False
        if tags.get("kerb") in {"flush", "no"}
        else None,
        "threshold_height_cm": height_cm(
            tags.get("entrance:threshold:height") or tags.get("door:threshold:height")
        ),
        "entrance_width_cm": height_cm(
            tags.get("entrance:width") or tags.get("door:width") or tags.get("width")
        ),
        "lighting_available": tags.get("lit") == "yes"
        if tags.get("lit") in {"yes", "no"}
        else None,
        "surface": SURFACES.get(tags["surface"], "other")
        if tags.get("surface")
        else None,
        "smoothness": tags.get("smoothness")
        if tags.get("smoothness") in SMOOTHNESS
        else None,
        "slope_percent": None,
    }
    raw = tags.get("incline", "").strip()
    try:
        if raw.endswith("%"):
            result["slope_percent"] = abs(float(raw[:-1]))
        elif raw.endswith("°"):
            result["slope_percent"] = abs(math.tan(math.radians(float(raw[:-1])))) * 100
        if result["slope_percent"] is not None and not math.isfinite(
            result["slope_percent"]
        ):
            result["slope_percent"] = None
    except ValueError:
        pass
    if result["steps_count"] is not None:
        result["steps_present"] = result["steps_present"] or result["steps_count"] > 0
    return result


@dataclass(slots=True)
class Way:
    id: int
    tags: dict[str, str]
    updated: datetime
    values: dict[m.Attribute, Any]


@dataclass(slots=True)
class Edge:
    a: int
    b: int
    way: int | None
    distance: float
    steps: int = 0


class CityGraph:
    def __init__(self, path: Path):
        with closing(
            sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        ) as db:
            self.metadata = {
                key: json.loads(value)
                for key, value in db.execute("SELECT key,value FROM metadata")
            }
            self.nodes = {}
            self.node_tags = {}
            for identifier, lon, lat, tags, updated in db.execute(
                "SELECT * FROM nodes"
            ):
                self.nodes[identifier] = (lon, lat)
                if tags != "{}":
                    self.node_tags[identifier] = (
                        json.loads(tags),
                        datetime.fromisoformat(updated),
                    )
            self.ways = {
                identifier: Way(
                    identifier,
                    json.loads(tags),
                    datetime.fromisoformat(updated),
                    values(json.loads(tags)),
                )
                for identifier, tags, updated in db.execute("SELECT * FROM ways")
            }
            self.edges = []
            self.adjacency = defaultdict(list)
            self.grid = defaultdict(list)
            links = list(
                db.execute("SELECT a,b,way,position FROM links ORDER BY way,position")
            )
            totals = defaultdict(float)
            for a, b, way, _ in links:
                totals[way] += length(self.nodes[a], self.nodes[b])
            walked = defaultdict(float)
            for a, b, way_id, _ in links:
                way = self.ways[way_id]
                meters = length(self.nodes[a], self.nodes[b])
                if meters < 0.001:
                    continue
                steps_total = way.values["steps_count"] or 0
                steps = round(
                    steps_total * (walked[way_id] + meters) / totals[way_id]
                ) - round(steps_total * walked[way_id] / totals[way_id])
                walked[way_id] += meters
                direction = way.tags.get("oneway:foot")
                if direction != "-1":
                    self.add_edge(Edge(a, b, way_id, meters, steps))
                if direction not in {"yes", "1", "true"}:
                    self.add_edge(Edge(b, a, way_id, meters, steps))
            self.rests = {}
            self.toilets = set()
            node_grid = defaultdict(list)
            for identifier, point in self.nodes.items():
                node_grid[cell(point)].append(identifier)
            for identifier, lon, lat, encoded, _updated in db.execute(
                "SELECT * FROM amenities"
            ):
                tags = json.loads(encoded)
                if tags.get("access") in {"private", "no"}:
                    continue
                point = (lon, lat)
                gx, gy = cell(point)
                candidates = [
                    node
                    for x in range(gx - 1, gx + 2)
                    for y in range(gy - 1, gy + 2)
                    for node in node_grid[(x, y)]
                ]
                node = min(
                    candidates, key=lambda n: length(point, self.nodes[n]), default=None
                )
                if node is None or length(point, self.nodes[node]) > 25:
                    continue
                if (
                    tags.get("amenity") == "toilets"
                    and tags.get("toilets:wheelchair") == "yes"
                ):
                    self.toilets.add(node)
                if (
                    tags.get("amenity") == "bench"
                    or tags.get("leisure") == "picnic_table"
                ):
                    self.rests[node] = m.RestPoint(
                        id=f"osm/node/{identifier}",
                        location=m.Coordinates(lon=lon, lat=lat),
                        description="Ławka lub miejsce odpoczynku w pobliżu wg OSM; dojście wymaga sprawdzenia.",
                        fact_ids=[],
                    )

    def add_edge(self, edge):
        index = len(self.edges)
        self.edges.append(edge)
        self.adjacency[edge.a].append(index)
        ax, ay = cell(self.nodes[edge.a])
        bx, by = cell(self.nodes[edge.b])
        for x in range(min(ax, bx), max(ax, bx) + 1):
            for y in range(min(ay, by), max(ay, by) + 1):
                self.grid[(x, y)].append(index)

    def snap(self, point) -> tuple[float, Edge, float, tuple[float, float]] | None:
        gx, gy = cell(point)
        indexes = {
            i
            for x in range(gx - 1, gx + 2)
            for y in range(gy - 1, gy + 2)
            for i in self.grid.get((x, y), [])
        }
        px, py = xy(point)
        nearest: tuple[float, Edge, float, tuple[float, float]] | None = None
        for index in indexes:
            edge = self.edges[index]
            a, b = self.nodes[edge.a], self.nodes[edge.b]
            ax, ay = xy(a)
            bx, by = xy(b)
            ratio = max(
                0,
                min(
                    1,
                    ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / edge.distance**2,
                ),
            )
            projected = (a[0] + ratio * (b[0] - a[0]), a[1] + ratio * (b[1] - a[1]))
            gap = length(point, projected)
            if gap <= SNAP_LIMIT and (nearest is None or gap < nearest[0]):
                nearest = (gap, edge, ratio, projected)
        return nearest


def graph_path():
    return Path(
        os.getenv(
            "ROUTE_GRAPH_PATH",
            Path(__file__).resolve().parents[2] / "data/routes/city.sqlite3",
        )
    )


@lru_cache(maxsize=1)
def load_graph(path: str, modified: int):
    return CityGraph(Path(path))


_graph_lock = Lock()


def get_graph():
    path = graph_path()
    if not path.is_file():
        raise HTTPException(503, "ROUTING_DATA_UNAVAILABLE")
    with _graph_lock:
        return load_graph(str(path.resolve()), path.stat().st_mtime_ns)


def resolve(point):
    if isinstance(point, m.Coordinates):
        return point.lon, point.lat
    # Legacy landmarks now resolve to real coordinates in the city graph.
    landmarks = {
        "rynek": (19.9373, 50.0617),
        "planty": (19.9325, 50.0605),
        "wawel": (19.9354, 50.0543),
    }
    if point.place_id in landmarks:
        return landmarks[point.place_id]
    from hackyeah.places import catalogue_table

    with closing(
        sqlite3.connect(database_path().as_uri() + "?mode=ro", uri=True)
    ) as db:
        row = db.execute(
            f"SELECT lon,lat FROM {catalogue_table(db)} WHERE id=?", (point.place_id,)
        ).fetchone()
    return tuple(row) if row else None


def requirement_checks(constraints):
    checks = []
    for field, attribute, minimum in (
        ("max_threshold_cm", "threshold_height_cm", False),
        ("max_kerb_height_cm", "kerb_height_cm", False),
        ("max_slope_percent", "slope_percent", False),
        ("min_entrance_width_cm", "entrance_width_cm", True),
    ):
        limit = getattr(constraints, field)
        if limit is not None:
            checks.append(
                (
                    attribute,
                    lambda v, limit=limit, minimum=minimum: (
                        v >= limit if minimum else v <= limit
                    ),
                )
            )
    for allowed, attribute in (
        (constraints.allowed_surfaces, "surface"),
        (constraints.allowed_smoothness, "smoothness"),
    ):
        if allowed is not None:
            checks.append((attribute, lambda v, allowed=allowed: v in allowed))
    if constraints.require_lighting:
        checks.append(("lighting_available", lambda v: v is True))
    return checks


def walking_time(edge, graph):
    data = graph.ways[edge.way].values if edge.way is not None else {}
    factor = {"gravel": 1.25, "cobblestone": 1.3, "ground": 1.4}.get(
        data.get("surface") or "", 1
    )
    return (
        edge.distance / 1.2 * factor * (1 + (data.get("slope_percent") or 0) * 0.06)
        + edge.steps * 1.5
    )


def edge_cost(edge, graph, constraints, checks, fastest=False):
    if edge.way is None:
        return edge.distance / 1.2 * (1 if fastest else 3), 0
    way = graph.ways[edge.way]
    tags = way.tags
    data = way.values
    step_free = constraints.require_step_free_access or constraints.max_steps == 0
    if data["smoothness"] == "impassable" or (
        step_free and (data["steps_present"] or tags.get("wheelchair") == "no")
    ):
        return None
    if (
        step_free
        and constraints.max_slope_percent is not None
        and data["slope_percent"] is not None
        and data["slope_percent"] > constraints.max_slope_percent
    ):
        return None
    multiplier = {"gravel": 1.25, "cobblestone": 1.3, "ground": 1.4, "other": 1.4}.get(
        data["surface"], 1
    )
    multiplier *= {
        "bad": 1.35,
        "very_bad": 1.6,
        "horrible": 2,
        "very_horrible": 2.5,
    }.get(data["smoothness"], 1)
    if data["slope_percent"] is not None:
        multiplier *= 1 + min(100, data["slope_percent"]) * 0.06
    if tags.get("highway") in {
        "primary",
        "primary_link",
        "secondary",
        "secondary_link",
        "tertiary",
        "tertiary_link",
    }:
        multiplier += (
            0.5 if tags.get("sidewalk") in {"both", "left", "right", "yes"} else 2
        )
    for attribute, predicate in checks:
        value = data.get(attribute)
        if value is not None and not predicate(value):
            return None
        multiplier += 0.15 if value is None else 0
    if step_free and data["steps_present"] is None:
        multiplier += 0.1
    node_penalty = 0
    node_steps = 0
    for node in (edge.a, edge.b):
        if node not in graph.node_tags:
            continue
        node_tags, _ = graph.node_tags[node]
        if node_tags.get("access") in {"no", "private"} and node_tags.get(
            "foot"
        ) not in {"yes", "designated", "permissive"}:
            return None
        node_values = values(node_tags)
        if (
            step_free
            and constraints.max_slope_percent is not None
            and node_values["slope_percent"] is not None
            and node_values["slope_percent"] > constraints.max_slope_percent
        ):
            return None
        if node_tags.get("barrier") in {"wall", "fence", "block"}:
            return None
        if step_free and (
            node_values["steps_present"]
            or node_tags.get("barrier") in {"stile", "turnstile"}
            or node_tags.get("wheelchair") == "no"
        ):
            return None
        if node == edge.b:
            node_steps = node_values["steps_count"] or 0
            for attribute, predicate in checks:
                value = node_values.get(attribute)
                if value is not None and not predicate(value):
                    return None
    steps = edge.steps + node_steps
    if fastest:
        return walking_time(edge, graph), steps
    return edge.distance / 1.2 * multiplier + steps * 1.5 + node_penalty, steps


@dataclass(slots=True)
class Label:
    node: int
    cost: float
    steps: int
    unrested: float
    toilet_missing: bool
    previous: int | None
    edge: Edge | None


def plan_city_route(
    request: m.RoutePlanRequest, graph: CityGraph | None = None, *, fastest=False
):
    graph = graph or get_graph()
    constraints = request.constraints or m.Constraints.model_validate(
        {field: None for field in m.Constraints.model_fields}
    )
    assessment_constraints = constraints
    if fastest:
        constraints = m.Constraints.model_validate(
            {field: None for field in m.Constraints.model_fields}
        )
    warnings = [
        "Trasa oparta na OSM. Brak danych nie oznacza braku bariery; dostępność nie została zweryfikowana w terenie.",
        "Dojścia od wskazanych punktów do sieci pieszej są orientacyjne i wymagają sprawdzenia.",
    ]
    attribution = [
        m.Source(
            type="osm",
            label="© OpenStreetMap contributors",
            url="https://www.openstreetmap.org/copyright",
            license="ODbL",
            retrieved_at=datetime.fromisoformat(graph.metadata["generated_at"]),
        )
    ]

    def empty(message):
        return m.RoutePlanResponse(
            routes=[], warnings=[*warnings, message], attribution=attribution
        )

    start, finish = resolve(request.origin), resolve(request.destination)
    if start is None or finish is None:
        return empty("Nie znaleziono wskazanego miejsca w katalogu miasta.")
    snapped = []
    for point in (start, finish):
        snap = graph.snap(point)
        if snap is None:
            return empty(
                f"Punkt leży poza siecią pieszą lub dalej niż {SNAP_LIMIT} m od niej."
            )
        snapped.append(snap)
    # Virtual endpoints split existing directed edges, without joining nearby disconnected ways.
    nodes = {-1: start, -2: finish}
    extra = defaultdict(list)
    for number, (_point, snap) in enumerate(zip((start, finish), snapped, strict=True)):
        gap, original, _ratio, projected = snap
        virtual = -3 - number
        nodes[virtual] = projected
        if number == 0:
            extra[-1].append(Edge(-1, virtual, None, gap))
        else:
            extra[virtual].append(Edge(virtual, -2, None, gap))
        # Consider both existing directions of this exact way/segment.
        for index in graph.adjacency.get(original.a, []) + graph.adjacency.get(
            original.b, []
        ):
            edge = graph.edges[index]
            if edge.way != original.way or {edge.a, edge.b} != {original.a, original.b}:
                continue
            before = length(graph.nodes[edge.a], projected)
            after = length(projected, graph.nodes[edge.b])
            extra[edge.a].append(
                Edge(
                    edge.a,
                    virtual,
                    edge.way if before > 0.01 else None,
                    before,
                    round(edge.steps * before / edge.distance),
                )
            )
            extra[virtual].append(
                Edge(
                    virtual,
                    edge.b,
                    edge.way if after > 0.01 else None,
                    after,
                    round(edge.steps * after / edge.distance),
                )
            )
    # Two points on the same edge can travel directly, respecting pedestrian direction.
    first, last = snapped[0], snapped[1]
    if first[1].way == last[1].way and {first[1].a, first[1].b} == {
        last[1].a,
        last[1].b,
    }:
        edge = first[1]

        def projection(p):
            return length(graph.nodes[edge.a], p)

        delta = projection(last[3]) - projection(first[3])
        if delta >= 0:
            extra[-3].append(
                Edge(
                    -3,
                    -4,
                    edge.way,
                    abs(delta),
                    round(edge.steps * abs(delta) / edge.distance),
                )
            )
        else:
            reverse = next(
                (
                    graph.edges[i]
                    for i in graph.adjacency.get(edge.b, [])
                    if graph.edges[i].b == edge.a and graph.edges[i].way == edge.way
                ),
                None,
            )
            if reverse:
                extra[-3].append(
                    Edge(
                        -3,
                        -4,
                        edge.way,
                        abs(delta),
                        round(edge.steps * abs(delta) / edge.distance),
                    )
                )

    def coordinates(n):
        return nodes[n] if n < 0 else graph.nodes[n]

    checks = requirement_checks(constraints)
    labels = [
        Label(-1, 0, 0, 0, bool(constraints.require_accessible_toilet), None, None)
    ]
    frontier = defaultdict(list)
    frontier[-1].append(0)
    serial = count()
    queue = [(0.0, next(serial), 0)]
    costs = {}
    answer = None
    while queue:
        _, _, index = heappop(queue)
        label = labels[index]
        if index not in frontier[label.node]:
            continue
        if label.node == -2:
            answer = index
            break
        edges = [
            graph.edges[i] for i in graph.adjacency.get(label.node, [])
        ] + extra.get(label.node, [])
        for edge in edges:
            # Cache shared directed edges across resource labels.
            key = (edge.a, edge.b, edge.way, edge.distance, edge.steps)
            if key not in costs:
                costs[key] = edge_cost(edge, graph, constraints, checks, fastest)
            result = costs[key]
            if result is None:
                continue
            cost, steps = result
            next_steps = label.steps + steps
            if constraints.max_steps is not None:
                if next_steps > constraints.max_steps:
                    continue
            else:
                next_steps = 0
            unrested = label.unrested + edge.distance
            if constraints.max_distance_without_rest_m is not None:
                limit = constraints.max_distance_without_rest_m
                if unrested > limit:
                    continue
                # Conservative 10 m resource buckets keep city-scale label search finite.
                unrested = math.ceil(unrested / 10) * 10
                if edge.b in graph.rests:
                    unrested = 0
            else:
                unrested = 0
            missing = label.toilet_missing and edge.b not in graph.toilets
            if edge.b == -2 and missing:
                continue
            new = Label(
                edge.b, label.cost + cost, next_steps, unrested, missing, index, edge
            )
            existing = frontier[edge.b]

            def dominates(a, b):
                return (
                    a.cost <= b.cost
                    and a.steps <= b.steps
                    and a.unrested <= b.unrested
                    and a.toilet_missing <= b.toilet_missing
                )

            if any(dominates(labels[i], new) for i in existing):
                continue
            frontier[edge.b] = [i for i in existing if not dominates(new, labels[i])]
            next_index = len(labels)
            labels.append(new)
            frontier[edge.b].append(next_index)
            heuristic = length(coordinates(edge.b), finish) / 1.2
            heappush(queue, (new.cost + heuristic, next(serial), next_index))
    if answer is None:
        return empty(
            "Nie znaleziono trasy spełniającej Twoje wymagania w dostępnej sieci pieszej. Zmień punkty lub wymagania."
        )
    path = []
    cursor = answer
    while True:
        current = labels[cursor]
        if current.previous is None:
            break
        if current.edge is not None and current.edge.distance > 0.01:
            path.append(current.edge)
        cursor = current.previous
    path.reverse()
    return route_response(
        path, coordinates, graph, assessment_constraints, warnings, attribution
    )


def facts_for(tags, object_id, updated, retrieved):
    facts = extract_facts(tags, object_id, updated, retrieved)
    normalized = values(tags)
    for attribute, value in normalized.items():
        if any(f.attribute == attribute for f in facts):
            if value is not None:
                fact = next(f for f in facts if f.attribute == attribute)
                fact.value = value
                fact.unconfirmed_reason = "pending_verification"
                fact.sources = [
                    m.Source(
                        type="osm",
                        label="OpenStreetMap",
                        url=f"https://www.openstreetmap.org/{object_id}",
                        license="ODbL",
                        retrieved_at=retrieved,
                    )
                ]
            continue
        facts.append(
            m.Fact(
                id=f"osm/{object_id}/{attribute}",
                attribute=attribute,
                value=value,
                unit="percent"
                if attribute == "slope_percent"
                else "cm"
                if attribute.endswith("_cm")
                else None,
                status="unconfirmed",
                confidence_percent=None,
                observed_at=None,
                updated_at=updated,
                valid_until=None,
                sources=[
                    m.Source(
                        type="osm",
                        label="OpenStreetMap",
                        url=f"https://www.openstreetmap.org/{object_id}",
                        license="ODbL",
                        retrieved_at=retrieved,
                    )
                ]
                if value is not None
                else [],
                unconfirmed_reason="pending_verification"
                if value is not None
                else "missing",
            )
        )
    return facts


def route_response(path, coordinates, graph, constraints, warnings, attribution):
    now = datetime.now(UTC)
    retrieved = datetime.fromisoformat(graph.metadata["generated_at"])
    groups = []
    for edge in path:
        if groups and groups[-1][0].way == edge.way:
            groups[-1].append(edge)
        else:
            groups.append([edge])
    segments = []
    reasons = {}
    violated = set()
    unknown_resources = []
    checks = requirement_checks(constraints)
    if constraints.max_steps is not None:
        checks.append(("steps_count", lambda value: value <= constraints.max_steps))
    if constraints.require_step_free_access:
        checks.append(("steps_present", lambda value: value is False))
    total_steps = sum(
        edge.steps
        + (
            values(graph.node_tags[edge.b][0])["steps_count"] or 0
            if edge.b in graph.node_tags
            else 0
        )
        for edge in path
    )
    if constraints.max_steps is not None and total_steps > constraints.max_steps:
        violated.add("steps_count")
    longest_unrested = 0
    unrested = 0
    toilets = any(edge.a in graph.toilets or edge.b in graph.toilets for edge in path)
    for group_index, group in enumerate(groups):
        edge = group[0]
        way = graph.ways[edge.way] if edge.way is not None else None
        tags = way.tags if way else {}
        facts = facts_for(
            tags,
            f"way/{way.id}" if way else f"connector/{group_index}",
            way.updated if way else now,
            retrieved,
        )
        point_ids = {e.a for e in group} | {e.b for e in group}
        for node in point_ids & graph.node_tags.keys():
            node_tags, updated = graph.node_tags[node]
            facts.extend(
                f
                for f in facts_for(node_tags, f"node/{node}", updated, retrieved)
                if f.value is not None
            )
        segment_violations = set()
        for fact in facts:
            for attribute, predicate in checks:
                if (
                    fact.attribute == attribute
                    and fact.value is not None
                    and not predicate(fact.value)
                ):
                    violated.add(attribute)
                    segment_violations.add(attribute)
                    reasons.setdefault(attribute, []).append(fact.id)
        for piece in group:
            unrested += piece.distance
            longest_unrested = max(longest_unrested, unrested)
            if piece.b in graph.rests:
                unrested = 0
        assessment = m.Assessment(
            status="does_not_meet_requirements" if segment_violations else "uncertain",
            summary="Niedogodność wg OSM: "
            + ", ".join(
                ATTRIBUTE_NAMES.get(str(a), str(a)) for a in sorted(segment_violations)
            )
            if segment_violations
            else "Dane OSM wymagają weryfikacji.",
            reasons=[
                m.AssessmentReason(
                    code="OSM_INCONVENIENCE",
                    message=f"{ATTRIBUTE_NAMES.get(attribute, attribute)}: niedogodność na tym odcinku wg OSM.",
                    fact_ids=[
                        f.id
                        for f in facts
                        if f.attribute == attribute and f.value is not None
                    ],
                )
                for attribute in sorted(segment_violations)
            ],
        )
        if way:
            name = tags.get("name") or {
                "steps": "schody",
                "footway": "chodnik",
                "path": "ścieżka",
                "pedestrian": "deptak",
            }.get(tags.get("highway", ""), "droga piesza")
            direction = "Idź prosto"
            if group_index and len(groups[group_index - 1]) > 0:
                previous = groups[group_index - 1][-1]
                ax, ay = xy(coordinates(previous.a))
                bx, by = xy(coordinates(edge.a))
                cx, cy = xy(coordinates(edge.b))
                angle = math.degrees(
                    math.atan2(
                        (bx - ax) * (cy - by) - (by - ay) * (cx - bx),
                        (bx - ax) * (cx - bx) + (by - ay) * (cy - by),
                    )
                )
                if abs(angle) > 30:
                    direction = "Skręć w lewo" if angle > 0 else "Skręć w prawo"
            instruction = f"{direction}: {name}."
        else:
            instruction = (
                "Dojdź do sieci pieszej; sprawdź dostępność dojścia."
                if group_index == 0
                else "Dojdź do celu; sprawdź dostępność wejścia."
            )
        segments.append(
            m.RouteSegment(
                id=f"city-segment-{group_index}",
                distance_m=sum(e.distance for e in group),
                instruction=instruction,
                geometry=m.LineString(
                    type="LineString",
                    coordinates=[
                        coordinates(edge.a),
                        *[coordinates(e.b) for e in group],
                    ],
                ),
                assessment=assessment,
                facts=facts,
                barriers=[],
                rest_points=[graph.rests[n] for n in point_ids if n in graph.rests],
            )
        )
    if (
        constraints.max_distance_without_rest_m is not None
        and longest_unrested > constraints.max_distance_without_rest_m
    ):
        unknown_resources.append(
            "Brak zmapowanego odpoczynku w wymaganym odstępie na części trasy."
        )
    if constraints.require_accessible_toilet and not toilets:
        unknown_resources.append(
            "Nie znaleziono zmapowanej dostępnej toalety w pobliżu wybranej trasy."
        )
    warnings.extend(unknown_resources)
    if violated:
        warnings.append(
            "Nie udało się uniknąć wszystkich niedogodności. Sprawdź odcinki i niespełnione potrzeby przed wyjściem."
        )
    for attribute in sorted(violated):
        warnings.append(
            f"Pozostała niedogodność wg OSM: {ATTRIBUTE_NAMES.get(attribute, attribute)}."
        )
    warnings.append(
        "Czas przejścia jest orientacyjny. Miejsca odpoczynku i toalety w pobliżu trasy wymagają sprawdzenia dostępności."
    )
    assessment = m.Assessment(
        status="does_not_meet_requirements" if violated else "uncertain",
        summary="Trasa minimalizuje niedogodności, ale nie spełnia wszystkich potrzeb."
        if violated
        else "Wybrano trasę ograniczającą niedogodności; część parametrów jest nieznana.",
        reasons=[
            m.AssessmentReason(
                code="OSM_INCONVENIENCE",
                message=f"{ATTRIBUTE_NAMES.get(attribute, attribute)}: niedogodność wg niezweryfikowanych danych OSM.",
                fact_ids=reasons.get(attribute, []),
            )
            for attribute in sorted(violated)
        ]
        + [
            m.AssessmentReason(
                code="OSM_MISSING_RESOURCE", message=message, fact_ids=[]
            )
            for message in unknown_resources
        ],
    )
    geometry = (
        [coordinates(path[0].a), *[coordinates(edge.b) for edge in path]]
        if path
        else [coordinates(-1), coordinates(-2)]
    )
    if len(geometry) < 2:
        geometry *= 2
    duration = sum(walking_time(edge, graph) for edge in path)
    route = m.Route(
        id=f"city-{uuid4().hex}",
        distance_m=sum(edge.distance for edge in path),
        estimated_duration_s=duration,
        assessment=assessment,
        geometry=m.LineString(type="LineString", coordinates=geometry),
        segments=segments,
        facts=[fact for segment in segments for fact in segment.facts],
        computed_at=now,
    )
    return m.RoutePlanResponse(
        routes=[route], warnings=warnings, attribution=attribution
    )
