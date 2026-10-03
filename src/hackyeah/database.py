"""Additive SQLite storage shared by the implemented API domains."""

import base64
import json
import os
import sqlite3
from collections.abc import Iterator, MutableMapping
from contextlib import closing
from datetime import datetime
from pathlib import Path
from threading import local
from typing import Any, cast

from pydantic import BaseModel

from hackyeah import models as m

SCHEMA = """CREATE TABLE IF NOT EXISTS backend_records (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value BLOB NOT NULL,
    PRIMARY KEY (namespace, key)
)"""
_models = {
    model.__name__: model
    for model in (
        m.User,
        m.Session,
        m.Profile,
        m.Photo,
        m.Report,
        m.ReportReview,
        m.Observation,
        m.PlaceSummary,
        m.Fact,
        m.DeclarationRequest,
    )
}
_state = local()


def database_path() -> Path:
    return Path(
        os.environ.get(
            "DATABASE_PATH",
            str(Path(__file__).resolve().parents[2] / "data/krakow.sqlite3"),
        )
    ).resolve()


def _encode(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return {
            "$type": "model",
            "name": type(value).__name__,
            "data": value.model_dump(mode="json"),
        }
    if isinstance(value, datetime):
        return {"$type": "datetime", "data": value.isoformat()}
    if isinstance(value, bytes):
        return {"$type": "bytes", "data": base64.b64encode(value).decode()}
    if isinstance(value, set):
        return {"$type": "set", "data": sorted(value)}
    raise TypeError(f"Unsupported stored value: {type(value).__name__}")


def _decode(value: dict) -> Any:
    match value.get("$type"):
        case "model":
            return _models[value["name"]].model_validate(value["data"])
        case "datetime":
            return datetime.fromisoformat(value["data"])
        case "bytes":
            return base64.b64decode(value["data"], validate=True)
        case "set":
            return set(value["data"])
    return value


class Atomic:
    """Nested domain operations share one SQLite transaction, including photo links."""

    def __enter__(self) -> sqlite3.Connection:
        if getattr(_state, "connection", None) is None:
            connection = sqlite3.connect(
                database_path().as_uri() + "?mode=rw",
                uri=True,
                timeout=30,
                isolation_level=None,
            )
            try:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(SCHEMA)
            except BaseException:
                connection.close()
                raise
            _state.connection = connection
            _state.depth = 0
        _state.depth += 1
        return _state.connection

    def __exit__(self, exception_type, exception, traceback) -> None:
        _state.depth -= 1
        if _state.depth == 0:
            connection = _state.connection
            try:
                connection.execute(
                    "ROLLBACK" if exception_type is not None else "COMMIT"
                )
            finally:
                connection.close()
                _state.connection = None


atomic = Atomic()


def initialize() -> None:
    """Require the existing file and add backend tables."""
    with atomic:
        _state.connection.execute(
            """CREATE TABLE IF NOT EXISTS place_web_data (
                place_id TEXT PRIMARY KEY REFERENCES places(id),
                source_url TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                title TEXT,
                description TEXT,
                telephone TEXT,
                opening_hours TEXT,
                accessibility_summary TEXT
            )"""
        )


class Store[K, V](MutableMapping[K, V]):
    """Record operations return detached values; assign changes explicitly to persist."""

    def __init__(self, namespace: str, *, binary: bool = False):
        self.namespace = namespace
        self.binary = binary

    def __getitem__(self, key: K) -> V:
        with atomic as connection:
            row = connection.execute(
                "SELECT value FROM backend_records WHERE namespace=? AND key=?",
                (self.namespace, json.dumps(key)),
            ).fetchone()
            if row is None:
                raise KeyError(key)
            return row[0] if self.binary else json.loads(row[0], object_hook=_decode)

    def __setitem__(self, key: K, value: V) -> None:
        encoded = value if self.binary else json.dumps(value, default=_encode).encode()
        with atomic as connection:
            connection.execute(
                "INSERT INTO backend_records VALUES (?, ?, ?) "
                "ON CONFLICT(namespace, key) DO UPDATE SET value=excluded.value",
                (self.namespace, json.dumps(key), encoded),
            )

    def __delitem__(self, key: K) -> None:
        with atomic as connection:
            if (
                connection.execute(
                    "DELETE FROM backend_records WHERE namespace=? AND key=?",
                    (self.namespace, json.dumps(key)),
                ).rowcount
                == 0
            ):
                raise KeyError(key)

    def __iter__(self) -> Iterator[K]:
        with atomic as connection:
            keys = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT key FROM backend_records WHERE namespace=? ORDER BY key",
                    (self.namespace,),
                )
            ]
        return iter(
            cast(K, tuple(key) if isinstance(key, list) else key) for key in keys
        )

    def __len__(self) -> int:
        with atomic as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM backend_records WHERE namespace=?",
                (self.namespace,),
            ).fetchone()[0]


def preserve_backend_data(previous: Path, target: sqlite3.Connection) -> None:
    """Retain backend records when an offline OSM importer rebuilds the database."""
    if not previous.exists():
        return
    with closing(
        sqlite3.connect(previous.resolve().as_uri() + "?mode=ro", uri=True)
    ) as source:
        if source.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='backend_records'"
        ).fetchone():
            target.execute(SCHEMA)
            target.executemany(
                "INSERT INTO backend_records VALUES (?, ?, ?)",
                source.execute("SELECT * FROM backend_records"),
            )
        if source.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='place_web_data'"
        ).fetchone():
            target.execute(
                """CREATE TABLE IF NOT EXISTS place_web_data (
                    place_id TEXT PRIMARY KEY REFERENCES places(id),
                    source_url TEXT NOT NULL, retrieved_at TEXT NOT NULL,
                    title TEXT, description TEXT, telephone TEXT,
                    opening_hours TEXT, accessibility_summary TEXT
                )"""
            )
            target.executemany(
                "INSERT OR REPLACE INTO place_web_data VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                source.execute(
                    "SELECT w.* FROM place_web_data w JOIN places p ON p.id=w.place_id"
                ),
            )
