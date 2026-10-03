import sqlite3
import unittest
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from test_osm_import import make_fixture
from test_temporary_data import KML, NOW, forecast

from hackyeah import models as m
from hackyeah.temporary_data import parse_construction, parse_weather
from hackyeah.temporary_store import import_snapshots
from scripts.build_places_db import build_database
from scripts.update_database import update_database


class TemporaryStoreTests(unittest.TestCase):
    def test_idempotence_rollback_weather_rejection_and_osm_preservation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, boundary = make_fixture(root)
            database = root / "places.sqlite3"
            build_database(source, boundary, database)
            snapshot = parse_construction(KML, NOW)
            for _ in range(2):
                self.assertEqual(
                    import_snapshots(database, [snapshot])["temporary_difficulties"], 2
                )
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(
                    db.execute("SELECT count(*) FROM places").fetchone()[0], 4
                )
                prior = db.execute(
                    "SELECT * FROM temporary_difficulties ORDER BY id"
                ).fetchall()
            weather = parse_weather(forecast(), NOW, "https://api.open-meteo.com/test")
            with self.assertRaises(ValueError):
                import_snapshots(database, [weather])
            duplicate = snapshot.model_copy(
                update={"items": [snapshot.items[0], snapshot.items[0]]}
            )
            with self.assertRaises(sqlite3.IntegrityError):
                import_snapshots(database, [duplicate])
            older = snapshot.model_copy(
                update={"generated_at": NOW - timedelta(hours=1)}
            )
            with self.assertRaises(ValueError):
                import_snapshots(database, [older])
            build_database(source, boundary, database)
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(
                    db.execute(
                        "SELECT * FROM temporary_difficulties ORDER BY id"
                    ).fetchall(),
                    prior,
                )
                self.assertEqual(
                    db.execute("SELECT count(*) FROM places").fetchone()[0], 4
                )
                self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertIsNone(
                    db.execute(
                        "SELECT name FROM sqlite_master WHERE name='weather_hours'"
                    ).fetchone()
                )

    def test_missing_only_preserves_existing_rows_and_skips_heavy_jobs(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, boundary = make_fixture(root)
            database = root / "places.sqlite3"
            build_database(source, boundary, database)
            snapshot = parse_construction(KML, NOW)
            partial = snapshot.model_copy(update={"items": [snapshot.items[0]]})
            import_snapshots(database, [partial])
            with closing(sqlite3.connect(database)) as db:
                original = db.execute(
                    "SELECT data_json FROM temporary_difficulties WHERE id=?",
                    (snapshot.items[0].id,),
                ).fetchone()[0]
            snapshot.items[0].description = "Changed upstream; must not overwrite"
            for _ in range(2):
                import_snapshots(database, [snapshot], missing_only=True)
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) FROM temporary_difficulties"
                    ).fetchone()[0],
                    2,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT data_json FROM temporary_difficulties WHERE id=?",
                        (snapshot.items[0].id,),
                    ).fetchone()[0],
                    original,
                )
            (root / "data/temporary").mkdir(parents=True)
            (root / "data/temporary/construction.json").write_text(
                snapshot.model_dump_json()
            )
            with (
                patch("scripts.update_database.ROOT", root),
                patch("scripts.update_database.run_script") as run,
            ):
                update_database(database, missing_only=True)
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], "scripts.import_temporary_data")
            self.assertIn("--missing-only", run.call_args.args)

    def test_orchestrator_failure_keeps_existing_database(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "places.sqlite3"
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("CREATE TABLE marker (value TEXT)")
                db.execute("INSERT INTO marker VALUES ('original')")
            original = database.read_bytes()
            with patch(
                "scripts.update_database.run_script",
                side_effect=RuntimeError("fetch failed"),
            ):
                with self.assertRaises(RuntimeError):
                    update_database(database)
            self.assertEqual(database.read_bytes(), original)

    def test_live_weather_on_each_route_request(self):
        from fastapi.testclient import TestClient

        from hackyeah.main import app

        now = datetime.now(UTC)
        snapshot = m.TemporaryDataSnapshot(
            source="weather",
            generated_at=now,
            valid_until=now + timedelta(hours=3),
            items=[],
            weather_hours=[],
            attribution=[],
            warnings=[],
        )
        with (
            patch("hackyeah.api.get_weather", return_value=snapshot) as fetch,
            TestClient(app) as client,
        ):
            for _ in range(2):
                response = client.post(
                    "/api/v1/routes/plan",
                    json={
                        "origin": {"place_id": "rynek"},
                        "destination": {"place_id": "wawel"},
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["weather"]["source"], "weather")
            self.assertEqual(fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
