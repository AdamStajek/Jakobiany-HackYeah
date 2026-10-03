"""Persistent field missions; photo verification or independent moderator review awards points."""

import json
from contextlib import closing
from datetime import UTC, datetime
from hashlib import sha256
from math import cos, radians
from uuid import uuid4

from fastapi import HTTPException

from hackyeah import models as m
from hackyeah import places, reports
from hackyeah.database import Store, atomic

_catalog = Store[str, m.Mission]("missions.catalog")
_progress = Store[str, m.MissionProgress]("missions.progress")
_enrollments = Store[tuple[str, str], str]("missions.enrollments")
_report_progress = Store[str, str]("missions.report_progress")


def catalog(near: m.Coordinates | None = None, offset: int = 0) -> list[m.Mission]:
    """Refresh tasks from current facts, retaining completed tasks for history."""

    candidates = []
    with closing(places._connect()) as db:
        updated = datetime.fromisoformat(
            json.loads(
                db.execute(
                    "SELECT value_json FROM metadata WHERE key='imported_at'"
                ).fetchone()[0]
            )
        )
        if near is None:
            rows = db.execute(
                "SELECT * FROM places ORDER BY id LIMIT 100 OFFSET ?", (offset,)
            ).fetchall()
        else:
            lat_delta = 200 / 111000
            lon_delta = lat_delta / max(0.01, abs(cos(radians(near.lat))))
            rows = db.execute(
                "SELECT * FROM places WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ? ORDER BY id",
                (
                    near.lat - lat_delta,
                    near.lat + lat_delta,
                    near.lon - lon_delta,
                    near.lon + lon_delta,
                ),
            ).fetchall()
        for row in rows:
            facts = places._facts(db, row, updated)
            known = {fact.attribute for fact in facts}
            for attribute in (
                "steps_count",
                "threshold_height_cm",
                "entrance_width_cm",
                "accessible_toilet",
                "elevator_available",
            ):
                if attribute not in known:
                    facts.append(
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
                    )
            for fact in facts:
                missing = fact.unconfirmed_reason == "missing" or (
                    fact.value is None and fact.unconfirmed_reason != "conflicting"
                )
                uncertain = (
                    fact.status == "unconfirmed"
                    or fact.confidence_level == "uncertain"
                    or (
                        fact.confidence_percent is not None
                        and fact.confidence_percent <= 60
                    )
                    or (
                        fact.valid_until is not None
                        and fact.valid_until <= datetime.now(UTC)
                    )
                )
                candidates.append((row, fact, missing, uncertain))
    with atomic:
        active = []
        for row, fact, missing, uncertain in candidates:
            mission_id = "mission_" + sha256(fact.id.encode()).hexdigest()[:24]
            previous = _catalog.get(mission_id)
            requested = previous is not None and previous.priority == 1
            available = missing or uncertain
            if not available and previous is None:
                continue
            mission = m.Mission(
                id=mission_id,
                place_id=row["id"],
                place_name=row["name"] or "Miejsce bez nazwy",
                title=f"Sprawdź: {row['name'] or 'Miejsce bez nazwy'}",
                fact_id=fact.id,
                attribute=fact.attribute,
                priority=1 if requested else 2 if missing else 3,
                location=m.Coordinates(lat=row["lat"], lon=row["lon"]),
                available=available,
                points=30,
                time_minutes=10,
            )
            if previous != mission:
                _catalog[mission_id] = mission
            active.append(mission)
        current_ids = {item.id for item in active}
        history_ids = {item.mission_id for item in _progress.values()}
        for previous in _catalog.values():
            if previous.id not in current_ids and (
                previous.priority == 1 or previous.id in history_ids
            ):
                active.append(previous)
        return sorted(
            active, key=lambda item: (item.priority, item.place_name, item.id)
        )


def request_verification(body: m.MissionRequest) -> list[m.Mission]:
    """Create or reuse field missions for low-confidence place facts."""
    catalog()
    place = places.get(body.place_id)
    facts_by_id = {item.id: item for item in place.facts}
    if len(set(body.fact_ids)) != len(body.fact_ids):
        raise HTTPException(422, "VALIDATION_ERROR")
    facts = []
    for fact_id in body.fact_ids:
        fact = facts_by_id.get(fact_id)
        if fact is None:
            raise HTTPException(404, "NOT_FOUND")
        facts.append(fact)
    if any(
        fact.status != "unconfirmed"
        and not (fact.confidence_percent is not None and fact.confidence_percent <= 60)
        for fact in facts
    ):
        raise HTTPException(422, "FACT_NOT_LOW_CONFIDENCE")
    result = []
    with atomic:
        for fact in facts:
            mission_id = "mission_" + sha256(fact.id.encode()).hexdigest()[:24]
            mission = _catalog.get(mission_id)
            if mission is None:
                mission = m.Mission(
                    id=mission_id,
                    place_id=place.id,
                    place_name=place.name,
                    title=f"Sprawdź: {place.name} — {fact.attribute}",
                    fact_id=fact.id,
                    attribute=fact.attribute,
                    points=30,
                    time_minutes=10,
                )
                _catalog[mission.id] = mission
            mission = mission.model_copy(
                update={"priority": 1, "location": place.location}
            )
            _catalog[mission.id] = mission
            result.append(mission)
    return result


