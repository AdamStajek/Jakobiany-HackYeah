import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from shapely.geometry import box

from scripts.build_route_graph import build_graph


class RouteGraphBuildTests(unittest.TestCase):
    def test_full_extent_filtering_topology_and_failed_rebuild_preserves_graph(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "tiny.osm"
            boundary = root / "boundary.json"
            boundary.write_text("{}")
            output = root / "city.sqlite3"
            source.write_text("""<osm version="0.6">
              <bounds minlat="50" minlon="19.9" maxlat="50.1" maxlon="20"/>
              <node id="1" lat="50.06" lon="19.93" timestamp="2026-10-01T12:00:00Z"/>
              <node id="2" lat="50.061" lon="19.931" timestamp="2026-10-01T12:00:00Z">
                <tag k="barrier" v="kerb"/><tag k="kerb:height" v="0.15"/>
              </node>
              <node id="3" lat="50.062" lon="19.932" timestamp="2026-10-01T12:00:00Z"/>
              <node id="4" lat="50.062" lon="19.93" timestamp="2026-10-01T12:00:00Z"/>
              <node id="5" lat="50.06" lon="19.932" timestamp="2026-10-01T12:00:00Z"/>
              <way id="10" timestamp="2026-10-01T12:00:00Z">
                <nd ref="1"/><nd ref="2"/><nd ref="3"/>
                <tag k="highway" v="footway"/><tag k="oneway:foot" v="yes"/>
              </way>
              <way id="20" timestamp="2026-10-01T12:00:00Z">
                <nd ref="4"/><nd ref="5"/><tag k="highway" v="footway"/>
              </way>
              <way id="30" timestamp="2026-10-01T12:00:00Z">
                <nd ref="1"/><nd ref="5"/><tag k="highway" v="footway"/><tag k="foot" v="no"/>
              </way>
              <way id="40" timestamp="2026-10-01T12:00:00Z">
                <nd ref="1"/><nd ref="5"/><tag k="highway" v="cycleway"/>
              </way>
            </osm>""")
            with patch(
                "scripts.build_route_graph.load_boundary",
                return_value=box(19.92, 50.05, 19.94, 50.07),
            ):
                metadata = build_graph(source, boundary, output)
            self.assertEqual(metadata["ways"], 2)
            self.assertEqual(metadata["links"], 3)
            with closing(sqlite3.connect(output)) as db:
                self.assertEqual(
                    db.execute("SELECT a,b FROM links WHERE way=20").fetchall(),
                    [(4, 5)],
                )
                tags = json.loads(
                    db.execute("SELECT tags FROM nodes WHERE id=2").fetchone()[0]
                )
                self.assertEqual(tags["kerb:height"], "0.15")
            previous = output.read_bytes()
            with patch(
                "scripts.build_route_graph.load_boundary",
                return_value=box(19.9, 50, 20.2, 50.1),
            ):
                with self.assertRaises(ValueError):
                    build_graph(source, boundary, output)
            self.assertEqual(output.read_bytes(), previous)
            source.write_text("broken")
            with patch(
                "scripts.build_route_graph.load_boundary",
                return_value=box(19.92, 50.05, 19.94, 50.07),
            ):
                with self.assertRaises(RuntimeError):
                    build_graph(source, boundary, output)
            self.assertEqual(output.read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
