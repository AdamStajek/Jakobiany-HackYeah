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
    defer_processing: bool = False,
) -> m.Report:
    now = datetime.now(UTC)
    if body.observed_at is None:
        body = body.model_copy(update={"observed_at": now})
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
    if defer_processing:
        items = photos.validate_owned(user, report.photo_ids)
        if any(item.status == "rejected" for item in items):
            raise HTTPException(409, "PHOTO_REJECTED")
        if items and (report.observations or verification_attribute is not None):
            report.ai_status = "pending"
            report.review_comment = "Przetwarzanie zdjęcia i weryfikacja w tle."
        return report
    images = photos.owned_contents(user, report.photo_ids)
    if any(
        photos.get(user, photo_id).error_code == "PHOTO_ANALYSIS_UNAVAILABLE"
        for photo_id in report.photo_ids
    ):
        report.ai_status = "failed"
        report.review_comment = (
            "Analiza zdjęcia jest niedostępna; wymagana ręczna weryfikacja."
        )
    else:
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


def create(
    user: m.User, body: m.ReportCreate, *, defer_processing: bool = False
) -> m.Report:
    return save(user, prepare(user, body, defer_processing=defer_processing))


def process(report_id: str) -> None:
    """Verify outside a transaction and discard results if the report changed."""
    from hackyeah import missions

    with _lock:
        original = _reports.get(report_id)
        if original is None or original.ai_status != "pending":
            return
        report = original.model_copy(deep=True)
        progress = missions.linked_progress(report_id)
        if progress is not None:
            return
    user = m.User(id=report.author_id, display_name="Background verification", roles=[])
    items = photos.validate_owned(user, report.photo_ids)
    processing = any(item.status == "processing" for item in items)
    if processing and progress is None:
        return
    if any(
        item.status == "rejected"
        or item.error_code not in {None, "PHOTO_DESCRIPTION_UNAVAILABLE"}
        for item in items
    ):
        report.ai_status = "failed"
        report.review_comment = (
            "Analiza zdjęcia jest niedostępna. Wyślij zdjęcie ponownie."
        )
    else:
        images = (
            photos.verification_contents(user, report.photo_ids)
            if progress and processing
            else photos.owned_contents(user, report.photo_ids)
        )
        if progress and processing:
            for photo_id, item in zip(report.photo_ids, items, strict=True):
                if item.status == "processing":
                    photos.process(photo_id)
            items = photos.validate_owned(user, report.photo_ids)
            if any(item.status == "rejected" for item in items):
                report.ai_status = "failed"
                report.review_comment = (
                    "Nie udało się zanonimizować zdjęcia przed jego zapisaniem."
                )
        if report.ai_status != "failed":
            attribute = missions.get(progress.mission_id).attribute if progress else None
            report_ai.verify(report, images, attribute)
    report.updated_at = datetime.now(UTC)
    with _lock:
        if _reports.get(report_id) != original:
            return
        _reports[report_id] = report
        if report.status == "accepted":
            _accepted_observations[report_id] = report.observations
        missions.sync_review(report)
        _refresh_confidence(report)


def accept_due_missions() -> None:
    """Temporary demo acceptance, five seconds after mission submission."""
    from hackyeah import missions

    now = datetime.now(UTC)
    with _lock:
        for report in _reports.values():
            progress = missions.linked_progress(report.id)
            if (
                report.status != "pending"
                or progress is None
                or progress.report_id != report.id
                or (now - report.created_at).total_seconds() < 5
            ):
                continue
            report.status = "accepted"
            report.ai_status = "not_requested"
            report.review_comment = (
                "Automatycznie zaakceptowano w trybie demonstracyjnym."
            )
            report.updated_at = now
            _reports[report.id] = report
            _accepted_observations[report.id] = report.observations
            missions.sync_review(report)
            _refresh_confidence(report)


def fail_processing(original: m.Report, message: str) -> None:
    from hackyeah import missions

    with _lock:
        if _reports.get(original.id) != original:
            return
        report = original.model_copy(deep=True)
        report.ai_status = "failed"
        report.review_comment = message
        report.updated_at = datetime.now(UTC)
        _reports[report.id] = report
        missions.sync_review(report)


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


def update(
    user: m.User, report_id: str, body: m.ReportPatch, *, defer_processing: bool = False
) -> m.Report:
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
    updated = prepare(user, content, defer_processing=defer_processing)
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
    if "moderator" not in user.roles:
        raise HTTPException(403, "FORBIDDEN")
    raise HTTPException(403, "FORBIDDEN")
