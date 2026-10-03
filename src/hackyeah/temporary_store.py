"""Additive SQLite storage for validated construction snapshots."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from hackyeah.models import TemporaryDataSnapshot

TABLES = ("temporary_imports", "temporary_difficulties")
SCHEMA = (
    """CREATE TABLE IF NOT EXISTS temporary_imports (
        source_key TEXT PRIMARY KEY,
        source TEXT NOT NULL CHECK (source = 'construction'),
        generated_at TEXT NOT NULL,
        valid_until TEXT NOT NULL,
        metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json))
    )""",
    """CREATE TABLE IF NOT EXISTS temporary_difficulties (
        source_key TEXT NOT NULL REFERENCES temporary_imports(source_key) ON DELETE CASCADE,
        id TEXT NOT NULL,
        category TEXT NOT NULL CHECK (category = 'construction'),
        starts_at TEXT,
        ends_at TEXT,
        data_json TEXT NOT NULL CHECK (json_valid(data_json)),
        PRIMARY KEY (source_key, id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_temporary_difficulties_time ON temporary_difficulties(category, starts_at, ends_at)",
)


def timestamp(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def ensure_schema(db: sqlite3.Connection) -> None:
    for statement in SCHEMA:
        db.execute(statement)


def source_key(snapshot: TemporaryDataSnapshot) -> str:
    if (
        snapshot.source != "construction"
        or snapshot.weather_hours
        or snapshot.heat_threshold_c is not None
        or any(
            item.category != "construction" or item.weather is not None
            for item in snapshot.items
        )
    ):
        raise ValueError(
            "Pogoda jest pobierana w locie i nie może być zapisana do SQLite."
        )
    return "construction"


def import_snapshots(
    database: Path,
    snapshots: list[TemporaryDataSnapshot],
    *,
    missing_only: bool = False,
) -> dict:
    """Replace latest data per source/point in one transaction; never touch places."""
    # Revalidate even objects built with model_construct or changed after parsing.
    validated = [
        TemporaryDataSnapshot.model_validate(s.model_dump()) for s in snapshots
    ]
    keys = [source_key(s) for s in validated]
    if len(set(keys)) != len(keys):
        raise ValueError(
            "Jeden import nie może zawierać dwóch kopii tego samego źródła/punktu."
        )
    # mode=rw requires an existing DB and avoids silently creating it at a typoed path.
    with closing(
        sqlite3.connect(database.resolve().as_uri() + "?mode=rw", uri=True)
    ) as db:
        db.execute("PRAGMA foreign_keys = ON")
        with db:
            db.execute("BEGIN IMMEDIATE")
            ensure_schema(db)
            for key, snapshot in zip(keys, validated, strict=True):
                existing = db.execute(
                    "SELECT generated_at FROM temporary_imports WHERE source_key=?",
                    (key,),
                ).fetchone()
                if (
                    not missing_only
                    and existing
                    and datetime.fromisoformat(existing[0]) > snapshot.generated_at
                ):
                    raise ValueError(
                        f"Odmowa zastąpienia nowszych danych starszą kopią: {key}."
                    )
                # Cascades remove only the previous successful copy of this source/point.
                if not missing_only:
                    db.execute(
                        "DELETE FROM temporary_imports WHERE source_key=?", (key,)
                    )
                db.execute(
                    ("INSERT OR IGNORE" if missing_only else "INSERT")
                    + " INTO temporary_imports VALUES (?, ?, ?, ?, ?)",
                    (
                        key,
                        snapshot.source,
                        timestamp(snapshot.generated_at),
                        timestamp(snapshot.valid_until),
                        snapshot.model_dump_json(
                            exclude={"items", "weather_hours", "heat_threshold_c"}
                        ),
                    ),
                )
                db.executemany(
                    ("INSERT OR IGNORE" if missing_only else "INSERT")
                    + " INTO temporary_difficulties VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (
                            key,
                            item.id,
                            item.category,
                            timestamp(item.starts_at),
                            timestamp(item.ends_at),
                            item.model_dump_json(),
                        )
                        for item in snapshot.items
                    ],
                )
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Import narusza spójność kluczy obcych.")
            return {
                table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in TABLES
            }


def preserve_temporary_data(previous: Path, target: sqlite3.Connection) -> None:
    """Carry this extension into a rebuilt OSM DB before its atomic replacement."""
    if not previous.exists():
        return
    with closing(
        sqlite3.connect(previous.resolve().as_uri() + "?mode=ro", uri=True)
    ) as source:
        source.execute("BEGIN")
        present = {
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        } & set(TABLES)
        if not present:
            return
        if present != set(TABLES):
            raise ValueError(
                "Niepełny schemat danych czasowych; przerwano przebudowę OSM."
            )
        ensure_schema(target)
        for table in TABLES:
            rows = source.execute(f"SELECT * FROM {table}")
            placeholders = ",".join("?" for _ in rows.description)
            target.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
