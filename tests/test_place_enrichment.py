import json
import os
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from hackyeah.place_enrichment import import_records, preserve_enrichment
from hackyeah.places import get
from scripts.import_place_web_data import import_records as import_web
from scripts.scrape_place_photos import photo_data
from scripts.scrape_place_websites import PlacePage, structured_values
from scripts.scrape_place_websites import main as scrape_main
from scripts.scrape_public_places import match_place, toilet_data


class EnrichmentTests(unittest.TestCase):
    def test_accessibility_observations_conflict_and_conditional_claims(self):
        self.assertEqual(
            toilet_data({"nplnsprw": "tak, po remoncie"})["accessibility_observations"],
            [],
        )
        data = toilet_data({"nplnsprw": "Nie", "status": "czynne"})
        self.assertEqual(
            toilet_data({"nplnsprw": "tak, po stronie damskiej"})[
                "accessibility_observations"
            ],
            [{"attribute": "accessible_toilet", "value": True}],
        )
        import_records(self.path, [{**self.record, "data": data}])
        with patch.dict(os.environ, DATABASE_PATH=str(self.path)):
            place = get("node/1")
            fact = next(f for f in place.facts if f.attribute == "accessible_toilet")
            self.assertIs(fact.value, False)
            self.assertEqual(fact.sources[0].url, self.record["source_url"])
            self.assertEqual(fact.status, "unconfirmed")
            self.assertIn("Nie", place.accessibility_summary)
            self.assertEqual(place.barriers[0].fact_ids, [fact.id])
        import_records(
            self.path,
            [
                {
                    **self.record,
                    "source_id": "2",
                    "data": toilet_data({"nplnsprw": "Tak"}),
                }
            ],
        )
        with patch.dict(os.environ, DATABASE_PATH=str(self.path)):
            fact = next(
                f for f in get("node/1").facts if f.attribute == "accessible_toilet"
            )
            self.assertIsNone(fact.value)
            self.assertEqual(fact.unconfirmed_reason, "conflicting")
            self.assertEqual(len(fact.sources), 2)

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "places.sqlite3"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript(Path("scripts/schema.sql").read_text())
            db.execute(
                "INSERT INTO metadata VALUES ('imported_at', '\"2026-10-03T12:00:00+00:00\"')"
            )
            db.execute(
                "INSERT INTO osm_objects VALUES ('node/1','node',1,'https://osm.org/node/1','ODbL',NULL,NULL,'{}','{}')"
            )
            db.execute(
                "INSERT INTO places(id,name,lat,lon,website) VALUES ('node/1','Muzeum',50,20,'https://example.org/museum')"
            )
            for field in (
                "steps_count",
                "threshold_height_cm",
                "elevator_available",
                "entrance_width_cm",
                "accessible_toilet",
            ):
                db.execute(
                    "INSERT INTO accessibility_facts VALUES ('node/1',?,NULL,NULL,'unconfirmed','missing',NULL,NULL)",
                    (field,),
                )
        self.record = dict(
            source="bip_libraries",
            source_id="1",
            place_id="node/1",
            source_url="https://www.bip.krakow.pl/?dok_id=83400",
            retrieved_at="2026-10-03T12:00:00+00:00",
            license="Public data",
            match_method="library_branch_and_address",
            data={"phone": "123456789", "opening_hours": "Mo 09:00-17:00"},
        )

    def test_idempotent_import_api_fallback_photo_and_preservation(self):
        page = {
            "title": "File:Museum.jpg",
            "imageinfo": [
                {
                    "mime": "image/jpeg",
                    "url": "https://upload.wikimedia.org/museum.jpg",
                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Museum.jpg",
                    "extmetadata": {
                        "Artist": {"value": "<a>Photographer</a>"},
                        "LicenseShortName": {"value": "CC BY-SA 4.0"},
                        "LicenseUrl": {
                            "value": "https://creativecommons.org/licenses/by-sa/4.0/"
                        },
                    },
                }
            ],
        }
        photo = photo_data(page)
        self.assertIsNotNone(photo)
        self.assertEqual(photo["author"], "Photographer")
        records = [
            self.record,
            {
                **self.record,
                "source": "commons",
                "source_id": "photo:1",
                "data": {"photo": photo},
            },
        ]
        for _ in range(2):
            import_records(self.path, records)
        with patch.dict(os.environ, DATABASE_PATH=str(self.path)):
            place = get("node/1")
            self.assertEqual(place.phone, "123456789")
            self.assertEqual(place.opening_hours, "Mo 09:00-17:00")
            self.assertEqual(len(place.photos), 1)
            self.assertEqual(place.photos[0].license, "CC BY-SA 4.0")
            self.assertEqual(len(place.attribution), 3)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM external_place_data").fetchone()[0], 2
            )
            self.assertIsNone(db.execute("SELECT phone FROM places").fetchone()[0])
        # An OSM rebuild which removes a place preserves the source record but clears its link.
        with closing(sqlite3.connect(":memory:")) as target:
            target.execute("PRAGMA foreign_keys=ON")
            target.execute("CREATE TABLE places(id TEXT PRIMARY KEY)")
            preserve_enrichment(self.path, target)
            self.assertEqual(
                target.execute(
                    "SELECT count(place_id) FROM external_place_data"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(target.execute("PRAGMA foreign_key_check").fetchall(), [])
        page["imageinfo"][0]["extmetadata"]["LicenseShortName"]["value"] = (
            "All rights reserved"
        )
        self.assertIsNone(photo_data(page))

    def test_foreign_key_failure_rolls_back_batch(self):
        with self.assertRaises(sqlite3.IntegrityError):
            import_records(
                self.path,
                [self.record, {**self.record, "source_id": "2", "place_id": "missing"}],
            )
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM external_place_data").fetchone()[0], 0
            )

    def test_structured_hours_belong_to_one_branch(self):
        doc = PlacePage()
        doc.feed(
            '<script type="application/ld+json">'
            + json.dumps(
                [
                    {
                        "@type": "LocalBusiness",
                        "name": "Muzeum",
                        "geo": {"latitude": 50, "longitude": 20},
                        "openingHoursSpecification": [
                            {"dayOfWeek": "Monday", "opens": "09:00", "closes": "17:00"}
                        ],
                    },
                    {
                        "@type": "Organization",
                        "name": "Head office",
                        "telephone": "wrong",
                    },
                ]
            )
            + "</script>"
        )
        values = structured_values(doc, {"lat": 50, "lon": 20}, shared=True)
        self.assertIn("09:00", values["openingHours"])
        self.assertNotIn("telephone", values)
        self.assertEqual(
            structured_values(doc, {"lat": 52, "lon": 21}, shared=True), {}
        )
        candidate = {"id": "node/1", "name": "Muzeum Lotnictwa", "lat": 50, "lon": 20}
        self.assertEqual(match_place(candidate, [candidate])[0], "node/1")
        self.assertEqual(
            match_place(candidate, [candidate, {**candidate, "id": "node/2"}]),
            (None, None),
        )
        self.assertEqual(
            match_place({**candidate, "lat": 51}, [candidate]), (None, None)
        )

    def test_scraper_cli_updates_database_and_snapshot_only_does_not(self):
        output = Path(self.directory.name) / "web.json"
        web = dict(
            source_url="https://example.org/museum",
            retrieved_at="2026-10-03T12:00:00+00:00",
            title="Museum",
            description=None,
            telephone="123",
            opening_hours="Mo 10:00-16:00",
            accessibility_summary=None,
        )
        argv = [
            "scrape",
            "--database",
            str(self.path),
            "--output",
            str(output),
            "--delay",
            "0",
        ]
        with (
            patch("sys.argv", argv),
            patch("scripts.scrape_place_websites.scrape", return_value=web),
        ):
            scrape_main()
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(
                db.execute("SELECT telephone FROM place_web_data").fetchone()[0], "123"
            )
        with (
            patch("sys.argv", argv + ["--refresh", "--snapshot-only"]),
            patch(
                "scripts.scrape_place_websites.scrape",
                return_value={**web, "telephone": "456"},
            ),
        ):
            scrape_main()
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(
                db.execute("SELECT telephone FROM place_web_data").fetchone()[0], "123"
            )
        self.assertEqual(json.loads(output.read_text())[0]["telephone"], "456")
        with self.assertRaises(ValueError):
            import_web(self.path, [{"place_id": "missing", **web}])


if __name__ == "__main__":
    unittest.main()
