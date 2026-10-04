"""Photo decisions, persistence, edits and mission rewards without model download."""

import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from account_fixture import create_database
from PIL import Image

from hackyeah import missions, photos, report_ai, reports
from hackyeah import models as m


class ReportAITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        db = Path(self.directory.name) / "test.sqlite3"
        create_database(db)
        self.env = patch.dict(os.environ, {"DATABASE_PATH": str(db)})
        self.env.start()
        self.user = m.User(id="user_test", display_name="Test", roles=[])
        output = BytesIO()
        Image.new("RGB", (32, 32)).save(output, format="PNG")
        with (
            patch("hackyeah.photo_privacy.detect_regions", return_value=[]),
            patch.object(report_ai, "describe_photo", return_value=("Schody", False)),
        ):
            self.photo = photos.create(self.user.id, output.getvalue()).id
        self.body = m.ReportCreate(
            target=m.ReportTarget(type="place", id="node/1"),
            kind="missing_data",
            observations=[m.Observation(attribute="steps_count", value=3)],
            photo_ids=[self.photo],
        )

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_decisions_and_persistence(self):
        for raw, status, value in [
            ('{"attribute":"steps_count","value":3}', "accepted", 3),
            ('{"steps_count":3}', "accepted", 3),
            ('{"attribute":"steps_count","value":2}', "rejected", 2),
            ('{"attribute":"steps_count","value":null}', "rejected", None),
            ('{"attribute":"steps_count","value":true}', "rejected", None),
            ('{"attribute":"surface","value":"paved"}', "rejected", None),
            ("not json", "rejected", None),
        ]:
            with (
                self.subTest(raw=raw),
                patch.object(report_ai, "extract_metric", return_value=raw) as infer,
            ):
                report = reports.create(self.user, self.body)
                self.assertEqual(report.status, status)
                self.assertEqual(report.ai_status, "completed")
                self.assertEqual(report.ai_proposals[0].value, value)
                self.assertEqual(reports.get(self.user, report.id), report)
                self.assertEqual(
                    report.id in reports._accepted_observations, status == "accepted"
                )
                self.assertEqual(
                    infer.call_args.args[0], [photos.content(self.user, self.photo)]
                )

    def test_all_metrics_must_match_and_prompt_omits_claim(self):
        body = self.body.model_copy(
            update={
                "observations": [
                    m.Observation(attribute="steps_count", value=98765),
                    m.Observation(attribute="ramp_available", value=True),
                ]
            }
        )
        with patch.object(
            report_ai,
            "extract_metric",
            side_effect=[
                '{"attribute":"steps_count","value":98765}',
                '{"attribute":"ramp_available","value":false}',
            ],
        ) as infer:
            report = reports.create(self.user, body)
        self.assertEqual(report.status, "rejected")
        self.assertNotIn("98765", infer.call_args_list[0].args[1])

    def test_failure_and_missing_evidence_stay_pending(self):
        with patch.object(
            report_ai, "extract_metric", side_effect=RuntimeError("offline")
        ):
            with self.assertLogs(report_ai.logger, level="ERROR"):
                report = reports.create(self.user, self.body)
        self.assertEqual((report.status, report.ai_status), ("pending", "failed"))
        for field in ("photo_ids", "observations"):
            with patch.object(report_ai, "extract_metric") as infer:
                report = reports.create(
                    self.user, self.body.model_copy(update={field: []})
                )
            infer.assert_not_called()
            self.assertEqual(
                (report.status, report.ai_status), ("pending", "not_requested")
            )

    def test_edit_reverifies_and_removes_accepted_values(self):
        with patch.object(
            report_ai,
            "extract_metric",
            return_value='{"attribute":"steps_count","value":3}',
        ):
            report = reports.create(self.user, self.body)
            updated = reports.update(
                self.user,
                report.id,
                m.ReportPatch(
                    observations=[m.Observation(attribute="steps_count", value=4)]
                ),
            )
        self.assertEqual(updated.status, "rejected")
        self.assertNotIn(report.id, reports._accepted_observations)
        self.assertEqual(updated.created_at, report.created_at)

    def test_photo_ownership_checked_before_model(self):
        other = m.User(id="user_other", display_name="Other", roles=["moderator"])
        with patch.object(report_ai, "extract_metric") as infer:
            with self.assertRaises(Exception) as caught:
                reports.create(other, self.body)
        self.assertEqual(caught.exception.status_code, 404)
        infer.assert_not_called()

    def test_mission_photo_required_and_inferred_without_claim(self):
        from pydantic import ValidationError

        for payload in ({}, {"photo_ids": []}):
            with self.assertRaises(ValidationError):
                m.MissionSubmit(description="Sprawdzono miejsce w terenie", **payload)
        for index, (raw, status) in enumerate(
            [
                ('{"steps_count":3}', "accepted"),
                ('{"steps_count":null}', "rejected"),
                ("invalid", "rejected"),
                (None, "pending"),
            ]
        ):
            mission = m.Mission(
                id=f"mission_photo_{index}",
                place_id="node/1",
                place_name="Test",
                title="Policz stopnie",
                fact_id="node/1:steps_count",
                attribute="steps_count",
                points=30,
                time_minutes=10,
            )
            missions._catalog[mission.id] = mission
            missions.start(self.user, mission.id)
            with (
                patch.object(
                    report_ai,
                    "extract_metric",
                    return_value=raw,
                    side_effect=RuntimeError("offline") if raw is None else None,
                ) as infer,
                patch.object(report_ai.logger, "exception"),
            ):
                progress = missions.submit(
                    self.user,
                    mission.id,
                    m.MissionSubmit(
                        description="Sprawdzono wejście do obiektu",
                        photo_ids=[self.photo],
                    ),
                )
            self.assertEqual(progress.status, status)
            self.assertEqual(progress.awarded_points, 30 if status == "accepted" else 0)
            infer.assert_called_once()
            self.assertEqual(
                infer.call_args.args[0], [photos.content(self.user, self.photo)]
            )
            self.assertEqual(
                infer.call_args.args[1], report_ai.metric_prompt("steps_count")
            )
            report = reports.get(self.user, progress.report_id)
            self.assertEqual(report.ai_status, "failed" if raw is None else "completed")
            if status == "accepted":
                self.assertEqual(report.observations[0].value, 3)
            missions.sync_review(report)
        self.assertEqual(missions.activity(self.user).points, 30)

    def test_mission_follows_automatic_decision_and_rewards_once(self):
        mission = m.Mission(
            id="mission_test",
            place_id="node/1",
            place_name="Test",
            title="Policz stopnie",
            fact_id="fact_test",
            attribute="steps_count",
            points=30,
            time_minutes=10,
        )
        missions._catalog[mission.id] = mission
        missions.start(self.user, mission.id)
        with patch.object(
            report_ai,
            "extract_metric",
            return_value='{"attribute":"steps_count","value":3}',
        ):
            progress = missions.submit(
                self.user,
                mission.id,
                m.MissionSubmit(
                    description="Policzono stopnie wejścia",
                    observations=self.body.observations,
                    photo_ids=[self.photo],
                ),
            )
        self.assertEqual(progress.status, "accepted")
        self.assertEqual(progress.awarded_points, mission.points)
        missions.sync_review(reports.get(self.user, progress.report_id))
        self.assertEqual(missions.activity(self.user).points, mission.points)


if __name__ == "__main__":
    unittest.main()
