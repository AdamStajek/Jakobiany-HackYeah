"""New places remain private until an independent moderator accepts them."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException

from hackyeah import models as m
from hackyeah.database import Store, atomic

submissions = Store[str, m.PlaceSubmission]("places.submissions")


def create(user: m.User, body: m.PlaceSubmissionCreate) -> m.PlaceSubmission:
    item = m.PlaceSubmission(
        **body.model_dump(),
        id=f"community:{uuid4().hex}",
        author_id=user.id,
        created_at=datetime.now(UTC),
    )
    submissions[item.id] = item
    return item


def list_page(
    user: m.User, limit: int, cursor: str | None, mine: bool = False
) -> m.Page[m.PlaceSubmission]:
    items = sorted(
        (
            item
            for item in submissions.values()
            if (
                item.status == "pending"
                if "moderator" in user.roles and not mine
                else item.author_id == user.id
            )
        ),
        key=lambda item: (item.created_at, item.id),
    )
    if cursor is not None:
        index = next((i for i, item in enumerate(items) if item.id == cursor), None)
        if index is None:
            raise HTTPException(422, "VALIDATION_ERROR")
        items = items[index + 1 :]
    return m.Page[m.PlaceSubmission](
        items=items[:limit],
        next_cursor=items[limit - 1].id if len(items) > limit else None,
    )


def review(user: m.User, id: str, body: m.PlaceSubmissionReview) -> m.PlaceSubmission:
    if "moderator" not in user.roles:
        raise HTTPException(403, "FORBIDDEN")
    with atomic as db:
        item = submissions.get(id)
        if item is None:
            raise HTTPException(404, "NOT_FOUND")
        if item.author_id == user.id:
            raise HTTPException(403, "FORBIDDEN")
        if item.status != "pending":
            raise HTTPException(409, "CONFLICT")
        item.status = body.decision
        item.reviewer_id = user.id
        item.reviewed_at = datetime.now(UTC)
        item.review_comment = body.comment.strip()
        if item.status == "accepted":
            location = body.location or item.location
            if location is None:
                raise HTTPException(422, "PLACE_LOCATION_REQUIRED")
            item.location = location
            db.execute(
                "INSERT INTO community_places (id,name,lat,lon,street) VALUES (?,?,?,?,?)",
                (
                    item.id,
                    item.name,
                    location.lat,
                    location.lon,
                    item.address,
                ),
            )
        submissions[id] = item
        from hackyeah.reports import refresh_author_confidence

        refresh_author_confidence(item.author_id)
        return item
