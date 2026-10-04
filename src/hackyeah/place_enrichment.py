"""Source-labelled enrichment, kept separate from original OSM observations."""

import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path

from hackyeah import models as m

SCHEMA = """CREATE TABLE IF NOT EXISTS external_place_data (
    source TEXT NOT NULL, source_id TEXT NOT NULL,
    place_id TEXT REFERENCES places(id), source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL, license TEXT,
    match_method TEXT, data_json TEXT NOT NULL CHECK(json_valid(data_json)),
    PRIMARY KEY(source, source_id)
)"""


def ensure_schema(db: sqlite3.Connection) -> None:
    db.execute(SCHEMA)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_external_place ON external_place_data(place_id)"
    )


def distance_m(lat: float, lon: float, other_lat: float, other_lon: float) -> float:
    # Short city-scale distances, only used to reject distant candidate matches.
    return 111_320 * math.hypot(
        lat - other_lat, (lon - other_lon) * math.cos(math.radians(lat))
    )


def enrichment(db: sqlite3.Connection, place_id: str) -> tuple[dict, list[dict]]:
    if not db.execute(
        "SELECT 1 FROM pragma_table_list WHERE name='external_place_data'"
    ).fetchone():
        return {}, []
    values, sources = {}, []
    for row in db.execute(
        """SELECT source, source_url, retrieved_at, license, data_json
        FROM external_place_data WHERE place_id=?
        ORDER BY CASE source WHEN 'bip_libraries' THEN 0 WHEN 'msip' THEN 1 ELSE 2 END,
        retrieved_at DESC, source_id""",
        (place_id,),
    ):
        for key, value in json.loads(row[4]).items():
            if value is not None and value != "":
                values.setdefault(key, value)
        sources.append(
            dict(
                zip(
                    ("source", "source_url", "retrieved_at", "license"),
                    row[:4],
                    strict=True,
                )
            )
        )
    return values, sources


def effective_places(db: sqlite3.Connection) -> list[dict]:
    db.row_factory = sqlite3.Row
    rows = []
    for row in db.execute("SELECT * FROM places ORDER BY id").fetchall():
        place = dict(row)
        extra, _ = enrichment(db, place["id"])
        for key in place:
            if not place[key] and extra.get(key):
                place[key] = extra[key]
        web = db.execute(
            "SELECT telephone, opening_hours FROM place_web_data WHERE place_id=?",
            (place["id"],),
        ).fetchone()
        if web:
            place["phone"] = place.get("phone") or web[0]
            place["opening_hours"] = place.get("opening_hours") or web[1]
        rows.append(place)
    return rows


def import_records(database: Path, records: list[dict]) -> int:
    for row in records:
        for observation in row["data"].get("accessibility_observations", []):
            m.Observation.model_validate(observation)
    with (
        closing(
            sqlite3.connect(database.resolve().as_uri() + "?mode=rw", uri=True)
        ) as db,
        db,
    ):
        db.execute("PRAGMA foreign_keys=ON")
        ensure_schema(db)
        for row in records:
            db.execute(
                """INSERT INTO external_place_data VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, source_id) DO UPDATE SET
                place_id=excluded.place_id, source_url=excluded.source_url,
                retrieved_at=excluded.retrieved_at, license=excluded.license,
                match_method=excluded.match_method, data_json=excluded.data_json""",
                (
                    row["source"],
                    row["source_id"],
                    row.get("place_id"),
                    row["source_url"],
                    row["retrieved_at"],
                    row.get("license"),
                    row.get("match_method"),
                    json.dumps(row["data"], ensure_ascii=False),
                ),
            )
    return len(records)


def accessibility_facts(
    db: sqlite3.Connection, place_id: str, facts: list[m.Fact]
) -> list[m.Fact]:
    """Combine sourced observations without overwriting disagreement or human evidence."""
    from datetime import datetime

    if not db.execute(
        "SELECT 1 FROM pragma_table_list WHERE name='external_place_data'"
    ).fetchone():
        return facts
    by_attribute = {f.attribute: f for f in facts}
    for row in db.execute(
        "SELECT source, source_url, retrieved_at, license, data_json FROM external_place_data WHERE place_id=? ORDER BY source, source_id",
        (place_id,),
    ):
        retrieved = datetime.fromisoformat(row[2])
        for raw in json.loads(row[4]).get("accessibility_observations", []):
            observation = m.Observation.model_validate(raw)
            if observation.value is None:
                continue
            old = by_attribute.get(observation.attribute)
            if old is not None and old.status == "confirmed":
                continue
            source = m.Source(
                type="other",
                label=row[0],
                url=row[1],
                license=row[3],
                retrieved_at=retrieved,
            )
            conflict = old is not None and (
                old.unconfirmed_reason == "conflicting"
                or (old.value is not None and old.value != observation.value)
            )
            by_attribute[observation.attribute] = m.Fact(
                id=f"{place_id}:{observation.attribute}",
                attribute=observation.attribute,
                value=None if conflict else observation.value,
                unit=old.unit if old else None,
                status="unconfirmed",
                confidence_percent=None,
                observed_at=None,
                updated_at=max(old.updated_at, retrieved) if old else retrieved,
                valid_until=None,
                sources=[*(old.sources if old else []), source],
                unconfirmed_reason="conflicting"
                if conflict
                else "pending_verification",
            )
    return list(by_attribute.values())


def preserve_enrichment(previous: Path, target: sqlite3.Connection) -> None:
    ensure_schema(target)
    if not previous.exists():
        return
    ids = {row[0] for row in target.execute("SELECT id FROM places")}
    with closing(
        sqlite3.connect(previous.resolve().as_uri() + "?mode=ro", uri=True)
    ) as source:
        if not source.execute(
            "SELECT 1 FROM pragma_table_list WHERE name='external_place_data'"
        ).fetchone():
            return
        for row in source.execute("SELECT * FROM external_place_data"):
            values = list(row)
            if values[2] not in ids:
                values[2] = None
                values[6] = None
            target.execute(
                "INSERT INTO external_place_data VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                values,
            )
