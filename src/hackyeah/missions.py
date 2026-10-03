"""Persistent field missions; only independent moderator review awards points."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from hackyeah import models as m
from hackyeah import places, reports
from hackyeah.database import Store, atomic

_catalog = Store[str, m.Mission]("missions.catalog")
_progress = Store[str, m.MissionProgress]("missions.progress")
_enrollments = Store[tuple[str, str], str]("missions.enrollments")
_report_progress = Store[str, str]("missions.report_progress")


def catalog() -> list[m.Mission]:
    with atomic:
        if not _catalog:
            for place in places.search(
                m.PlaceSearchRequest(query="*", limit=12), None
            ).items:
                fact = next(
                    (fact for fact in place.facts if fact.status == "unconfirmed"), None
                )
                if fact is None:
                    continue
                mission = m.Mission(
                    id="mission_" + sha256(fact.id.encode()).hexdigest()[:24],
                    place_id=place.id,
                    place_name=place.name,
                    title=f"Sprawdź dostępność: {place.name}",
                    fact_id=fact.id,
                    attribute=fact.attribute,
                    points=30,
                    time_minutes=10,
                )
                _catalog[mission.id] = mission
        return list(_catalog.values())


def get(mission_id: str) -> m.Mission:
    catalog()
    mission = _catalog.get(mission_id)
    if mission is None:
        raise HTTPException(404, "NOT_FOUND")
    return mission


def activity(user: m.User) -> m.MissionActivity:
    # ponytail: at most twelve missions per user; add indexed SQL if the catalog grows.
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
    get(mission_id)
    with atomic:
        existing = _enrollments.get((user.id, mission_id))
        if existing is not None:
            return _progress[existing]
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
    with atomic:
        enrollment = _enrollments.get((user.id, mission_id))
        if enrollment is None:
            raise HTTPException(409, "CONFLICT")
        progress = _progress[enrollment]
        if progress.status not in ("in_progress", "rejected"):
            raise HTTPException(409, "CONFLICT")
        report = reports.create(
            user,
            m.ReportCreate(
                target=m.ReportTarget(type="place", id=mission.place_id),
                kind="missing_data",
                fact_id=mission.fact_id,
                description=body.description.strip(),
                observations=body.observations,
                photo_ids=body.photo_ids,
            ),
        )
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
        return progress


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
