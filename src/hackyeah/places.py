"""Public place catalogue backed by the imported OSM snapshot."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from typing import get_args

from fastapi import HTTPException
from pydantic import ValidationError

from hackyeah import models as m
from hackyeah.confidence import get as get_confidence
from hackyeah.database import connect
from hackyeah.place_enrichment import accessibility_facts, enrichment


def _nearest_address(db: sqlite3.Connection, lat: float, lon: float) -> str | None:
    """Return the address of the closest place with a known OSM address."""
    best: tuple[float, str] | None = None
    for item in db.execute(
        """SELECT lat, lon, street, housenumber, address_unit, postcode, city
        FROM places WHERE street IS NOT NULL OR housenumber IS NOT NULL
        OR postcode IS NOT NULL OR city IS NOT NULL"""
    ):
        label = " ".join(str(value) for value in item[2:] if value)
        if not label:
            continue
        distance = (
            111_320
            * ((lat - item[0]) ** 2 + ((lon - item[1]) * cos(radians(lat))) ** 2) ** 0.5
        )
        if best is None or distance < best[0]:
            best = distance, label
    return best[1] if best else None


def _checks(constraints: m.Constraints | None):
    checks = []
    if constraints is not None:
        for field, attribute, minimum in (
            ("max_steps", "steps_count", False),
            ("max_threshold_cm", "threshold_height_cm", False),
            ("max_kerb_height_cm", "kerb_height_cm", False),
            ("max_slope_percent", "slope_percent", False),
            ("min_entrance_width_cm", "entrance_width_cm", True),
            ("max_distance_without_rest_m", "distance_without_rest_m", False),
        ):
            limit = getattr(constraints, field)
            if limit is not None:
                checks.append(
                    (
                        attribute,
                        lambda value, limit=limit, minimum=minimum: (
                            value >= limit if minimum else value <= limit
                        ),
                    )
                )
        if constraints.require_step_free_access:
            checks.append(("steps_count", lambda value: value == 0))
        for enabled, attribute in (
            (constraints.require_lighting, "lighting_available"),
            (constraints.require_accessible_toilet, "accessible_toilet"),
        ):
            if enabled:
                checks.append((attribute, lambda value: value is True))
        for allowed, attribute in (
            (constraints.allowed_surfaces, "surface"),
            (constraints.allowed_smoothness, "smoothness"),
        ):
            if allowed is not None:
                checks.append(
                    (attribute, lambda value, allowed=allowed: value in allowed)
                )
    return checks


def assess(facts: list[m.Fact], constraints: m.Constraints | None) -> m.Assessment:
    checks = _checks(constraints)
    reasons = []
    now = datetime.now(UTC)
    for attribute, predicate in checks:
        relevant = [fact for fact in facts if fact.attribute == attribute]
        confirmed = [
            fact
            for fact in relevant
            if fact.status == "confirmed"
            and fact.value is not None
            and (fact.valid_until is None or fact.valid_until > now)
        ]
        failed = any(not predicate(fact.value) for fact in confirmed)
        if failed or not confirmed or len(confirmed) != len(relevant):
            reasons.append(
                m.AssessmentReason(
                    code="REQUIREMENT_NOT_MET" if failed else "UNKNOWN_DATA",
                    message=f"{attribute}: wymaganie niespełnione."
                    if failed
                    else f"{attribute}: brak potwierdzonych, aktualnych danych.",
                    fact_ids=[fact.id for fact in relevant],
                )
            )
    status = (
        "does_not_meet_requirements"
        if any(reason.code == "REQUIREMENT_NOT_MET" for reason in reasons)
        else "uncertain"
        if reasons or not checks
        else "meets_requirements"
    )
    return m.Assessment(
        status=status,
        summary={
            "uncertain": "Brak wymagań lub potwierdzonych danych do oceny.",
            "does_not_meet_requirements": "Miejsce nie spełnia wymagań.",
            "meets_requirements": "Miejsce spełnia wymagania.",
        }[status],
        reasons=reasons,
    )


def source(
    updated: datetime, url: str | None = None, modified_at: str | None = None
) -> m.Source:
    return m.Source(
        type="osm",
        label="© OpenStreetMap contributors",
        url=url or "https://www.openstreetmap.org/copyright",
        license="ODbL",
        retrieved_at=updated,
        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
    )


def _facts(db: sqlite3.Connection, row: sqlite3.Row, updated: datetime) -> list[m.Fact]:
    facts = []
    for item in db.execute(
        "SELECT * FROM accessibility_facts WHERE place_id=? ORDER BY attribute",
        (row["id"],),
    ):
        if item["attribute"] not in get_args(m.Attribute):
            continue
        sources = [
            source(updated, evidence[0], evidence[1])
            for evidence in db.execute(
                "SELECT DISTINCT o.source_url, o.modified_at FROM fact_evidence e JOIN osm_objects o ON o.id=e.object_id WHERE e.place_id=? AND e.attribute=?",
                (row["id"], item["attribute"]),
            )
        ]
        raw_value = (
            json.loads(item["value_json"]) if item["value_json"] is not None else None
        )
        score, confidence_level, calculated_at = get_confidence(
            db, "place", row["id"], item["attribute"], raw_value
        )
        try:
            fact = m.Fact(
                id=f"{row['id']}:{item['attribute']}",
                attribute=item["attribute"],
                value=raw_value,
                unit=item["unit"],
                status=item["status"],
                confidence_score=score,
                confidence_level=confidence_level,
                confidence_calculated_at=calculated_at,
                confidence_percent=item["confidence_percent"],
                observed_at=item["observed_at"],
                updated_at=updated,
                valid_until=None,
                sources=sources,
                unconfirmed_reason=item["unconfirmed_reason"],
            )
        except ValidationError:
            # OSM surface vocabulary is broader than the API enum; preserve uncertainty.
            fact = m.Fact(
                id=f"{row['id']}:{item['attribute']}",
                attribute=item["attribute"],
                value=None,
                unit=item["unit"],
                status="unconfirmed",
                confidence_percent=None,
                observed_at=None,
                updated_at=updated,
                valid_until=None,
                sources=sources,
                unconfirmed_reason="missing",
            )
        facts.append(fact)
    return accessibility_facts(db, row["id"], facts)


def _details(
    db: sqlite3.Connection, row: sqlite3.Row, constraints: m.Constraints | None
) -> m.PlaceDetails:
    updated = datetime.fromisoformat(
        json.loads(
            db.execute(
                "SELECT value_json FROM metadata WHERE key='imported_at'"
            ).fetchone()[0]
        )
    )
    facts = _facts(db, row, updated)
    community = None
    if row["id"].startswith("community:"):
        from hackyeah.place_submissions import submissions

        community = submissions[row["id"]]
        updated = community.reviewed_at or community.created_at
        facts = [
            *facts,
            *[
                m.Fact(
                    id=f"{row['id']}:{attribute}",
                    attribute=attribute,
                    value=None,
                    unit=None,
                    status="unconfirmed",
                    confidence_percent=None,
                    observed_at=None,
                    updated_at=updated,
                    valid_until=None,
                    sources=[],
                    unconfirmed_reason="missing",
                )
                for attribute in (
                    "steps_count",
                    "threshold_height_cm",
                    "elevator_available",
                    "entrance_width_cm",
                    "accessible_toilet",
                )
                if attribute not in {fact.attribute for fact in facts}
            ],
        ]
    categories = [
        item[0]
        for item in db.execute(
            "SELECT c.label FROM place_categories pc JOIN categories c ON c.id=pc.category_id WHERE pc.place_id=? ORDER BY c.label",
            (row["id"],),
        )
    ]
    web = db.execute(
        "SELECT * FROM place_web_data WHERE place_id=?", (row["id"],)
    ).fetchone()
    extra, extra_sources = enrichment(db, row["id"])
    photos = []
    if extra_sources:
        seen = set()
        for record in db.execute(
            "SELECT data_json FROM external_place_data WHERE place_id=? AND source='commons' ORDER BY source_id",
            (row["id"],),
        ):
            photo = json.loads(record[0]).get("photo")
            if photo and photo["url"] not in seen:
                seen.add(photo["url"])
                photos.append(m.PlacePhoto.model_validate(photo))
    address = (
        " ".join(
            str(row[key] or extra.get(key))
            for key in ("street", "housenumber", "address_unit", "postcode", "city")
            if row[key] or extra.get(key)
        )
        or extra.get("address")
        or None
    )
    address_is_nearest = False
    if address is None:
        address = _nearest_address(db, row["lat"], row["lon"])
        address_is_nearest = address is not None
    return m.PlaceDetails(
        id=row["id"],
        name=row["name"] or "Miejsce bez nazwy",
        category=community.category if community else ", ".join(categories),
        address=address,
        address_is_nearest=address_is_nearest,
        location=m.Coordinates(lat=row["lat"], lon=row["lon"]),
        distance_m=None,
        assessment=assess(facts, constraints),
        facts=facts,
        barriers=[
            m.Barrier(
                id=f"{fact.id}:barrier",
                kind="permanent",
                description=description,
                location=m.Coordinates(lat=row["lat"], lon=row["lon"]),
                fact_ids=[fact.id],
                starts_at=None,
                ends_at=None,
                status=fact.status,
            )
            for fact in facts
            for attribute, value, description in (
                (
                    "steps_present",
                    True,
                    "Schody — lokalizacja obiektu OSM; przebieg wejścia wymaga sprawdzenia.",
                ),
                ("raised_kerb", True, "Podniesiony krawężnik."),
                ("lighting_available", False, "Brak oświetlenia według źródła."),
                (
                    "accessible_toilet",
                    False,
                    "Brak toalety dostosowanej do potrzeb osób z niepełnosprawnościami.",
                ),
                *(
                    ("smoothness", state, "Nierówna nawierzchnia: " + state)
                    for state in (
                        "bad",
                        "very_bad",
                        "horrible",
                        "very_horrible",
                        "impassable",
                    )
                ),
            )
            if fact.attribute == attribute and fact.value == value
        ],
        updated_at=updated,
        attribution=[
            m.Source(
                type="other",
                label="Zgłoszenie społeczności zatwierdzone przez administratora",
                url=None,
                license=None,
                retrieved_at=updated,
            )
            if community
            else source(updated),
            *[
                m.Source(
                    type="other",
                    label={
                        "msip": "MSIP Kraków",
                        "bip_libraries": "BIP — Biblioteka Kraków",
                        "wikidata": "Wikidata",
                        "commons": "Wikimedia Commons",
                    }.get(item["source"], str(item["source"])),
                    url=item["source_url"],
                    license=item["license"],
                    retrieved_at=datetime.fromisoformat(item["retrieved_at"]),
                )
                for item in extra_sources
            ],
        ],
        photos=photos,
        website=row["website"] or extra.get("website"),
        phone=row["phone"] or extra.get("phone") or (web["telephone"] if web else None),
        opening_hours=row["opening_hours"]
        or extra.get("opening_hours")
        or (web["opening_hours"] if web else None),
        operator=row["operator"],
        access=row["access"],
        website_title=web["title"] if web else None,
        website_description=(web["description"] if web else None)
        or (community.description if community else extra.get("description")),
        website_telephone=web["telephone"] if web else None,
        website_opening_hours=web["opening_hours"] if web else None,
        accessibility_summary=(web["accessibility_summary"] if web else None)
        or extra.get("accessibility_summary"),
        website_source=(
            m.Source(
                type="other",
                label="Strona miejsca",
                url=web["source_url"],
                license=None,
                retrieved_at=datetime.fromisoformat(web["retrieved_at"]),
            )
            if web
            else None
        ),
    )


def _connect() -> sqlite3.Connection:
    db = connect(readonly=True)
    db.row_factory = sqlite3.Row
    return db


def catalogue_table(db: sqlite3.Connection) -> str:
    if db.execute(
        "SELECT 1 FROM sqlite_master WHERE name='community_places'"
    ).fetchone():
        return "(SELECT * FROM places UNION ALL SELECT * FROM community_places)"
    return "places"


def get(place_id: str, constraints: m.Constraints | None = None) -> m.PlaceDetails:
    with closing(_connect()) as db:
        row = db.execute(
            f"SELECT * FROM {catalogue_table(db)} WHERE id=?", (place_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "NOT_FOUND")
        return _details(db, row, constraints)


def search(
    body: m.PlaceSearchRequest, constraints: m.Constraints | None
) -> m.PlaceSearchResponse:
    with closing(_connect()) as db:
        rows = db.execute(
            f"""SELECT p.* FROM {catalogue_table(db)} p
            WHERE p.id LIKE 'community:%' OR EXISTS (
                SELECT 1 FROM place_categories pc
                WHERE pc.place_id = p.id
                AND pc.category_id NOT IN ('rest_point', 'steps', 'kerb')
            )
            ORDER BY p.id"""
        ).fetchall()
        categories_by_place: dict[str, list[tuple[str, str]]] = {}
        for place_id, category_id, label in db.execute(
            """SELECT pc.place_id, c.id, c.label
            FROM place_categories pc JOIN categories c ON c.id=pc.category_id"""
        ):
            categories_by_place.setdefault(place_id, []).append((category_id, label))
        if body.cursor is not None and not any(
            row["id"] == body.cursor for row in rows
        ):
            raise HTTPException(422, "VALIDATION_ERROR")
        known_facts = dict(
            db.execute(
                "SELECT place_id, COUNT(*) FROM accessibility_facts WHERE value_json IS NOT NULL GROUP BY place_id"
            )
        )
        web_data = {
            row[0]: sum(value is not None and value != "" for value in row[1:])
            for row in db.execute("SELECT * FROM place_web_data")
        }
        external_data = {}
        if db.execute(
            "SELECT 1 FROM pragma_table_list WHERE name='external_place_data'"
        ).fetchone():
            external_data = {
                row[0]: (row[1], row[2])
                for row in db.execute(
                    """SELECT place_id,
                    MAX(source='commons' AND json_extract(data_json, '$.photo.url') IS NOT NULL),
                    SUM((SELECT COUNT(*) FROM json_each(data_json) WHERE value IS NOT NULL AND value != ''))
                    FROM external_place_data WHERE place_id IS NOT NULL GROUP BY place_id"""
                )
            }
        candidates = []
        for row in rows:
            categories = categories_by_place.get(row["id"], [])
            if row["id"].startswith("community:"):
                from hackyeah.place_submissions import submissions

                categories = [("community", submissions[row["id"]].category)]
            text = " ".join(
                str(value or "")
                for value in (
                    row["name"],
                    row["street"],
                    *(value for category in categories for value in category),
                )
            )
            if (
                body.query.strip() != "*"
                and body.query.strip().casefold() not in text.casefold()
            ):
                continue
            distance = None
            if body.near is not None:
                lat1, lat2 = radians(body.near.lat), radians(row["lat"])
                a = (
                    sin((lat2 - lat1) / 2) ** 2
                    + cos(lat1)
                    * cos(lat2)
                    * sin(radians(row["lon"] - body.near.lon) / 2) ** 2
                )
                distance = 6371000 * 2 * asin(sqrt(min(1, a)))
                if distance > body.radius_m:
                    continue
            has_photo, extra_fields = external_data.get(row["id"], (0, 0))
            populated_fields = sum(
                row[field] is not None and row[field] != ""
                for field in (
                    "name",
                    "street",
                    "housenumber",
                    "postcode",
                    "city",
                    "address_unit",
                    "website",
                    "phone",
                    "opening_hours",
                    "operator",
                    "access",
                )
            )
            candidates.append(
                (
                    -has_photo,
                    -(
                        populated_fields
                        + known_facts.get(row["id"], 0)
                        + web_data.get(row["id"], 0)
                        + extra_fields
                    ),
                    distance if distance is not None else 0,
                    row["id"],
                    row,
                    distance,
                )
            )
        candidates.sort(key=lambda candidate: candidate[:4])
        updated = datetime.fromisoformat(
            json.loads(
                db.execute(
                    "SELECT value_json FROM metadata WHERE key='imported_at'"
                ).fetchone()[0]
            )
        )
        matching = []
        checks = _checks(constraints)
        unassessed = assess([], constraints)
        for candidate in candidates:
            row = candidate[4]
            facts = _facts(db, row, updated) if checks else []
            if checks and not all(
                any(
                    fact.attribute == attribute
                    and fact.value is not None
                    and predicate(fact.value)
                    for fact in facts
                )
                for attribute, predicate in checks
            ):
                continue
            assessment = assess(facts, constraints) if checks else unassessed
            if assessment.status == "does_not_meet_requirements" or (
                not body.include_uncertain and assessment.status == "uncertain"
            ):
                continue
            matching.append(candidate)
        total_count = len(matching)
        if body.cursor is not None:
            cursor_index = next(
                (
                    index
                    for index, candidate in enumerate(matching)
                    if candidate[3] == body.cursor
                ),
                None,
            )
            if cursor_index is None:
                raise HTTPException(422, "VALIDATION_ERROR") from None
            matching = matching[cursor_index + 1 :]
        items = []
        for *_, row, distance in matching[: body.limit]:
            place = _details(db, row, constraints)
            items.append(
                m.PlaceSummary.model_validate(
                    {
                        **place.model_dump(include=set(m.PlaceSummary.model_fields)),
                        "distance_m": distance,
                    }
                )
            )
        next_cursor = items[-1].id if len(matching) > body.limit else None
    return m.PlaceSearchResponse(
        items=items[: body.limit],
        next_cursor=next_cursor,
        total_count=total_count,
        warnings=[
            "Dane pochodzą z lokalnej kopii OSM; import nie jest weryfikacją terenową."
        ],
        attribution=[source(updated)],
    )


def route_points(query: str) -> m.Page[m.PlaceSummary]:
    """Named places/addresses for endpoint selection, without accessibility filtering."""
    with closing(_connect()) as db:
        rows = db.execute(
            f"SELECT id,name,lat,lon,street,housenumber FROM {catalogue_table(db)} WHERE name IS NOT NULL ORDER BY name"
        ).fetchall()
    needle = query.strip().casefold()
    items = []
    for row in rows:
        address = " ".join(filter(None, (row["street"], row["housenumber"])))
        if needle not in f"{row['name']} {address}".casefold():
            continue
        items.append(
            m.PlaceSummary(
                id=row["id"],
                name=row["name"],
                category="Punkt trasy",
                assessment=m.Assessment(
                    status="uncertain",
                    summary="Punkt trasy z katalogu OSM.",
                    reasons=[],
                ),
                facts=[],
                address=address or None,
                location=m.Coordinates(lat=row["lat"], lon=row["lon"]),
                distance_m=None,
            )
        )
        if len(items) == 20:
            break
    return m.Page[m.PlaceSummary](items=items, next_cursor=None)
