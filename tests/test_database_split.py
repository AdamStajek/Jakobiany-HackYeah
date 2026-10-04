import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hackyeah import database


class SplitDatabaseTests(unittest.TestCase):
    def test_migration_readonly_osm_and_independent_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            osm = Path(folder) / "osm.sqlite3"
            app = Path(folder) / "application.sqlite3"
            with sqlite3.connect(osm) as db:
                db.executescript(Path("scripts/schema.sql").read_text())
                db.execute(database.SCHEMA)
                db.execute(
                    "INSERT INTO backend_records VALUES ('test', '\"old\"', '1')"
                )
            with patch.dict(
                os.environ, DATABASE_PATH=str(app), OSM_DATABASE_PATH=str(osm)
            ):
                database.initialize()
                database.initialize()
                store = database.Store("test")
                self.assertEqual(store["old"], 1)
                store["new"] = 2
                with database.atomic as db:
                    with self.assertRaises(sqlite3.OperationalError):
                        db.execute("DELETE FROM osm.places")
                with database.connect(readonly=True) as db:
                    self.assertEqual(
                        db.execute("SELECT count(*) FROM places").fetchone()[0], 0
                    )
            with sqlite3.connect(app) as db:
                self.assertIsNone(
                    db.execute(
                        "SELECT name FROM sqlite_master WHERE name='osm_objects'"
                    ).fetchone()
                )
                self.assertEqual(
                    db.execute("SELECT count(*) FROM backend_records").fetchone()[0], 2
                )
            with sqlite3.connect(osm) as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM backend_records").fetchone()[0], 1
                )
