"""Uploads respond before AI; pending evidence stays private and survives restart."""

import os
import tempfile
import time
import unittest
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from threading import Event
from unittest.mock import patch

from account_fixture import create_database
from fastapi.testclient import TestClient
from PIL import Image

from hackyeah import auth, missions, photo_worker, photos, report_ai, reports
from hackyeah.main import app


def hanging_analyzer(connection):
    connection.recv()
    time.sleep(30)


class BackgroundPhotoTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        db = Path(self.folder.name) / "app.sqlite3"
        create_database(db)
        env = patch.dict(os.environ, DATABASE_PATH=str(db))
        env.start()
        self.addCleanup(env.stop)
        self.client = TestClient(app, base_url="https://testserver")
        self.addCleanup(self.client.close)
        self.client.headers["Origin"] = "https://testserver"
        auth._attempts.clear()
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "background@example.com",
                "password": "test-password-long",
                "display_name": "Test",
            },
        ).raise_for_status()
        session = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "background@example.com",
                "password": "test-password-long",
            },
        ).json()
        self.client.headers["X-CSRF-Token"] = session["csrf_token"]
        output = BytesIO()
        Image.new("RGB", (32, 32), "red").save(output, format="PNG")
        self.image = output.getvalue()

    def upload_and_submit(self):
        mission = next(
            item
            for item in self.client.get("/api/v1/missions").json()
            if item["attribute"] == "steps_count"
        )
        self.client.post(f"/api/v1/missions/{mission['id']}/start").raise_for_status()
        uploaded = self.client.post(
            "/api/v1/photos", files={"file": ("photo.png", self.image, "image/png")}
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        self.assertEqual(uploaded.json()["status"], "processing")
        photo_id = uploaded.json()["id"]
        self.assertEqual(
            self.client.get(f"/api/v1/photos/{photo_id}/content").status_code, 409
        )
        self.assertIsNone(
            self.client.get(f"/api/v1/photos/{photo_id}").json()["preview_url"]
        )
        response = self.client.post(
            f"/api/v1/missions/{mission['id']}/submit",
            json={
                "photo_ids": [photo_id],
                "observations": [{"attribute": "steps_count", "value": 3}],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "pending")
        self.assertEqual(response.json()["awarded_points"], 0)
        return photo_id, response.json()["report_id"], mission

    def test_demo_mission_acceptance_after_five_seconds_awards_once(self):
        _, report_id, mission = self.upload_and_submit()
        created = reports._reports[report_id].created_at
        with patch("hackyeah.reports.datetime") as clock:
            clock.now.return_value = created + timedelta(seconds=4.99)
            reports.accept_due_missions()
            self.assertEqual(reports._reports[report_id].status, "pending")
            self.assertEqual(
                self.client.get("/api/v1/missions/progress").json()["points"], 0
            )
            clock.now.return_value = created + timedelta(seconds=5)
            reports.accept_due_missions()
            reports.accept_due_missions()
        report = self.client.get(f"/api/v1/reports/{report_id}").json()
        self.assertEqual(report["status"], "accepted")
        self.assertEqual(report["ai_status"], "not_requested")
        activity = self.client.get("/api/v1/missions/progress").json()
        self.assertEqual(activity["points"], mission["points"])
        self.assertEqual(activity["items"][0]["status"], "accepted")

    def test_response_before_ai_and_durable_completion_with_rewards_once(self):
        with (
            patch("hackyeah.photos.anonymize") as privacy,
            patch.object(report_ai, "extract_metric") as infer,
        ):
            photo_id, report_id, mission = self.upload_and_submit()
            privacy.assert_not_called()
            infer.assert_not_called()
        # No in-memory task is needed: a fresh worker discovers persisted pending records.
        with (
            patch("hackyeah.photos.anonymize", side_effect=lambda image: image.copy()),
            patch.object(report_ai, "describe_photo", return_value=("Schody", False)),
            patch.object(
                report_ai, "extract_metric", return_value='{"steps_count": 3}'
            ),
        ):
            photo_worker.process_once()
            photo_worker.process_once()
        self.assertEqual(
            self.client.get(f"/api/v1/photos/{photo_id}/content").status_code, 200
        )
        report = self.client.get(f"/api/v1/reports/{report_id}").json()
        self.assertEqual(report["ai_status"], "completed")
        self.assertEqual(report["status"], "accepted")
        progress = self.client.get("/api/v1/missions/progress").json()
        self.assertEqual(progress["points"], mission["points"])
        self.assertFalse(photos._pending_path(photo_id).exists())

    def test_privacy_failure_never_exposes_original_and_marks_analysis_failed(self):
        photo_id, report_id, _ = self.upload_and_submit()
        with (
            patch("hackyeah.photos.anonymize", side_effect=RuntimeError("offline")),
            self.assertLogs(photos.logger, level="ERROR"),
        ):
            photo_worker.process_once()
        self.assertEqual(
            self.client.get(f"/api/v1/photos/{photo_id}").json()["status"], "rejected"
        )
        self.assertEqual(
            self.client.get(f"/api/v1/photos/{photo_id}/content").status_code, 409
        )
        self.assertEqual(
            self.client.get(f"/api/v1/reports/{report_id}").json()["ai_status"],
            "failed",
        )
        self.assertFalse(photos._pending_path(photo_id).exists())
        self.assertFalse(photos._file_path(photo_id).exists())

    def test_hung_process_is_killed_and_failure_status_reaches_mission(self):
        photo_id, report_id, _ = self.upload_and_submit()
        analyzer = photo_worker.Analyzer(Event(), timeout=0.3)
        self.addCleanup(analyzer.close)
        started = time.monotonic()
        with patch.object(photo_worker, "_child", hanging_analyzer):
            photo_worker.process_once(analyzer.run)
        self.assertLess(time.monotonic() - started, 5)
        self.assertIsNone(analyzer.process)
        self.assertEqual(photos._photos[photo_id][1].status, "rejected")
        self.assertEqual(reports._reports[report_id].ai_status, "failed")
        progress = self.client.get("/api/v1/missions/progress").json()["items"][0]
        self.assertEqual(progress["ai_status"], "failed")
        self.assertEqual(progress["awarded_points"], 0)
        self.assertFalse(photos._pending_path(photo_id).exists())
        # Older progress records lacked ai_status; read the report and allow retry.
        stored = missions._progress[progress["id"]]
        stored.ai_status = "not_requested"
        missions._progress[stored.id] = stored
        self.assertEqual(
            self.client.get("/api/v1/missions/progress").json()["items"][0][
                "ai_status"
            ],
            "failed",
        )
        new_photo = self.client.post(
            "/api/v1/photos", files={"file": ("retry.png", self.image, "image/png")}
        ).json()["id"]
        retry = self.client.post(
            f"/api/v1/missions/{progress['mission_id']}/submit",
            json={"photo_ids": [new_photo]},
        )
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(retry.json()["ai_status"], "pending")

    def test_bad_description_does_not_block_metric_verification(self):
        _, report_id, _ = self.upload_and_submit()
        with (
            patch("hackyeah.photos.anonymize", side_effect=lambda image: image.copy()),
            patch.object(
                report_ai,
                "describe_photo",
                side_effect=ValueError("invalid description"),
            ),
            patch.object(
                report_ai, "extract_metric", return_value='{"steps_count": 3}'
            ),
            self.assertLogs(photos.logger, level="ERROR"),
        ):
            photo_worker.process_once()
        self.assertEqual(reports._reports[report_id].status, "accepted")

    def test_stale_analysis_cannot_overwrite_an_edit(self):
        _, report_id, _ = self.upload_and_submit()
        photo_id = reports._reports[report_id].photo_ids[0]
        with (
            patch("hackyeah.photos.anonymize", side_effect=lambda image: image.copy()),
            patch.object(report_ai, "describe_photo", return_value=("Schody", False)),
        ):
            photos.process(photo_id)

        def change_report(report, *args):
            updated = reports._reports[report_id]
            updated.description = "New revision"
            reports._reports[report_id] = updated
            report.status = "accepted"
            report.ai_status = "completed"

        with patch.object(report_ai, "verify", side_effect=change_report):
            reports.process(report_id)
        self.assertEqual(reports._reports[report_id].description, "New revision")
        self.assertEqual(reports._reports[report_id].ai_status, "pending")


if __name__ == "__main__":
    unittest.main()
