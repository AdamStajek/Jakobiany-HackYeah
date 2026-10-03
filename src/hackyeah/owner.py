"""Trusted assignments and owner declarations persisted in SQLite."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException

from hackyeah import models as m
from hackyeah.database import Store, atomic

_lock = atomic
_places = Store[str, tuple[str, m.PlaceSummary, list[m.Fact]]]("owner.places")
_declarations = Store[str, m.DeclarationRequest]("owner.declarations")
_history = Store[str, list[m.DeclarationRequest]]("owner.history")
_fact_ids = Store[tuple[str, str], str]("owner.fact_ids")
_required: set[m.Attribute] = {
    "steps_count",
    "threshold_height_cm",
    "elevator_available",
    "entrance_width_cm",
    "accessible_toilet",
}
_units: dict[m.Attribute, Literal["count", "cm", "percent", "m"]] = {
    "steps_count": "count",
    "threshold_height_cm": "cm",
    "kerb_height_cm": "cm",
    "entrance_width_cm": "cm",
    "slope_percent": "percent",
    "distance_without_rest_m": "m",
}
# Prototype policy: declarations older than one year need re-verification.
DECLARATION_VALIDITY = timedelta(days=365)


def assign_place(
    user_id: str, place: m.PlaceSummary, facts: list[m.Fact] | None = None
) -> None:
    """Trusted bootstrap only: ownership verification happens outside public API."""
    with _lock:
        previous = _places.get(place.id)
        if previous is not None and previous[0] != user_id:
            _declarations.pop(place.id, None)
        _places[place.id] = (
            user_id,
            place.model_copy(deep=True),
            [fact.model_copy(deep=True) for fact in facts or []],
        )
        for fact in facts or []:
            _fact_ids[(place.id, fact.attribute)] = fact.id


def _require_owner(user: m.User) -> None:
    if "owner" not in user.roles:
        raise HTTPException(403, "FORBIDDEN")


def _get(user: m.User, place_id: str) -> tuple[str, m.PlaceSummary, list[m.Fact]]:
    stored = _places.get(place_id)
    if stored is None or stored[0] != user.id:
        raise HTTPException(404, "NOT_FOUND")
    return stored


def list_page(user: m.User, limit: int, cursor: str | None) -> m.Page[m.PlaceSummary]:
    _require_owner(user)
    with _lock:
        items = sorted(
            (place for assigned, place, _ in _places.values() if assigned == user.id),
            key=lambda place: place.id,
        )
        if cursor is not None:
            _get(user, cursor)
            items = [place for place in items if place.id > cursor]
        return m.Page[m.PlaceSummary](
            items=[place.model_copy(deep=True) for place in items[:limit]],
            next_cursor=items[limit - 1].id if len(items) > limit else None,
        )


def declare(
    user: m.User, place_id: str, body: m.DeclarationRequest
) -> m.DeclarationResponse:
    _require_owner(user)
    with _lock:
        _, _, baseline = _get(user, place_id)
        now = datetime.now(UTC)
        if body.observed_at > now:
            raise HTTPException(422, "VALIDATION_ERROR")
        observations: dict[m.Attribute, m.Observation] = {
            item.attribute: item for item in body.observations
        }
        previous = _declarations.get(place_id)
        attributes: set[m.Attribute] = (
            _required | set(observations) | {fact.attribute for fact in baseline}
        )
        if previous is not None:
            attributes.update(item.attribute for item in previous.observations)
        source = m.Source(
            type="owner",
            label="Deklaracja właściciela",
            url=None,
            license=None,
            retrieved_at=now,
        )
        facts = []
        for attribute in sorted(attributes):
            original = [fact for fact in baseline if fact.attribute == attribute]
            observation = observations.get(attribute)
            if observation is None and original:
                for fact in original:
                    restored = fact.model_copy(deep=True)
                    if restored.valid_until is not None and restored.valid_until <= now:
                        restored.status = "unconfirmed"
                        restored.unconfirmed_reason = "stale"
                    facts.append(restored)
                continue
            value = observation.value if observation is not None else None
            conflict = value is not None and any(
                fact.value is not None and fact.value != value for fact in original
            )
            stale = body.observed_at + DECLARATION_VALIDITY <= now
            reason = (
                "missing"
                if value is None
                else "conflicting"
                if conflict
                else "stale"
                if stale
                else None
            )
            facts.append(
                m.Fact(
                    id=_fact_ids.setdefault(
                        (place_id, attribute), f"fact_{uuid4().hex}"
                    ),
                    attribute=attribute,
                    value=value,
                    unit=_units.get(attribute),
                    status="unconfirmed" if reason else "confirmed",
                    confidence_percent=None,
                    observed_at=body.observed_at if observation is not None else None,
                    updated_at=now,
                    valid_until=body.observed_at + DECLARATION_VALIDITY
                    if observation is not None
                    else None,
                    sources=([source] if observation is not None else [])
                    + [item for fact in original for item in fact.sources],
                    unconfirmed_reason=reason,
                )
            )
        stored = body.model_copy(deep=True)
        _declarations[place_id] = stored
        _history[place_id] = [*_history.get(place_id, []), stored.model_copy(deep=True)]
        return m.DeclarationResponse(place_id=place_id, facts=facts, updated_at=now)
