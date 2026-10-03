"""Persistence, isolation and rollback checks against an existing SQLite schema."""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from hackyeah import auth, database, owner
from hackyeah import models as m
from hackyeah.main import app

ROOT = Path(__file__).resolve().parents[1]


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "existing.sqlite3"
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.executescript((ROOT / "scripts/schema.sql").read_text())
            connection.execute(
                "INSERT INTO metadata VALUES ('sentinel', '\"unchanged\"')"
            )
        environment = patch.dict(os.environ, {"DATABASE_PATH": str(self.path)})
        environment.start()
        self.addCleanup(environment.stop)
        auth._attempts.clear()
        self.client = TestClient(app, base_url="https://testserver")
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def login(self):
        body = {
            "email": "user@example.com",
            "password": "long-password",
            "display_name": "User",
        }
        registered = self.client.post("/api/v1/auth/register", json=body)
        self.assertEqual(registered.status_code, 201, registered.text)
        response = self.client.post(
            "/api/v1/auth/login", json={key: body[key] for key in ("email", "password")}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        return m.User.model_validate(registered.json())

    def test_api_records_and_session_survive_new_process(self):
        user = self.login()
        csrf = self.client.headers["X-CSRF-Token"]
        token = self.client.cookies.get(auth.COOKIE_NAME)
        user.roles.extend(["owner", "moderator"])
        with database.atomic:
            session, expires = auth.sessions[token]
            session.user = user
            auth.sessions[token] = (session, expires)
        constraints = {key: None for key in m.Constraints.model_fields}
        constraints["max_steps"] = 0
        profile = self.client.post(
            "/api/v1/profiles",
            json={"name": "Saved", "description": "", "constraints": constraints},
        )
        self.assertEqual(profile.status_code, 201, profile.text)
        report = self.client.post(
            "/api/v1/reports",
            json={
                "target": {"type": "place", "id": "rynek"},
                "kind": "missing_data",
                "description": "Evidence",
            },
        )
        self.assertEqual(report.status_code, 201, report.text)
        review = self.client.post(
            f"/api/v1/reports/{report.json()['id']}/review",
            json={"decision": "accepted", "comment": "Checked"},
        )
        self.assertEqual(review.status_code, 200, review.text)
        png_header = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (1).to_bytes(4) * 2 + bytes(9)
        )
        photo = self.client.post(
            "/api/v1/photos", files={"file": ("image.png", png_header, "image/png")}
        )
        self.assertEqual(photo.status_code, 201, photo.text)
        place = m.PlaceSummary(
            id="rynek",
            name="Rynek",
            category="historic",
            address=None,
            location=m.Coordinates(lat=50.0617, lon=19.9373),
            distance_m=None,
            assessment=m.Assessment(status="uncertain", summary="Unknown", reasons=[]),
        )
        owner.assign_place(user.id, place)
        declaration = self.client.put(
            "/api/v1/owner/places/rynek/declaration",
            json={
                "observations": [{"attribute": "steps_count", "value": 0}],
                "observed_at": datetime.now(UTC).isoformat(),
            },
        )
        self.assertEqual(declaration.status_code, 200, declaration.text)
        with patch("hackyeah.api.get_weather", side_effect=ValueError):
            route = self.client.post(
                "/api/v1/routes/plan",
                json={
                    "origin": {"place_id": "rynek"},
                    "destination": {"place_id": "wawel"},
                    "profile_id": profile.json()["id"],
                },
            )
        self.assertEqual(route.status_code, 200, route.text)
        self.assertTrue(route.json()["routes"])
        payload = {
            "token": token,
            "csrf": csrf,
            "profile": profile.json()["id"],
            "report": report.json()["id"],
            "photo": photo.json()["id"],
            "user": user.model_dump(),
        }
        script = """
import json, sys
from fastapi.testclient import TestClient
from hackyeah.main import app
from hackyeah import auth, models as m, owner, photos, reports
args = json.loads(sys.argv[1])
with TestClient(app, base_url="https://testserver") as client:
    client.cookies.set(auth.COOKIE_NAME, args["token"])
    client.headers["X-CSRF-Token"] = args["csrf"]
    assert client.get("/api/v1/auth/session").status_code == 200
    assert client.get("/api/v1/profiles/" + args["profile"]).json()["name"] == "Saved"
    assert client.get("/api/v1/reports/" + args["report"]).json()["status"] == "accepted"
    assert client.get("/api/v1/photos/" + args["photo"]).json()["status"] == "rejected"
    assert client.get("/api/v1/owner/places").json()["items"][0]["id"] == "rynek"
    assert owner._declarations["rynek"].observations[0].value == 0
    assert len(owner._history["rynek"]) == 1
    assert len(reports._history[args["report"]]) == 1
    assert photos._files[args["photo"]].startswith(b"\\x89PNG")
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/session").status_code == 401
"""
        result = subprocess.run(
            [sys.executable, "-c", script, json.dumps(payload)],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.client.get("/api/v1/auth/session").status_code, 401)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertEqual(
                connection.execute(
                    "SELECT value_json FROM metadata WHERE key='sentinel'"
                ).fetchone()[0],
                '"unchanged"',
            )
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
            )

    def test_rollback_and_missing_lookup_inside_transaction(self):
        records = database.Store[str, list[str]]("test")
        with self.assertRaises(RuntimeError), database.atomic:
            records["new"] = ["value"]
            raise RuntimeError("cancel")
        self.assertNotIn("new", records)
        with database.atomic:
            self.assertIsNone(records.get("missing"))
            records["kept"] = ["value"]
        self.assertEqual(records["kept"], ["value"])
        self.login()
        self.assertEqual(
            self.client.post(
                "/api/v1/profiles",
                json={
                    "name": "X",
                    "description": "",
                    "constraints": {key: None for key in m.Constraints.model_fields},
                },
                headers={"X-CSRF-Token": "wrong"},
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/v1/profiles").json()["items"], [])

    def test_rebuild_preserves_backend_records(self):
        records = database.Store[str, bytes]("test.files", binary=True)
        records["image"] = bytes(range(256))
        rebuilt = self.path.with_name("rebuilt.sqlite3")
        with closing(sqlite3.connect(rebuilt)) as target, target:
            target.executescript((ROOT / "scripts/schema.sql").read_text())
            database.preserve_backend_data(self.path, target)
        with patch.dict(os.environ, {"DATABASE_PATH": str(rebuilt)}):
            self.assertEqual(records["image"], bytes(range(256)))


if __name__ == "__main__":
    unittest.main()
