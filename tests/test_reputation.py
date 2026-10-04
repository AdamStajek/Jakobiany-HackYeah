import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hackyeah import confidence, database, place_submissions, reports, reputation
from hackyeah import models as m


class ReputationTests(unittest.TestCase):
    def test_decisions_reweight_existing_facts_without_exposing_score(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.sqlite3"
            with sqlite3.connect(path) as db:
                db.executescript(
                    (
                        Path(__file__).resolve().parents[1] / "scripts/schema.sql"
                    ).read_text()
                )
            with patch.dict(os.environ, {"DATABASE_PATH": str(path)}):
                database.initialize()
                user = m.User(id="author", display_name="Author", roles=["user"])
                moderator = m.User(id="mod", display_name="Mod", roles=["moderator"])
                self.assertEqual(reputation.scores().get(user.id, 0.5), 0.5)

                def create(target):
                    return reports.create(
                        user,
                        m.ReportCreate(
                            target=m.ReportTarget(type="place", id=target),
                            kind="missing_data",
                            observations=[
                                m.Observation(attribute="steps_count", value=2)
                            ],
                        ),
                    )

                good = create("good")
                reports.review(
                    moderator,
                    good.id,
                    m.ReportReview(decision="accepted", comment="OK"),
                )

                def weight():
                    with database.atomic as db:
                        return confidence.get(db, "place", "good", "steps_count", 2)[0]

                self.assertEqual(weight(), 1.25)
                bad = create("bad")
                reports.review(
                    moderator,
                    bad.id,
                    m.ReportReview(decision="rejected", comment="Wrong"),
                )
                self.assertEqual(reputation.scores()[user.id], 0.5)
                self.assertEqual(weight(), 0.625)
                reports.update(user, bad.id, m.ReportPatch(description="Try again"))
                self.assertEqual(reputation.scores()[user.id], 0.5)
                self.assertEqual(weight(), 0.625)

                item = place_submissions.create(
                    user,
                    m.PlaceSubmissionCreate(
                        name="Fake",
                        category="cafe",
                        address="Test 1",
                        location=m.Coordinates(lat=50, lon=20),
                    ),
                )
                place_submissions.review(
                    moderator,
                    item.id,
                    m.ReportReview(decision="rejected", comment="Wrong place"),
                )
                self.assertAlmostEqual(reputation.scores()[user.id], 1 / 3)
                self.assertAlmostEqual(weight(), 1.25 / 3)
                confidence.recalculate_all()
                self.assertAlmostEqual(weight(), 1.25 / 3)
                self.assertNotIn("score", user.model_dump())
                self.assertNotIn("reputation", reports.get(user, good.id).model_dump())


if __name__ == "__main__":
    unittest.main()
