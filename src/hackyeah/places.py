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
from hackyeah.database import database_path


def assess(facts: list[m.Fact], constraints: m.Constraints | None) -> m.Assessment:
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


def source(updated: datetime, url: str | None = None) -> m.Source:
    return m.Source(
        type="osm",
        label="© OpenStreetMap contributors",
        url=url or "https://www.openstreetmap.org/copyright",
        license="ODbL",
        retrieved_at=updated,
    )


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
    facts = []
    for item in db.execute(
        "SELECT * FROM accessibility_facts WHERE place_id=? ORDER BY attribute",
        (row["id"],),
    ):
        if item["attribute"] not in get_args(m.Attribute):
            continue
        sources = [
            source(updated, evidence[0])
            for evidence in db.execute(
                "SELECT DISTINCT o.source_url FROM fact_evidence e JOIN osm_objects o ON o.id=e.object_id WHERE e.place_id=? AND e.attribute=?",
                (row["id"], item["attribute"]),
            )
        ]
        try:
            fact = m.Fact(
                id=f"{row['id']}:{item['attribute']}",
                attribute=item["attribute"],
                value=json.loads(item["value_json"])
                if item["value_json"] is not None
                else None,
                unit=item["unit"],
                status=item["status"],
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
    categories = [
        item[0]
        for item in db.execute(
            "SELECT category_id FROM place_categories WHERE place_id=? ORDER BY category_id",
            (row["id"],),
        )
    ]
    address = (
        " ".join(
            str(row[key])
            for key in ("street", "housenumber", "address_unit", "postcode", "city")
            if row[key]
        )
        or None
    )
    return m.PlaceDetails(
        id=row["id"],
        name=row["name"] or "Miejsce bez nazwy",
        category=",".join(categories),
        address=address,
        location=m.Coordinates(lat=row["lat"], lon=row["lon"]),
        distance_m=None,
        assessment=assess(facts, constraints),
        facts=facts,
        barriers=[],
        updated_at=updated,
        attribution=[source(updated)],
    )


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(database_path().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def get(place_id: str, constraints: m.Constraints | None = None) -> m.PlaceDetails:
    with closing(_connect()) as db:
        row = db.execute("SELECT * FROM places WHERE id=?", (place_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "NOT_FOUND")
        return _details(db, row, constraints)


def search(
    body: m.PlaceSearchRequest, constraints: m.Constraints | None
) -> m.PlaceSearchResponse:
    items = []
    with closing(_connect()) as db:
        rows = db.execute("SELECT * FROM places ORDER BY id").fetchall()
        if body.cursor is not None and not any(
            row["id"] == body.cursor for row in rows
        ):
            raise HTTPException(422, "VALIDATION_ERROR")
        for row in rows:
            if body.cursor is not None and row["id"] <= body.cursor:
                continue
            categories = db.execute(
                "SELECT c.id, c.label FROM categories c JOIN place_categories pc ON pc.category_id=c.id WHERE pc.place_id=?",
                (row["id"],),
            ).fetchall()
            text = " ".join(
                str(value or "")
                for value in (
                    row["name"],
                    row["street"],
                    *(value for category in categories for value in category),
                )
            )
            if body.query.strip().casefold() not in text.casefold():
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
            place = _details(db, row, constraints)
            if place.assessment.status == "does_not_meet_requirements" or (
                not body.include_uncertain and place.assessment.status == "uncertain"
            ):
                continue
            items.append(
                m.PlaceSummary.model_validate(
                    {
                        **place.model_dump(include=set(m.PlaceSummary.model_fields)),
                        "distance_m": distance,
                    }
                )
            )
            if len(items) > body.limit:
                break
        updated = datetime.fromisoformat(
            json.loads(
                db.execute(
                    "SELECT value_json FROM metadata WHERE key='imported_at'"
                ).fetchone()[0]
            )
        )
    return m.PlaceSearchResponse(
        items=items[: body.limit],
        next_cursor=items[body.limit - 1].id if len(items) > body.limit else None,
        warnings=[
            "Dane pochodzą z lokalnej kopii OSM; import nie jest weryfikacją terenową."
        ],
        attribution=[source(updated)],
    )
