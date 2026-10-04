"""SQLite-backed reports with local photo verification and review history.

Target/fact existence and publishing accepted facts await the place data service.
"""

import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException

from hackyeah import models as m
from hackyeah import photos, report_ai
from hackyeah.database import Store, atomic

_lock = atomic
_reports = Store[str, m.Report]("reports.reports")
_history = Store[str, list[m.Report]]("reports.history")
_reviews = Store[str, m.ReportReview]("reports.reviews")
_accepted_observations = Store[str, list[m.Observation]](
    "reports.accepted_observations"
)


def _refresh_confidence(report: m.Report) -> None:
    refresh_author_confidence(report.author_id)


def refresh_author_confidence(author_id: str) -> None:
    from hackyeah.confidence import recalculate_all

    targets = {
        (item.target.type, item.target.id)
        for item in _reports.values()
        if item.author_id == author_id
    }
    for target in targets:
        recalculate_all(target=target)


def get(user: m.User, report_id: str) -> m.Report:
    with _lock:
        report = _reports.get(report_id)
        if report is None or (
            report.author_id != user.id and "moderator" not in user.roles
        ):
            raise HTTPException(404, "NOT_FOUND")
        return report.model_copy(deep=True)


def prepare(
    user: m.User,
    body: m.ReportCreate,
    *,
    verification_attribute: m.Attribute | None = None,
) -> m.Report:
    now = datetime.now(UTC)
    report = m.Report(
        **body.model_dump(),
        id=f"report_{uuid4().hex}",
        author_id=user.id,
        status="pending",
        ai_status="not_requested",
        ai_proposals=[],
        review_comment=None,
        created_at=now,
        updated_at=now,
    )
    images = photos.owned_contents(user, report.photo_ids)
    report_ai.verify(report, images, verification_attribute)
    return report


def save(user: m.User, report: m.Report) -> m.Report:
    with _lock:
        photos.replace_report_links(user, report.id, report.photo_ids)
        _reports[report.id] = report
        _history[report.id] = []
        if report.status == "accepted":
            _accepted_observations[report.id] = report.observations
        _refresh_confidence(report)
    return report.model_copy(deep=True)


def create(user: m.User, body: m.ReportCreate) -> m.Report:
    return save(user, prepare(user, body))


def list_page(
    user: m.User,
    mine: bool | None,
    status: m.ReportStatus | None,
    limit: int,
    cursor: str | None,
) -> m.Page[m.Report]:
    moderator = "moderator" in user.roles
    if (mine is False or status == "pending") and not moderator:
        raise HTTPException(403, "FORBIDDEN")
    own_only = mine is True or not moderator
    scope = [user.id, own_only, status]
    with _lock:
        items = sorted(
            (
                report
                for report in _reports.values()
                if (not own_only or report.author_id == user.id)
                and (status is None or report.status == status)
            ),
            key=lambda report: (report.created_at, report.id),
            reverse=True,
        )
        if cursor is not None:
            try:
                decoded = json.loads(
                    base64.b64decode(cursor, altchars=b"-_", validate=True)
                )
                if decoded["scope"] != scope:
                    raise ValueError
                anchor = (datetime.fromisoformat(decoded["created_at"]), decoded["id"])
                if anchor[0].tzinfo is None or not isinstance(anchor[1], str):
                    raise ValueError
            except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                raise HTTPException(400, "INVALID_REQUEST") from None
            items = [
                report for report in items if (report.created_at, report.id) < anchor
            ]
        next_cursor = None
        if len(items) > limit:
            last = items[limit - 1]
            next_cursor = base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "scope": scope,
                        "created_at": last.created_at.isoformat(),
                        "id": last.id,
                    }
                ).encode()
            ).decode()
        return m.Page[m.Report](
            items=[report.model_copy(deep=True) for report in items[:limit]],
            next_cursor=next_cursor,
        )


def update(user: m.User, report_id: str, body: m.ReportPatch) -> m.Report:
    from hackyeah import missions

    with _lock:
        report = get(user, report_id)
        if missions.linked_progress(report_id) is not None:
            raise HTTPException(409, "CONFLICT")
        if report.author_id != user.id:
            raise HTTPException(404, "NOT_FOUND")
        values = {**report.model_dump(), **body.model_dump(exclude_unset=True)}
        # Revalidate the resulting content, including attempts to clear every field.
        try:
            content = m.ReportCreate.model_validate(
                {name: values[name] for name in m.ReportCreate.model_fields}
            )
        except ValueError:
            raise HTTPException(422, "VALIDATION_ERROR") from None
    updated = prepare(user, content)
    updated.id = report.id
    updated.created_at = report.created_at
    with _lock:
        if _reports[report_id] != report:
            raise HTTPException(409, "CONFLICT")
        photos.replace_report_links(user, report_id, updated.photo_ids)
        _history[report_id] = [*_history[report_id], report]
        _reports[report_id] = updated
        _reviews.pop(report_id, None)
        _accepted_observations.pop(report_id, None)
        if updated.status == "accepted":
            _accepted_observations[report_id] = updated.observations
        _refresh_confidence(report)
        return updated.model_copy(deep=True)


def review(user: m.User, report_id: str, body: m.ReportReview) -> m.Report:
    from hackyeah import missions

    if "moderator" not in user.roles:
        raise HTTPException(403, "FORBIDDEN")
    with _lock:
        report = get(user, report_id)
        missions.check_review(user, report_id)
        if report.status != "pending":
            if _reviews.get(report_id) == body:
                return report
            raise HTTPException(409, "CONFLICT")
        indexes = body.accepted_ai_proposal_indexes
        if len(set(indexes)) != len(indexes) or any(
            index >= len(report.ai_proposals) for index in indexes
        ):
            raise HTTPException(422, "VALIDATION_ERROR")
        if body.decision == "rejected" and indexes:
            raise HTTPException(422, "VALIDATION_ERROR")
        updated = report.model_copy(
            update={
                "status": body.decision,
                "review_comment": body.comment,
                "updated_at": datetime.now(UTC),
            },
            deep=True,
        )
        _history[report_id] = [*_history[report_id], report]
        _reviews[report_id] = body.model_copy(deep=True)
        _reports[report_id] = updated
        if body.decision == "accepted":
            _accepted_observations[report_id] = [
                observation.model_copy(deep=True) for observation in report.observations
            ] + [
                m.Observation(
                    attribute=report.ai_proposals[index].attribute,
                    value=report.ai_proposals[index].value,
                )
                for index in indexes
            ]
        _refresh_confidence(report)
        missions.sync_review(updated)
        return updated.model_copy(deep=True)