def get(mission_id: str) -> m.Mission:
    mission = _catalog.get(mission_id)
    if mission is None:
        catalog()
        mission = _catalog.get(mission_id)
    if mission is None:
        raise HTTPException(404, "NOT_FOUND")
    return mission


def activity(user: m.User) -> m.MissionActivity:
    # ponytail: scans progress records; add indexed SQL when account volume grows.
    with atomic:
        items = [item for item in _progress.values() if item.user_id == user.id]
        return m.MissionActivity(
            items=items, points=sum(item.awarded_points for item in items)
        )


def queue(user: m.User, limit: int, cursor: str | None) -> m.Page[m.MissionProgress]:
    if "moderator" not in user.roles:
        raise HTTPException(403, "FORBIDDEN")
    with atomic:
        items = sorted(
            (
                item
                for item in _progress.values()
                if item.status == "pending"
                and item.user_id != user.id
                and (cursor is None or item.id > cursor)
            ),
            key=lambda item: item.id,
        )
        return m.Page[m.MissionProgress](
            items=items[:limit],
            next_cursor=items[limit - 1].id if len(items) > limit else None,
        )


def start(user: m.User, mission_id: str) -> m.MissionProgress:
    mission = get(mission_id)
    with atomic:
        existing = _enrollments.get((user.id, mission_id))
        if existing is not None:
            return _progress[existing]
        if not mission.available:
            raise HTTPException(409, "MISSION_UNAVAILABLE")
        now = datetime.now(UTC)
        progress = m.MissionProgress(
            id=f"progress_{uuid4().hex}",
            mission_id=mission_id,
            user_id=user.id,
            status="in_progress",
            report_id=None,
            answer="",
            awarded_points=0,
            review_comment=None,
            created_at=now,
            updated_at=now,
        )
        _progress[progress.id] = progress
        _enrollments[(user.id, mission_id)] = progress.id
        return progress


def submit(user: m.User, mission_id: str, body: m.MissionSubmit) -> m.MissionProgress:
    mission = get(mission_id)
    if any(
        observation.attribute != mission.attribute for observation in body.observations
    ):
        raise HTTPException(422, "VALIDATION_ERROR")
    # Validate enrollment before inference and again before committing.
    with atomic:
        enrollment = _enrollments.get((user.id, mission_id))
        if enrollment is None or _progress[enrollment].status not in (
            "in_progress",
            "rejected",
        ):
            raise HTTPException(409, "CONFLICT")
    report = reports.prepare(
        user,
        m.ReportCreate(
            target=m.ReportTarget(type="place", id=mission.place_id),
            kind="missing_data",
            fact_id=mission.fact_id,
            description=body.description.strip(),
            observations=body.observations,
            photo_ids=body.photo_ids,
        ),
        verification_attribute=mission.attribute,
    )
    with atomic:
        enrollment = _enrollments.get((user.id, mission_id))
        if enrollment is None:
            raise HTTPException(409, "CONFLICT")
        progress = _progress[enrollment]
        if progress.status not in ("in_progress", "rejected"):
            raise HTTPException(409, "CONFLICT")
        reports.save(user, report)
        progress = progress.model_copy(
            update={
                "status": "pending",
                "report_id": report.id,
                "answer": body.description.strip(),
                "review_comment": None,
                "updated_at": datetime.now(UTC),
            }
        )
        _progress[progress.id] = progress
        _report_progress[report.id] = progress.id
        sync_review(report)
        return _progress[progress.id]


def linked_progress(report_id: str) -> m.MissionProgress | None:
    progress_id = _report_progress.get(report_id)
    return _progress[progress_id] if progress_id is not None else None


def check_review(user: m.User, report_id: str) -> None:
    progress = linked_progress(report_id)
    if progress is not None:
        if progress.user_id == user.id:
            raise HTTPException(403, "FORBIDDEN")
        if progress.report_id != report_id:
            raise HTTPException(409, "CONFLICT")


def sync_review(report: m.Report) -> None:
    progress = linked_progress(report.id)
    if progress is not None and progress.report_id == report.id:
        mission = _catalog[progress.mission_id]
        _progress[progress.id] = progress.model_copy(
            update={
                "status": report.status,
                "review_comment": report.review_comment,
                "awarded_points": mission.points if report.status == "accepted" else 0,
                "updated_at": report.updated_at,
            }
        )


def review(user: m.User, progress_id: str, body: m.ReportReview) -> m.MissionProgress:
    if "moderator" not in user.roles:
        raise HTTPException(403, "FORBIDDEN")
    with atomic:
        progress = _progress.get(progress_id)
        if progress is None:
            raise HTTPException(404, "NOT_FOUND")
        if progress.report_id is None:
            raise HTTPException(409, "CONFLICT")
        reports.review(user, progress.report_id, body)
        return _progress[progress_id]
