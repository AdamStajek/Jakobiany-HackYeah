import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from xml.etree.ElementTree import Element, SubElement, tostring

from shapely import STRtree
from shapely.geometry import Point, Polygon

from scripts.build_places_db import (
    FIELDS,
    Evidence,
    OSMObject,
    build_database,
    classify,
    consolidate,
    length_cm,
    link_features,
    load_boundary,
    observations,
)
from scripts.download_osm import download
from scripts.report_places import coverage


def make_fixture(directory: Path) -> tuple[Path, Path]:
    source = directory / "places.osm"
    root = Element("osm", version="0.6", generator="unit-test")
    records = [
        (1, 50.0, 19.9, {}),
        (2, 50.0, 19.94, {}),
        (3, 50.04, 19.94, {}),
        (4, 50.04, 19.9, {}),
        (
            11,
            50.02,
            19.9,
            {
                "entrance": "main",
                "door:width": "90 cm",
                "threshold:height": "2 cm",
                "entrance:step_count": "2",
                "ramp:wheelchair": "yes",
            },
        ),
        (12, 50.01, 19.91, {"highway": "elevator"}),
        (13, 50.01, 19.92, {"amenity": "toilets", "wheelchair": "yes"}),
        (14, 50.02, 19.89999, {"amenity": "toilets", "wheelchair": "no"}),
        (
            20,
            50.02,
            19.92,
            {
                "shop": "supermarket",
                "name": "Sklep we wspólnym budynku",
                "wheelchair": "no",
                "toilets:wheelchair": "no",
            },
        ),
        (21, 50.1, 20.0, {"amenity": "library", "name": "Biblioteka bez danych"}),
        (22, 50.5, 20.0, {"tourism": "hotel", "name": "Poza Krakowem"}),
        (
            23,
            50.1,
            19.99,
            {"amenity": "community_centre", "name": "Centrum Aktywizacji Seniora"},
        ),
    ]
    for id, lat, lon, tags in records:
        node = SubElement(
            root,
            "node",
            id=str(id),
            lat=str(lat),
            lon=str(lon),
            version="1",
            timestamp="2026-01-01T12:00:00Z",
        )
        for key, value in tags.items():
            SubElement(node, "tag", k=key, v=value)
    way = SubElement(
        root, "way", id="100", version="1", timestamp="2026-01-01T12:00:00Z"
    )
    for id in (1, 2, 3, 4, 1):
        SubElement(way, "nd", ref=str(id))
    for key, value in {
        "tourism": "hotel",
        "building": "yes",
        "name": "Hotel testowy",
        "wheelchair": "yes",
    }.items():
        SubElement(way, "tag", k=key, v=value)
    source.write_bytes(tostring(root, encoding="utf-8", xml_declaration=True))
    boundary = directory / "boundary.json"
    boundary.write_text(
        json.dumps(
            {
                "elements": [
                    *[
                        {"type": "node", "id": id, "lat": lat, "lon": lon}
                        for id, lat, lon in [
                            (1, 49.9, 19.8),
                            (2, 49.9, 20.1),
                            (3, 50.2, 20.1),
                            (4, 50.2, 19.8),
                        ]
                    ],
                    {"type": "way", "id": 10, "nodes": [1, 2, 3, 4, 1]},
                    {
                        "type": "relation",
                        "id": 449696,
                        "tags": {"name": "Kraków", "boundary": "administrative"},
                        "members": [{"type": "way", "ref": 10, "role": "outer"}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return source, boundary


class OSMImportTests(unittest.TestCase):
    def test_additive_import_retains_uncategorized_places(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source, boundary = make_fixture(folder)
            destination = folder / "places.sqlite3"
            build_database(source, boundary, destination)
            with sqlite3.connect(destination) as db:
                db.execute(
                    "INSERT INTO osm_objects VALUES ('node/999','node',999,'https://www.openstreetmap.org/node/999','ODbL',NULL,NULL,'{}','{}')"
                )
                db.execute(
                    "INSERT INTO places(id,name,lat,lon) VALUES ('node/999','Existing place',50,20)"
                )
                db.execute(
                    "INSERT INTO accessibility_facts VALUES ('node/999','steps_count','3','count','unconfirmed','pending_verification',NULL,NULL)"
                )
                db.execute(
                    "INSERT INTO accessibility_facts VALUES ('node/999','surface','\"fine_gravel\"',NULL,'unconfirmed','pending_verification',NULL,NULL)"
                )
            build_database(source, boundary, destination, additive=True)
            with sqlite3.connect(destination) as db:
                self.assertEqual(
                    db.execute(
                        "SELECT name FROM places WHERE id='node/999'"
                    ).fetchone()[0],
                    "Existing place",
                )
                self.assertEqual(
                    db.execute(
                        "SELECT value_json FROM accessibility_facts WHERE place_id='node/999' AND attribute='steps_count'"
                    ).fetchone()[0],
                    "3",
                )
                self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(
                    db.execute(
                        "SELECT value_json FROM accessibility_facts WHERE place_id='node/999' AND attribute='surface'"
                    ).fetchone()[0],
                    '"gravel"',
                )

    def test_obstacle_categories_and_api_facts(self):
        tags = {
            "highway": "steps",
            "step_count": "12",
            "lit": "no",
            "surface": "paving_stones",
            "smoothness": "bad",
        }
        obj = OSMObject("node/1", "node", 1, tags, Point(19.94, 50.06))
        values = {e.attribute: e.value for e in observations(obj)}
        self.assertEqual(classify(tags), ["steps"])
        self.assertEqual(values["steps_count"], 12)
        self.assertIs(values["steps_present"], True)
        self.assertIs(values["lighting_available"], False)
        self.assertEqual(values["surface"], "paved")
        self.assertEqual(values["smoothness"], "bad")
        obj.tags = {"barrier": "kerb", "height": "15 cm", "kerb": "raised"}
        values = {e.attribute: e.value for e in observations(obj)}
        self.assertEqual(classify(obj.tags), ["kerb"])
        self.assertEqual(values["kerb_height_cm"], 15)
        self.assertIs(values["raised_kerb"], True)

    def test_lengths_do_not_guess_ambiguous_measurements(self):
        self.assertEqual(length_cm("0.9"), 90)
        self.assertEqual(length_cm("90 cm"), 90)
        self.assertEqual(length_cm("0,9 m"), 90)
        self.assertEqual(length_cm("20 mm"), 2)
        self.assertIsNone(length_cm("high"))
        self.assertIsNone(length_cm("0.8;1.2"))
        self.assertIsNone(length_cm("5", default_unit=None))
        self.assertEqual(length_cm("0", default_unit=None), 0)
        self.assertEqual(length_cm("0,0", default_unit=None), 0)

    def test_failed_download_keeps_previous_snapshot(self):
        class Response(io.BytesIO):
            headers = {"Content-Length": "100"}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.pbf"
            path.write_bytes(b"previous snapshot")
            with (
                patch(
                    "scripts.download_osm.urlopen",
                    side_effect=lambda *args, **kwargs: Response(b"partial"),
                ),
                patch("scripts.download_osm.time.sleep"),
            ):
                with self.assertRaises(OSError):
                    download("https://example.org/snapshot.pbf", path)
            self.assertEqual(path.read_bytes(), b"previous snapshot")
            self.assertFalse(path.with_suffix(".pbf.part").exists())

    def test_no_detailed_measurements_from_wheelchair(self):
        obj = OSMObject(
            "node/1",
            "node",
            1,
            {"wheelchair": "yes", "toilets:wheelchair": "limited"},
            Point(19.9, 50),
        )
        facts = {e.attribute: e.value for e in observations(obj)}
        self.assertEqual(facts["wheelchair"], "yes")
        self.assertEqual(facts["toilet_wheelchair"], "limited")
        self.assertNotIn("steps_count", facts)
        self.assertNotIn("entrance_width_cm", facts)
        self.assertNotIn("threshold_height_cm", facts)
        self.assertNotIn("accessible_toilet", facts)

    def test_step_height_and_width_are_not_confused_with_other_features(self):
        obj = OSMObject(
            "node/1",
            "node",
            1,
            {
                "highway": "elevator",
                "door:width": "1",
                "wheelchair:step_height": "2 cm",
            },
            Point(19.9, 50),
        )
        facts = {e.attribute: e.value for e in observations(obj)}
        self.assertNotIn("entrance_width_cm", facts)
        self.assertNotIn("threshold_height_cm", facts)
        self.assertEqual(facts["entrance_step_height_cm"], 2)

    def test_explicit_description_is_narrow(self):
        for text, expected in [
            ("1 step at entrance", 1),
            ("wheelchair accessible", None),
            ("1 step at entrance, another 10 inside", None),
        ]:
            obj = OSMObject(
                "node/1", "node", 1, {"wheelchair:description": text}, Point(19.9, 50)
            )
            facts = {e.attribute: e.value for e in observations(obj)}
            self.assertEqual(facts.get("steps_count"), expected)

    def test_conflicting_values_remain_unknown(self):
        evidence = [
            Evidence(
                "accessible_toilet", True, "node/1", "wheelchair", "yes", "within_place"
            ),
            Evidence(
                "accessible_toilet", False, "node/2", "wheelchair", "no", "within_place"
            ),
        ]
        self.assertEqual(consolidate(evidence), (None, "conflicting"))
        self.assertEqual(consolidate(evidence[:1]), ("true", "pending_verification"))
        self.assertEqual(consolidate([]), (None, "missing"))

    def test_no_association_by_proximity(self):
        place = OSMObject(
            "way/1", "way", 1, {}, Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        )
        outside = OSMObject(
            "node/2", "node", 2, {"amenity": "toilets"}, Point(1.00001, 0.5)
        )
        self.assertEqual(
            link_features(place, [outside], STRtree([outside.geometry])), []
        )

    def test_all_categories_and_senior_facilities(self):
        cases = [
            ({"tourism": "hotel"}, "hotel"),
            ({"tourism": "museum"}, "museum"),
            ({"office": "government"}, "government"),
            ({"shop": "convenience"}, "grocery"),
            ({"amenity": "post_office"}, "post_office"),
            ({"amenity": "bank"}, "bank"),
            ({"heritage": "2"}, "historic"),
            ({"tourism": "viewpoint"}, "viewpoint"),
            ({"amenity": "library"}, "library"),
            ({"amenity": "cinema"}, "cinema"),
            ({"amenity": "theatre"}, "theatre"),
            ({"amenity": "parcel_locker"}, "parcel_locker"),
            (
                {"amenity": "place_of_worship", "religion": "christian"},
                "church",
            ),
            ({"amenity": "arts_centre"}, "community_centre"),
            (
                {"amenity": "community_centre", "name": "Centrum Aktywizacji Seniora"},
                "senior_club",
            ),
        ]
        for tags, expected in cases:
            with self.subTest(tags=tags):
                self.assertIn(expected, classify(tags))
        self.assertNotIn(
            "senior_club",
            classify(
                {
                    "amenity": "social_facility",
                    "social_facility": "nursing_home",
                    "social_facility:for": "senior",
                }
            ),
        )

    def test_full_import_and_repeat_are_consistent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, boundary = make_fixture(root)
            destination = root / "places.sqlite3"
            self.assertTrue(load_boundary(boundary).covers(Point(19.9, 50)))
            for _ in range(2):
                build_database(source, boundary, destination)
                with closing(sqlite3.connect(destination)) as db:
                    self.assertEqual(
                        db.execute("PRAGMA integrity_check").fetchone()[0], "ok"
                    )
                    self.assertEqual(
                        db.execute("PRAGMA foreign_key_check").fetchall(), []
                    )
                    self.assertEqual(
                        db.execute("SELECT COUNT(*) FROM places").fetchone()[0], 7
                    )
                    self.assertIsNone(
                        db.execute(
                            "SELECT id FROM places WHERE id='node/22'"
                        ).fetchone()
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT COUNT(*) FROM accessibility_facts"
                        ).fetchone()[0],
                        7 * len(FIELDS),
                    )
                    row = db.execute(
                        "SELECT steps_count, threshold_height_cm, elevator_available, entrance_width_cm, accessible_toilet FROM place_accessibility WHERE id='way/100'"
                    ).fetchone()
                    self.assertEqual(row, (2, 2, 1, 90, 1))
                    row = db.execute(
                        "SELECT steps_count, elevator_available, entrance_width_cm, accessible_toilet FROM place_accessibility WHERE id='node/20'"
                    ).fetchone()
                    self.assertEqual(row, (None, None, None, 0))
                    self.assertEqual(
                        db.execute(
                            "SELECT COUNT(*) FROM accessibility_facts WHERE status!='unconfirmed' OR observed_at IS NOT NULL OR confidence_percent IS NOT NULL"
                        ).fetchone()[0],
                        0,
                    )
                report = coverage(destination)
                self.assertEqual(report["total_places"], 7)
                self.assertEqual(report["all_five_primary_fields"], 1)
                self.assertEqual(
                    next(
                        f for f in report["fields"] if f["attribute"] == "steps_count"
                    )["known"],
                    1,
                )
            original = destination.read_bytes()
            boundary.write_text("{}")
            with self.assertRaises(KeyError):
                build_database(source, boundary, destination)
            self.assertEqual(destination.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
