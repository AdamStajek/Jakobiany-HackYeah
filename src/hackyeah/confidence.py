"""Persisted credibility scores for map, owner and user observations."""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Literal

from hackyeah.database import atomic

ConfidenceLevel = Literal["certain", "probable", "uncertain"]

SCHEMA = """CREATE TABLE IF NOT EXISTS fact_confidence (
    target_type TEXT NOT NULL CHECK(target_type IN ('place', 'segment')),
    target_id TEXT NOT NULL,
    attribute TEXT NOT NULL,
    value_json TEXT NOT NULL CHECK(json_valid(value_json)),
    score REAL NOT NULL CHECK(score >= 0),
    level TEXT NOT NULL CHECK(level IN ('certain', 'probable', 'uncertain')),
    calculated_at TEXT NOT NULL,
    PRIMARY KEY(target_type, target_id, attribute, value_json)
)"""


def level(score: float) -> ConfidenceLevel:
    if score > 10:
        return "certain"
    if score > 5:
        return "probable"
    return "uncertain"


def _weeks(old: datetime, now: datetime) -> int:
    return max(0, (now - old).days // 7)


def _time_factor(old: datetime, now: datetime) -> float:
    return 0.9 ** _weeks(old, now)


def _date(value: datetime | str | None, fallback: datetime) -> datetime:
    if value is None:
        return fallback
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(SCHEMA)


def recalculate_all(
    now: datetime | None = None, target: tuple[str, str] | None = None
) -> None:
    """Idempotently rebuild scores from the evidence currently stored in SQLite."""
    from hackyeah import owner, reports, reputation

    now = now or datetime.now(UTC)
    scores: dict[tuple[str, str, str, str], float] = {}
    user_scores: dict[tuple[str, str, str, str], float] = {}

    def add(
        target_type: str,
        target_id: str,
        attribute: str,
        value: object,
        points: float,
        bucket: dict[tuple[str, str, str, str], float] = scores,
    ) -> None:
        key = (
            target_type,
            target_id,
            attribute,
            json.dumps(value, ensure_ascii=False, sort_keys=True),
        )
        bucket[key] = bucket.get(key, 0) + points

    with atomic as connection:
        ensure_schema(connection)
        imported = connection.execute(
            "SELECT value_json FROM metadata WHERE key='imported_at'"
        ).fetchone()
        imported_at = _date(json.loads(imported[0]) if imported else None, now)
        query = "SELECT place_id, attribute, value_json FROM accessibility_facts"
        arguments: tuple[str, ...] = ()
        if target is not None:
            if target[0] == "place":
                query += " WHERE place_id=?"
                arguments = (target[1],)
            else:
                query += " WHERE 0"
        for place_id, attribute, value_json in connection.execute(query, arguments):
            value = json.loads(value_json) if value_json is not None else None
            add("place", place_id, attribute, value, 0)
            if value is not None:
                add(
                    "place",
                    place_id,
                    attribute,
                    value,
                    5 * _time_factor(imported_at, now),
                )

        for place_id, declarations in owner._history.items():
            if target is not None and target != ("place", place_id):
                continue
            for declaration in declarations:
                for observation in declaration.observations:
                    add(
                        "place",
                        place_id,
                        observation.attribute,
                        observation.value,
                        15 * _time_factor(declaration.observed_at, now),
                    )

        all_reports = list(reports._reports.values())
        reliability = reputation.scores()
        for report in all_reports:
            if report.status != "accepted":
                continue
            if target is not None and target != (
                report.target.type,
                report.target.id,
            ):
                continue
            x = reliability.get(report.author_id, 0.5)
            review = reports._reviews.get(report.id)
            accepted_ai = {
                (
                    report.ai_proposals[index].attribute,
                    report.ai_proposals[index].value,
                )
                for index in (
                    review.accepted_ai_proposal_indexes
                    if review is not None and report.ai_status == "completed"
                    else []
                )
            }
            observed_at = _date(report.observed_at, report.created_at)
            for observation in reports._accepted_observations.get(report.id, []):
                y = (
                    1
                    if (observation.attribute, observation.value) in accepted_ai
                    and report.photo_ids
                    else 0.25
                )
                add(
                    report.target.type,
                    report.target.id,
                    observation.attribute,
                    observation.value,
                    5 * x * y * _time_factor(observed_at, now),
                    user_scores,
                )

        for key, points in user_scores.items():
            scores[key] = scores.get(key, 0) + min(15, points)

        if target is None:
            connection.execute("DELETE FROM fact_confidence")
        else:
            connection.execute(
                "DELETE FROM fact_confidence WHERE target_type=? AND target_id=?",
                target,
            )
        calculated_at = now.isoformat()
        connection.executemany(
            "INSERT INTO fact_confidence VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                (*key, score, level(score), calculated_at)
                for key, score in scores.items()
            ),
        )


def get(
    connection: sqlite3.Connection,
    target_type: str,
    target_id: str,
    attribute: str,
    value: object,
) -> tuple[float, ConfidenceLevel, datetime | None]:
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fact_confidence'"
    ).fetchone():
        return 0, "uncertain", None
    row = connection.execute(
        """SELECT score, level, calculated_at FROM fact_confidence
        WHERE target_type=? AND target_id=? AND attribute=? AND value_json=?""",
        (
            target_type,
            target_id,
            attribute,
            json.dumps(value, ensure_ascii=False, sort_keys=True),
        ),
    ).fetchone()
    if row is None:
        return 0, "uncertain", None
    return row[0], row[1], datetime.fromisoformat(row[2])
