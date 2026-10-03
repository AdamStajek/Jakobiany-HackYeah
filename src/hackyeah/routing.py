"""Routing on an in-memory graph of existing API models; no database or OSM IO."""

from datetime import UTC, datetime
from heapq import heappop, heappush
from itertools import count
from math import asin, cos, radians, sin, sqrt

from hackyeah import models as m


def distance(a: m.Coordinates, b: m.Coordinates) -> float:
    lat1, lat2 = radians(a.lat), radians(b.lat)
    h = (
        sin((lat2 - lat1) / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(radians(b.lon - a.lon) / 2) ** 2
    )
    return 6371000 * 2 * asin(min(1, sqrt(h)))


def walking_duration(segment: m.RouteSegment, at: datetime) -> tuple[float, bool]:
    """Heuristic seconds and whether any inputs needed an assumed default.

    Coefficients are prototype assumptions, not calibrated walking measurements.
    Slope is unsigned in the API, so both directions receive the same penalty.
    """
    surface_factors = {
        "paved": 1.0,
        "asphalt": 1.0,
        "gravel": 1.25,
        "cobblestone": 1.3,
        "ground": 1.4,
        "other": 1.4,
    }
    smoothness_factors = dict(
        zip(
            (
                "excellent",
                "good",
                "intermediate",
                "bad",
                "very_bad",
                "horrible",
                "very_horrible",
                "impassable",
            ),
            (1.0, 1.0, 1.15, 1.35, 1.6, 2.0, 2.5, 4.0),
            strict=True,
        )
    )
    values = {}
    for fact in segment.facts:
        if (
            fact.status == "confirmed"
            and fact.value is not None
            and (fact.valid_until is None or fact.valid_until > at)
        ):
            values.setdefault(fact.attribute, []).append(fact.value)
    assumed = False

    def worst(attribute, transform, default):
        nonlocal assumed
        known = values.get(attribute, [])
        if not known:
            assumed = True
            return default
        return max(transform(value) for value in known)

    surface = worst("surface", lambda value: surface_factors[value], 1.4)
    smoothness = worst("smoothness", lambda value: smoothness_factors[value], 1.35)
    slope = worst("slope_percent", float, 5.0)
    steps = worst("steps_count", float, 20.0)
    return segment.distance_m / 1.2 * surface * smoothness * (
        1 + 0.06 * slope
    ) + steps * 1.5, assumed


def permitted(
    segment: m.RouteSegment, constraints: m.Constraints, at: datetime
) -> bool:
    values = {}
    for fact in segment.facts:
        if (
            fact.status == "confirmed"
            and fact.value is not None
            and (fact.valid_until is None or fact.valid_until > at)
        ):
            values.setdefault(fact.attribute, []).append(fact.value)

    if "impassable" in values.get("smoothness", []):
        return False

    def check(attribute, predicate):
        facts = values.get(attribute, [])
        return bool(facts) and all(predicate(value) for value in facts)

    for field, attribute in (
        ("max_threshold_cm", "threshold_height_cm"),
        ("max_kerb_height_cm", "kerb_height_cm"),
        ("max_slope_percent", "slope_percent"),
    ):
        limit = getattr(constraints, field)
        if limit is not None and not check(
            attribute, lambda value, limit=limit: value <= limit
        ):
            return False
    if constraints.min_entrance_width_cm is not None and not check(
        "entrance_width_cm", lambda value: value >= constraints.min_entrance_width_cm
    ):
        return False
    for required, attribute in (
        (constraints.require_lighting, "lighting_available"),
        (constraints.require_accessible_toilet, "accessible_toilet"),
    ):
        if required and not check(attribute, lambda value: value is True):
            return False
    for allowed, attribute in (
        (constraints.allowed_surfaces, "surface"),
        (constraints.allowed_smoothness, "smoothness"),
    ):
        if allowed is not None and not check(
            attribute, lambda value, allowed=allowed: value in allowed
        ):
            return False
    if constraints.require_step_free_access and not (
        check("steps_count", lambda value: value == 0)
        and check("steps_present", lambda value: value is False)
    ):
        return False
    return not any(
        (barrier.starts_at is None or barrier.starts_at <= at)
        and (barrier.ends_at is None or at < barrier.ends_at)
        for barrier in segment.barriers
    )


def plan_route(
    request: m.RoutePlanRequest,
    nodes: dict[str, m.Coordinates],
    edges: list[tuple[str, str, m.RouteSegment]],
    profiles: dict[str, m.Profile] | None = None,
) -> m.RoutePlanResponse:
    """Edges are directed. Rest points reset distance only at their exact geometry position."""
    warnings = [
        "Prototyp: syntetyczna sieć centrum Krakowa, bez gwarancji rzeczywistej dostępności."
    ]

    def empty(message):
        return m.RoutePlanResponse(
            routes=[], warnings=[*warnings, message], attribution=[]
        )

    constraints = request.constraints
    if request.profile_id is not None:
        profile = (profiles or {}).get(request.profile_id)
        if profile is None:
            return empty("Nieznany profil w pamięci prototypu.")
        constraints = profile.constraints
    if constraints is None:
        constraints = m.Constraints.model_validate(
            {field: None for field in m.Constraints.model_fields}
        )

    def resolve(point):
        if isinstance(point, m.PlaceReference):
            return point.place_id if point.place_id in nodes else None
        # ponytail: snap only within 1 m; add verified pedestrian connectors for arbitrary coordinates.
        return next(
            (key for key, location in nodes.items() if distance(point, location) <= 1),
            None,
        )

    start, finish = resolve(request.origin), resolve(request.destination)
    if start is None or finish is None:
        return empty(
            "Punkt poza grafem demonstracyjnym; podaj identyfikator węzła lub jego współrzędne (tolerancja 1 m)."
        )
    now = datetime.now(UTC)
    at = request.departure_at or now
    adjacency: dict[str, list[tuple[str, m.RouteSegment]]] = {}
    durations = {}
    assumed_segments = set()
    for source, target, segment in edges:
        if permitted(segment, constraints, at):
            adjacency.setdefault(source, []).append((target, segment))
            duration, assumed = walking_duration(segment, at)
            durations[id(segment)] = duration
            if assumed:
                assumed_segments.add(id(segment))
    serial = count()
    queue: list[
        tuple[float, int, str, int, float, tuple[str, ...], list[m.RouteSegment]]
    ] = [(0.0, next(serial), start, 0, 0.0, (start,), [])]
    # ponytail: enumerate simple paths on the tiny demo graph; use resource-constrained labels for a city-sized graph.
    while queue:
        total, _, node, steps, unrested, visited, segments = heappop(queue)
        if node == finish:
            coordinates = [(nodes[start].lon, nodes[start].lat)]
            for segment in segments:
                coordinates.extend(segment.geometry.coordinates[1:])
            if len(coordinates) == 1:
                coordinates *= 2
            assessment = m.Assessment(
                status="meets_requirements",
                summary="Spełnia ograniczenia na danych demonstracyjnych.",
                reasons=[],
            )
            route = m.Route(
                id="prototype-route",
                distance_m=sum(segment.distance_m for segment in segments),
                estimated_duration_s=total,
                assessment=assessment,
                geometry=m.LineString(type="LineString", coordinates=coordinates),
                segments=[
                    segment.model_copy(update={"assessment": assessment})
                    for segment in segments
                ],
                facts=[fact for segment in segments for fact in segment.facts],
                computed_at=now,
            )
            warnings.append(
                "Czas przejścia jest szacunkiem z heurystycznych współczynników; nachylenie traktowane jest jednakowo w obu kierunkach."
            )
            if any(id(segment) in assumed_segments for segment in segments):
                warnings.append(
                    "Brakujące, niepotwierdzone lub wygasłe dane czasu zastąpiono ostrożnymi wartościami domyślnymi."
                )
            return m.RoutePlanResponse(
                routes=[route], warnings=warnings, attribution=[]
            )
        for target, segment in adjacency.get(node, []):
            if target in visited:
                continue
            step_facts = [
                fact for fact in segment.facts if fact.attribute == "steps_count"
            ]
            if constraints.max_steps is not None and (
                not step_facts
                or any(
                    fact.status != "confirmed"
                    or fact.value is None
                    or (fact.valid_until is not None and fact.valid_until <= at)
                    for fact in step_facts
                )
            ):
                continue
            next_steps = steps + max(
                (int(fact.value) for fact in step_facts if fact.value is not None),
                default=0,
            )
            if constraints.max_steps is not None and next_steps > constraints.max_steps:
                continue
            next_unrested = unrested
            rest_duration = 0.0
            rest_locations = {
                (rest.location.lon, rest.location.lat) for rest in segment.rest_points
            }
            for a, b in zip(
                segment.geometry.coordinates,
                segment.geometry.coordinates[1:],
                strict=False,
            ):
                next_unrested += distance(
                    m.Coordinates(lon=a[0], lat=a[1]), m.Coordinates(lon=b[0], lat=b[1])
                )
                if (
                    constraints.max_distance_without_rest_m is not None
                    and next_unrested > constraints.max_distance_without_rest_m
                ):
                    break
                if b in rest_locations:
                    if (
                        constraints.max_distance_without_rest_m is not None
                        and next_unrested > 0
                        and b != (nodes[finish].lon, nodes[finish].lat)
                    ):
                        rest_duration += 60.0
                    next_unrested = 0.0
            else:
                heappush(
                    queue,
                    (
                        total + durations[id(segment)] + rest_duration,
                        next(serial),
                        target,
                        next_steps,
                        next_unrested,
                        (*visited, target),
                        [*segments, segment],
                    ),
                )
    return empty(
        "Brak trasy spełniającej ograniczenia; brakujące, niepotwierdzone lub wygasłe wymagane fakty wykluczają odcinek."
    )


def demo_graph():
    nodes = {
        "rynek": m.Coordinates(lat=50.0617, lon=19.9373),
        "planty": m.Coordinates(lat=50.0605, lon=19.9325),
        "wawel": m.Coordinates(lat=50.0543, lon=19.9354),
    }
    now = datetime.now(UTC)
    edges = []
    for source, target, steps in (
        ("rynek", "wawel", 12),
        ("rynek", "planty", 0),
        ("planty", "wawel", 0),
    ):
        for a, b in ((source, target), (target, source)):
            values: dict[m.Attribute, int | bool | m.Surface | m.Smoothness] = {
                "steps_count": steps,
                "steps_present": bool(steps),
                "threshold_height_cm": 0,
                "kerb_height_cm": 0,
                "raised_kerb": False,
                "ramp_available": False,
                "surface": "paved",
                "smoothness": "good",
                "lighting_available": True,
                "slope_percent": 2,
                "entrance_width_cm": 150,
                "accessible_toilet": False,
            }
            facts = [
                m.Fact(
                    id=f"{a}-{b}-{attribute}",
                    attribute=attribute,
                    value=value,
                    unit="count"
                    if attribute == "steps_count"
                    else "percent"
                    if attribute == "slope_percent"
                    else "cm"
                    if attribute.endswith("_cm")
                    else None,
                    status="confirmed",
                    confidence_percent=None,
                    observed_at=now,
                    updated_at=now,
                    valid_until=None,
                    sources=[],
                    unconfirmed_reason=None,
                )
                for attribute, value in values.items()
            ]
            segment = m.RouteSegment(
                id=f"{a}-{b}",
                distance_m=distance(nodes[a], nodes[b]),
                instruction=f"Idź do: {b} (odcinek demonstracyjny).",
                geometry=m.LineString(
                    type="LineString",
                    coordinates=[
                        (nodes[a].lon, nodes[a].lat),
                        (nodes[b].lon, nodes[b].lat),
                    ],
                ),
                assessment=m.Assessment(
                    status="uncertain", summary="Dane syntetyczne.", reasons=[]
                ),
                facts=facts,
                barriers=[],
                rest_points=[
                    m.RestPoint(
                        id=f"rest-{b}",
                        location=nodes[b],
                        description="Demonstracyjny punkt odpoczynku.",
                        fact_ids=[],
                    )
                ],
            )
            edges.append((a, b, segment))
    return nodes, edges
