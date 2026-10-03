"""SQLite-backed profiles."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException

from hackyeah import models as m
from hackyeah.database import Store, atomic

_lock = atomic
_profiles = Store[str, tuple[str, m.Profile]]("profiles.profiles")


def get(user_id: str, profile_id: str) -> m.Profile:
    with _lock:
        stored = _profiles.get(profile_id)
        if stored is None or stored[0] != user_id:
            raise HTTPException(404, "Profile not found")
        return stored[1].model_copy(deep=True)


def list_page(user_id: str, limit: int, cursor: str | None) -> m.Page[m.Profile]:
    with _lock:
        items = sorted(
            (profile for owner, profile in _profiles.values() if owner == user_id),
            key=lambda profile: (profile.created_at, profile.id),
        )
        if cursor is not None:
            previous = get(user_id, cursor)
            items = [
                item
                for item in items
                if (item.created_at, item.id) > (previous.created_at, previous.id)
            ]
        return m.Page[m.Profile](
            items=[item.model_copy(deep=True) for item in items[:limit]],
            next_cursor=items[limit - 1].id if len(items) > limit else None,
        )


def create(user_id: str, body: m.ProfileCreate) -> m.Profile:
    now = datetime.now(UTC)
    profile = m.Profile(
        **body.model_dump(),
        id=f"profile_{uuid4().hex}",
        created_at=now,
        updated_at=now,
    )
    with _lock:
        _profiles[profile.id] = (user_id, profile)
    return profile.model_copy(deep=True)


def update(user_id: str, profile_id: str, body: m.ProfilePatch) -> m.Profile:
    with _lock:
        profile = get(user_id, profile_id)
        updated = m.Profile.model_validate(
            {
                **profile.model_dump(),
                **body.model_dump(exclude_unset=True),
                "updated_at": datetime.now(UTC),
            }
        )
        _profiles[profile_id] = (user_id, updated)
        return updated.model_copy(deep=True)


def delete(user_id: str, profile_id: str) -> None:
    with _lock:
        get(user_id, profile_id)
        del _profiles[profile_id]
