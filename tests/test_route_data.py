import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from hackyeah.models import (
    ROUTE_ATTRIBUTES,
    Constraints,
    Observation,
    RouteDataFeature,
    RouteSegment,
)
from hackyeah.route_data import export_routes, extract_facts, height_cm


class RouteDataTests(unittest.TestCase):
    def test_units_unknowns_and_conservative_evidence(self):
        now = datetime.now(UTC)
        facts = {
            f.attribute: f
            for f in extract_facts(
                {
                    "highway": "steps",
                    "kerb": "raised",
                    "kerb:height": "0.15",
                    "ramp:bicycle": "yes",
                    "surface": "asphalt",
                    "smoothness": "bad",
                    "lit": "no",
                },
                "way/1",
                now,
                now,
            )
        }
        self.assertEqual(set(facts), ROUTE_ATTRIBUTES)
        self.assertTrue(facts["steps_present"].value)
        self.assertIsNone(facts["steps_count"].value)
        self.assertEqual(facts["kerb_height_cm"].value, 15)
        self.assertIsNone(facts["ramp_available"].value)
        self.assertIsNone(facts["threshold_height_cm"].value)
        self.assertFalse(facts["lighting_available"].value)
        self.assertEqual(facts["smoothness"].value, "bad")
        for fact in facts.values():
            self.assertEqual(fact.status, "unconfirmed")
            self.assertIsNone(fact.confidence_percent)
            if fact.value is not None:
                self.assertEqual(fact.sources[0].license, "ODbL")
                self.assertEqual(fact.unconfirmed_reason, "pending_verification")
            else:
                self.assertEqual(fact.unconfirmed_reason, "missing")
        self.assertEqual(height_cm("15 cm"), 15)
        self.assertEqual(height_cm("150 mm"), 15)
        self.assertIsNone(height_cm("~0.15"))
        unknown = extract_facts({}, "way/2", now, now)
        self.assertTrue(all(f.value is None for f in unknown))

    def test_route_models_validate_added_categories(self):
        for attribute, value in [
            ("kerb_height_cm", -1),
            ("raised_kerb", 1),
            ("lighting_available", "yes"),
            ("smoothness", "asphalt"),
            ("surface", "bad"),
        ]:
            with self.subTest(attribute=attribute), self.assertRaises(ValidationError):
                Observation(attribute=attribute, value=value)
        now = datetime.now(UTC)
        facts = extract_facts({}, "way/1", now, now)
        segment = {
            "id": "segment1",
            "distance_m": 10,
            "instruction": "Idź do celu.",
            "geometry": {
                "type": "LineString",
                "coordinates": [(19.93, 50.06), (19.931, 50.061)],
            },
            "assessment": {
                "status": "uncertain",
                "summary": "Brak danych",
                "reasons": [],
            },
            "facts": facts,
            "barriers": [],
            "rest_points": [],
        }
        RouteSegment.model_validate(segment)
        for index in range(len(facts)):
            with (
                self.subTest(missing=facts[index].attribute),
                self.assertRaises(ValidationError),
            ):
                RouteSegment.model_validate(
                    {**segment, "facts": facts[:index] + facts[index + 1 :]}
                )
        required = RouteSegment.model_json_schema()["required"]
        self.assertIn("facts", required)
        # Optional new profile fields preserve old clients.
        self.assertNotIn(
            "require_lighting", Constraints.model_json_schema()["required"]
        )

    def test_export_topology_filtering_and_failed_refresh(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "tiny.osm"
            output = root / "network.geojsonl"
            source.write_text(
                """<osm version="0.6">
              <node id="1" lat="50.06" lon="19.93" timestamp="2026-10-01T12:00:00Z"/>
              <node id="2" lat="50.061" lon="19.931" timestamp="2026-10-01T12:00:00Z">
                <tag k="barrier" v="kerb"/><tag k="kerb" v="raised"/>
                <tag k="height" v="12 cm"/>
              </node>
              <node id="3" lat="50.062" lon="19.932" timestamp="2026-10-01T12:00:00Z"/>
              <way id="10" timestamp="2026-10-01T12:00:00Z">
                <nd ref="1"/><nd ref="2"/><nd ref="3"/>
                <tag k="highway" v="steps"/><tag k="step_count" v="3"/>
                <tag k="ramp:wheelchair" v="yes"/><tag k="lit" v="no"/>
              </way>
              <way id="11" timestamp="2026-10-01T12:00:00Z">
                <nd ref="1"/><nd ref="3"/><tag k="highway" v="footway"/>
                <tag k="foot" v="no"/>
              </way>
            </osm>""",
                encoding="utf-8",
            )
            manifest = export_routes(source, output)
            features = [
                RouteDataFeature.model_validate_json(line)
                for line in output.read_text().splitlines()
            ]
            self.assertEqual([f.id for f in features], ["osm/node/2", "osm/way/10"])
            self.assertEqual(features[1].properties.node_ids, [1, 2, 3])
            self.assertEqual(features[1].geometry.coordinates[1], (19.931, 50.061))
            self.assertEqual(manifest["counts"]["stairs"], 1)
            self.assertEqual(manifest["counts"]["unlit"], 1)
            self.assertEqual(manifest["known_facts"]["kerb_height_cm"], 1)
            self.assertEqual(
                json.loads(output.with_suffix(".manifest.json").read_text())["counts"],
                manifest["counts"],
            )
            previous = output.read_bytes()
            source.write_text("broken", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                export_routes(source, output)
            self.assertEqual(output.read_bytes(), previous)
            self.assertFalse(output.with_suffix(".geojsonl.tmp").exists())


if __name__ == "__main__":
    unittest.main()
