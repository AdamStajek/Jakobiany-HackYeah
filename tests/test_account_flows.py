"""Account persistence, private photo uploads and exactly-once mission rewards."""

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from account_fixture import create_database
from fastapi.testclient import TestClient
from PIL import Image

from hackyeah import auth, report_ai
from hackyeah import models as m
from hackyeah.main import app

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "integration-password"
CONSTRAINTS = {key: None for key in m.Constraints.model_fields}


class AccountFlowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "accounts.sqlite3"
        create_database(self.path)
        environment = patch.dict(os.environ, DATABASE_PATH=str(self.path))
        environment.start()
        self.addCleanup(environment.stop)
        inference = patch.object(
            report_ai,
            "extract_metric",
            side_effect=RuntimeError("test model unavailable"),
        )
        inference.start()
        self.addCleanup(inference.stop)
        logging = patch.object(report_ai.logger, "exception")
        logging.start()
        self.addCleanup(logging.stop)
        auth._attempts.clear()
        self.user = self.client()
        self.moderator = self.client()
        self.other = self.client()
        self.user_id = self.register(self.user, "user@example.com")
        self.register(self.moderator, "moderator@example.com")
        auth.set_moderator("moderator@example.com")
        self.login(self.moderator, "moderator@example.com")
        self.register(self.other, "other@example.com")

    def client(self):
        client = TestClient(app, base_url="https://testserver")
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        client.headers["Origin"] = "https://testserver"
        return client

    def register(self, client, email):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": PASSWORD,
                "display_name": email.split("@")[0],
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["roles"], ["user"])
        self.login(client, email)
        return response.json()["id"]

    def login(self, client, email):
        response = client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200, response.text)
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        return response.json()

    def image(self):
        data = BytesIO()
        exif = Image.Exif()
        exif[0x010E] = "Private metadata"
        Image.new("RGB", (8, 8), "red").save(data, "JPEG", exif=exif)
        return data.getvalue()

    def assert_persisted_in_new_process(self, assertions):
        response = subprocess.run(
            [sys.executable, "-c", assertions],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(response.returncode, 0, response.stderr)

    def test_profile_photo_report_bookmarks_and_session_persist(self):
        profile = self.user.post(
            "/api/v1/profiles",
            json={
                "name": "Saved",
                "description": "Bez schodów",
                "constraints": {
                    **CONSTRAINTS,
                    "max_steps": 0,
                    "require_step_free_access": True,
                },
            },
        )
        self.assertEqual(profile.status_code, 201, profile.text)
        profile_id = profile.json()["id"]
        self.assertEqual(
            self.other.get(f"/api/v1/profiles/{profile_id}").status_code, 404
        )
        changed = self.user.patch(
            f"/api/v1/profiles/{profile_id}", json={"name": "Updated"}
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        bookmarks = self.user.put("/api/v1/bookmarks", json=["node/1"])
        self.assertEqual(bookmarks.status_code, 200, bookmarks.text)
        self.assertEqual(self.other.get("/api/v1/bookmarks").json(), [])
        uploaded = self.user.post(
            "/api/v1/photos", files={"file": ("photo.jpg", self.image(), "image/jpeg")}
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        self.assertEqual(uploaded.json()["status"], "ready")
        photo_id = uploaded.json()["id"]
        picture = self.user.get(f"/api/v1/photos/{photo_id}/content")
        self.assertEqual(picture.status_code, 200)
        with Image.open(BytesIO(picture.content)) as sanitized:
            self.assertEqual(sanitized.format, "PNG")
            self.assertFalse(sanitized.getexif())
            self.assertNotIn(b"Private metadata", picture.content)
        self.assertEqual(
            self.other.get(f"/api/v1/photos/{photo_id}/content").status_code, 404
        )
        self.assertEqual(
            self.moderator.get(f"/api/v1/photos/{photo_id}/content").status_code, 200
        )
        report = self.user.post(
            "/api/v1/reports",
            json={
                "target": {"type": "place", "id": "node/1"},
                "kind": "missing_data",
                "description": "Sprawdzono wejście",
                "photo_ids": [photo_id],
                "observed_at": datetime.now(UTC).isoformat(),
            },
        )
        self.assertEqual(report.status_code, 201, report.text)
        report_id = report.json()["id"]
        self.assertEqual(
            self.user.delete(f"/api/v1/photos/{photo_id}").status_code, 409
        )
        self.assertEqual(
            self.other.post(
                "/api/v1/reports",
                json={
                    "target": {"type": "place", "id": "node/1"},
                    "kind": "missing_data",
                    "photo_ids": [photo_id],
                },
            ).status_code,
            404,
        )
        decision = self.moderator.post(
            f"/api/v1/reports/{report_id}/review",
            json={"decision": "accepted", "comment": "Sprawdzono zdjęcie"},
        )
        self.assertEqual(decision.status_code, 200, decision.text)
        token = self.user.cookies.get(auth.COOKIE_NAME)
        self.assert_persisted_in_new_process(f"""
from hackyeah import auth, profiles, photos, reports, models as m
from hackyeah.api import _bookmarks
session, expires = auth.sessions[{token!r}]
assert session.user.id == {self.user_id!r}
assert profiles.get(session.user.id, {profile_id!r}).name == "Updated"
assert _bookmarks[session.user.id] == ["node/1"]
assert reports.get(session.user, {report_id!r}).status == "accepted"
assert photos.content(session.user, {photo_id!r}).startswith(b"\\x89PNG")
""")
        self.assertEqual(self.user.post("/api/v1/auth/logout").status_code, 204)
        self.assertEqual(self.user.get("/api/v1/auth/session").status_code, 401)
        self.login(self.user, "user@example.com")
        self.assertEqual(
            self.user.get("/api/v1/profiles").json()["items"][0]["name"], "Updated"
        )
        self.assertEqual(
            self.user.get("/api/v1/reports?mine=true").json()["items"][0]["status"],
            "accepted",
        )

    def test_route_verification_accepts_osm_and_synthetic_gaps(self):
        for fact_id in (
            "osm/way/123/rest_area_available",
            "synthetic/bednarski-kika/rest_area_available",
        ):
            with self.subTest(fact_id=fact_id):
                body = {
                    "fact_id": fact_id,
                    "attribute": "rest_area_available",
                    "instruction": "Sprawdź miejsce odpoczynku na odcinku.",
                    "location": {"lat": 50.043, "lon": 19.95},
                }
                response = self.user.post(
                    "/api/v1/missions/route-verification-requests", json=body
                )
                self.assertEqual(response.status_code, 201, response.text)
                mission = response.json()
                self.assertEqual(mission["fact_id"], fact_id)
                self.assertEqual(mission["target_type"], "segment")
                self.assertEqual(mission["priority"], 1)
                repeated = self.user.post(
                    "/api/v1/missions/route-verification-requests", json=body
                )
                self.assertEqual(repeated.json()["id"], mission["id"])
        for fact_id in ("unknown/rest_area_available", "synthetic/demo/surface"):
            body["fact_id"] = fact_id
            response = self.user.post(
                "/api/v1/missions/route-verification-requests", json=body
            )
            self.assertEqual(response.status_code, 422, response.text)

    def test_automatic_mission_priorities_refresh_and_guest_access(self):
        import sqlite3
        from contextlib import closing

        initial = self.user.get("/api/v1/missions").json()
        self.assertTrue(initial)
        self.assertTrue(all(item["priority"] == 2 for item in initial))
        selected = initial[-1]
        response = self.user.post(
            "/api/v1/missions/verification-requests",
            json={
                "place_id": selected["place_id"],
                "fact_ids": [selected["fact_id"]],
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()[0]["priority"], 1)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "UPDATE accessibility_facts SET value_json='1', unconfirmed_reason='conflicting' WHERE attribute='steps_count'"
            )
            for number in range(2, 16):
                place_id = f"node/{number}"
                db.execute(
                    "INSERT INTO places (id, name, lat, lon) VALUES (?, ?, 50.0614, 19.9366)",
                    (place_id, f"Miejsce {number}"),
                )
                db.execute(
                    "INSERT INTO accessibility_facts VALUES (?, 'steps_count', NULL, 'count', 'unconfirmed', 'missing', NULL, NULL)",
                    (place_id,),
                )
        refreshed = self.user.get("/api/v1/missions").json()
        self.assertEqual(refreshed[0]["id"], selected["id"])
        priorities = [item["priority"] for item in refreshed]
        self.assertEqual(priorities, sorted(priorities))
        self.assertIn(3, priorities)
        self.assertTrue(any(item["place_id"] == "node/15" for item in refreshed))
        self.assertTrue(
            all(item["location"] and item["description"] for item in refreshed)
        )
        nearby = self.user.get("/api/v1/missions?lat=50.0614&lon=19.9366").json()
        self.assertTrue(any(item["place_id"] == "node/15" for item in nearby))
        far = self.user.get("/api/v1/missions?lat=52&lon=21").json()
        self.assertTrue(all(item["priority"] == 1 for item in far))
        self.assertEqual(self.user.get("/api/v1/missions?lat=50").status_code, 422)
        self.assertEqual(self.user.get("/api/v1/missions?offset=-1").status_code, 422)
        guest = self.client()
        for endpoint in ("start", "submit"):
            response = guest.post(
                f"/api/v1/missions/{selected['id']}/{endpoint}",
                json={
                    "description": "Sprawdzono wejście do obiektu.",
                    "photo_ids": ["guest-photo"],
                },
            )
            self.assertEqual(response.status_code, 401)
        self.assertEqual(guest.get("/api/v1/missions/progress").status_code, 401)

    def test_mission_review_awards_once_and_cannot_be_bypassed(self):
        mission = self.user.get("/api/v1/missions").json()[0]
        mission_id = mission["id"]
        start = self.user.post(f"/api/v1/missions/{mission_id}/start")
        self.assertEqual(start.status_code, 200, start.text)
        self.assertEqual(
            self.user.post(f"/api/v1/missions/{mission_id}/start").json()["id"],
            start.json()["id"],
        )
        photo_id = self.user.post(
            "/api/v1/photos", files={"file": ("mission.png", self.image(), "image/png")}
        ).json()["id"]
        self.assertEqual(
            self.user.post(
                f"/api/v1/missions/{mission_id}/submit",
                json={"description": "Odpowiedź bez zdjęcia"},
            ).status_code,
            422,
        )
        submitted = self.user.post(
            f"/api/v1/missions/{mission_id}/submit",
            json={
                "description": "Wejście ma szerokość 95 centymetrów.",
                "photo_ids": [photo_id],
            },
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        progress_id = submitted.json()["id"]
        report_id = submitted.json()["report_id"]
        self.assertEqual(self.user.get("/api/v1/missions/progress").json()["points"], 0)
        self.assertEqual(
            self.user.post(
                f"/api/v1/missions/{mission_id}/submit",
                json={
                    "description": "Ponownie wysłana odpowiedź",
                    "photo_ids": [photo_id],
                },
            ).status_code,
            409,
        )
        review_body = {"decision": "accepted", "comment": "Potwierdzono pomiar"}
        self.assertEqual(
            self.user.post(
                f"/api/v1/missions/progress/{progress_id}/review", json=review_body
            ).status_code,
            403,
        )
        auth.set_moderator("user@example.com")
        self.login(self.user, "user@example.com")
        self.assertEqual(
            self.user.post(
                f"/api/v1/reports/{report_id}/review", json=review_body
            ).status_code,
            403,
        )
        accepted = self.moderator.post(
            f"/api/v1/missions/progress/{progress_id}/review", json=review_body
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["awarded_points"], mission["points"])
        self.assertEqual(
            self.moderator.post(
                f"/api/v1/missions/progress/{progress_id}/review", json=review_body
            ).status_code,
            200,
        )
        self.assertEqual(
            self.moderator.post(
                f"/api/v1/reports/{report_id}/review", json=review_body
            ).status_code,
            200,
        )
        self.assertEqual(
            self.user.get("/api/v1/missions/progress").json()["points"],
            mission["points"],
        )
        self.assertEqual(
            self.user.patch(
                f"/api/v1/reports/{report_id}",
                json={
                    "description": "Próba ponownego naliczenia",
                    "photo_ids": [photo_id],
                },
            ).status_code,
            409,
        )
        self.assertEqual(
            self.user.post(
                f"/api/v1/missions/{mission_id}/submit",
                json={
                    "description": "Próba ponownego naliczenia",
                    "photo_ids": [photo_id],
                },
            ).status_code,
            409,
        )
        self.assert_persisted_in_new_process(f"""
from hackyeah import missions, models as m
user = m.User(id={self.user_id!r}, display_name="User", roles=["user"])
activity = missions.activity(user)
assert activity.points == {mission["points"]}
assert activity.items[0].status == "accepted"
""")

    def test_rejection_resubmission_csrf_and_invalid_images(self):
        mission_id = self.user.get("/api/v1/missions").json()[0]["id"]
        self.assertEqual(
            self.user.post(
                f"/api/v1/missions/{mission_id}/start",
                headers={"X-CSRF-Token": "wrong"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.user.post(
                f"/api/v1/missions/{mission_id}/start",
                headers={"Origin": "https://untrusted.example"},
            ).status_code,
            403,
        )
        self.user.post(f"/api/v1/missions/{mission_id}/start")
        photo_id = self.user.post(
            "/api/v1/photos", files={"file": ("mission.png", self.image(), "image/png")}
        ).json()["id"]
        first = self.user.post(
            f"/api/v1/missions/{mission_id}/submit",
            json={
                "description": "Niedostateczne informacje o wejściu",
                "photo_ids": [photo_id],
            },
        ).json()
        rejected = self.moderator.post(
            f"/api/v1/missions/progress/{first['id']}/review",
            json={"decision": "rejected", "comment": "Dodaj pomiar szerokości"},
        )
        self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertEqual(rejected.json()["awarded_points"], 0)
        second = self.user.post(
            f"/api/v1/missions/{mission_id}/submit",
            json={"description": "Szerokość zmierzono: 95 cm", "photo_ids": [photo_id]},
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertNotEqual(second.json()["report_id"], first["report_id"])
        self.assertEqual(
            self.moderator.post(
                f"/api/v1/reports/{first['report_id']}/review",
                json={"decision": "accepted", "comment": "Stare zgłoszenie"},
            ).status_code,
            409,
        )
        invalid = self.user.post(
            "/api/v1/photos",
            files={"file": ("invalid.png", b"not an image", "image/png")},
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)
        bad_password = self.user.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "wrong-password"},
        )
        self.assertEqual(bad_password.status_code, 401)
        self.assertEqual(bad_password.json()["error"]["code"], "INVALID_CREDENTIALS")
        forbidden_role = self.user.post(
            "/api/v1/auth/register",
            json={
                "email": "intruder@example.com",
                "password": PASSWORD,
                "display_name": "Intruder",
                "roles": ["moderator"],
            },
        )
        self.assertEqual(forbidden_role.status_code, 422)


if __name__ == "__main__":
    unittest.main()
