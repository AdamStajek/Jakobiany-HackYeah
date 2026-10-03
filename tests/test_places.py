import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from hackyeah import places
from hackyeah.main import app
from hackyeah.models import Constraints


class PlaceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "places.sqlite3"
        with sqlite3.connect(path) as db:
            db.executescript(
                (Path(__file__).resolve().parents[1] / "scripts/schema.sql").read_text()
            )
            db.execute(
                "INSERT INTO metadata VALUES ('imported_at', '\"2026-10-03T12:00:00+00:00\"')"
            )
            db.execute("INSERT INTO categories VALUES ('museum', 'Muzea')")
            for number in (1, 2, 3):
                place_id = f"node/{number}"
                db.execute(
                    "INSERT INTO osm_objects VALUES (?, 'node', ?, ?, 'ODbL', NULL, NULL, '{}', '{}')",
                    (place_id, number, f"https://www.openstreetmap.org/{place_id}"),
                )
                db.execute(
                    "INSERT INTO places (id, name, lat, lon) VALUES (?, ?, 50, 19)",
                    (place_id, f"Muzeum {number}"),
                )
                db.execute(
                    "INSERT INTO place_categories VALUES (?, 'museum')", (place_id,)
                )
                for attribute, unit in [
                    ("steps_count", "count"),
                    ("threshold_height_cm", "cm"),
                    ("elevator_available", None),
                    ("entrance_width_cm", "cm"),
                    ("accessible_toilet", None),
                ]:
                    db.execute(
                        "INSERT INTO accessibility_facts VALUES (?, ?, NULL, ?, 'unconfirmed', 'missing', NULL, NULL)",
                        (place_id, attribute, unit),
                    )
        env = patch.dict(os.environ, DATABASE_PATH=str(path))
        env.start()
        self.addCleanup(env.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_search_details_pagination_and_filters(self):
        result = self.client.post(
            "/api/v1/places/search", json={"query": "MUZEUM", "limit": 2}
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["next_cursor"], "node/2")
        self.assertEqual(len(result.json()["items"]), 2)
        second = self.client.post(
            "/api/v1/places/search", json={"query": "Muzeum", "cursor": "node/2"}
        ).json()
        self.assertEqual([p["id"] for p in second["items"]], ["node/3"])
        detail = self.client.get("/api/v1/places/node/1")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(len(detail.json()["facts"]), 5)
        self.assertEqual(detail.json()["assessment"]["status"], "uncertain")
        self.assertEqual(self.client.get("/api/v1/places/node/99").status_code, 404)
        self.assertEqual(
            self.client.get("/api/v1/places/node/1?profile_id=private").status_code, 401
        )
        for extra in (
            {"include_uncertain": False},
            {"near": {"lat": 51, "lon": 19}},
            {"query": "absent"},
        ):
            self.assertEqual(
                self.client.post(
                    "/api/v1/places/search", json={"query": "Muzeum", **extra}
                ).json()["items"],
                [],
            )

    def test_confirmed_failure_and_unknown_assessment(self):
        constraints = Constraints.model_validate(
            dict(
                max_steps=0,
                max_threshold_cm=None,
                max_slope_percent=None,
                min_entrance_width_cm=None,
                max_distance_without_rest_m=None,
                require_step_free_access=True,
                require_accessible_toilet=None,
                allowed_surfaces=None,
            )
        )
        fact = places.get("node/1").facts[0]
        fact.attribute = "steps_count"
        fact.value = 2
        fact.status = "confirmed"
        self.assertEqual(
            places.assess([fact], constraints).status, "does_not_meet_requirements"
        )
        fact.value = 0
        self.assertEqual(
            places.assess([fact], constraints).status, "meets_requirements"
        )
        fact.status = "unconfirmed"
        self.assertEqual(places.assess([fact], constraints).status, "uncertain")
