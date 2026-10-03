"""Small isolated OSM catalog for account integration checks."""

import sqlite3
from contextlib import closing
from pathlib import Path


def create_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(
            (Path(__file__).resolve().parents[1] / "scripts/schema.sql").read_text()
        )
        db.execute(
            "INSERT INTO metadata VALUES ('imported_at', '\"2026-10-03T12:00:00+00:00\"')"
        )
        db.execute("INSERT INTO categories VALUES ('museum', 'Muzea')")
        db.execute(
            "INSERT INTO osm_objects VALUES ('node/1', 'node', 1, 'https://www.openstreetmap.org/node/1', 'ODbL', NULL, NULL, '{}', '{}')"
        )
        db.execute(
            "INSERT INTO places (id, name, lat, lon) VALUES ('node/1', 'Muzeum integracyjne', 50.0614, 19.9366)"
        )
        db.execute("INSERT INTO place_categories VALUES ('node/1', 'museum')")
        for attribute, unit in [
            ("steps_count", "count"),
            ("threshold_height_cm", "cm"),
            ("elevator_available", None),
            ("entrance_width_cm", "cm"),
            ("accessible_toilet", None),
        ]:
            db.execute(
                "INSERT INTO accessibility_facts VALUES ('node/1', ?, NULL, ?, 'unconfirmed', 'missing', NULL, NULL)",
                (attribute, unit),
            )
