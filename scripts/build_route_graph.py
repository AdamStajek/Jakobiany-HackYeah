"""Build a compact pedestrian graph covering Kraków from a complete OSM extract."""

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import osmium
from osmium.io import Reader
from shapely.geometry import LineString, Point, box
from shapely.prepared import prep

from hackyeah.route_data import HIGHWAYS, TAG_KEYS
from scripts.build_places_db import load_boundary
from scripts.download_osm import ROOT, sha256

KEYS = TAG_KEYS | {
    "wheelchair",
    "amenity",
    "leisure",
    "toilets:wheelchair",
    "entrance",
    "entrance:width",
    "entrance:threshold:height",
    "door:width",
    "door:threshold:height",
}


def walkable(tags):
    if tags.get("highway") not in HIGHWAYS or tags.get("area") == "yes":
        return False
    if tags.get("foot") in {"no", "private", "use_sidepath"}:
        return False
    explicit = tags.get("foot") in {"yes", "designated", "permissive"}
    if tags.get("access") in {"no", "private"} and not explicit:
        return False
    return not (tags.get("highway") == "cycleway" and not explicit)


def build_graph(source: Path, boundary_path: Path, output: Path) -> dict:
    boundary = load_boundary(boundary_path)
    with Reader(str(source)) as reader:
        extent = reader.header().box()
        if extent.valid() and not box(
            extent.bottom_left.lon,
            extent.bottom_left.lat,
            extent.top_right.lon,
            extent.top_right.lat,
        ).covers(boundary):
            raise ValueError(
                "Wyciąg nie pokrywa całego Krakowa. Użyj pełnego wyciągu Małopolski."
            )
    # Include nearby streets so routes can follow connections crossing the city boundary.
    region = prep(boundary.buffer(0.005))
    west, south, east, north = boundary.buffer(0.005).bounds
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as directory:
        candidate = Path(directory) / "city.sqlite3"
        with closing(sqlite3.connect(candidate)) as db:
            db.executescript("""
                PRAGMA journal_mode=OFF;
                CREATE TABLE nodes(id INTEGER PRIMARY KEY, lon REAL, lat REAL, tags TEXT, updated TEXT);
                CREATE TABLE ways(id INTEGER PRIMARY KEY, tags TEXT, updated TEXT);
                CREATE TABLE links(a INTEGER, b INTEGER, way INTEGER, position INTEGER);
                CREATE TABLE amenities(id INTEGER PRIMARY KEY, lon REAL, lat REAL, tags TEXT, updated TEXT);
                CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT);
            """)

            class Handler(osmium.SimpleHandler):
                def node(self, node):
                    if not node.location.valid():
                        return
                    lon, lat = node.location.lon, node.location.lat
                    if not (west <= lon <= east and south <= lat <= north):
                        return
                    tags = {t.k: t.v for t in node.tags if t.k in KEYS}
                    if not tags or not region.covers(Point(lon, lat)):
                        return
                    encoded = json.dumps(tags)
                    updated = node.timestamp.isoformat()
                    db.execute(
                        "INSERT INTO nodes VALUES(?,?,?,?,?)",
                        (node.id, lon, lat, encoded, updated),
                    )
                    if (
                        tags.get("amenity") in {"bench", "toilets"}
                        or tags.get("leisure") == "picnic_table"
                    ):
                        db.execute(
                            "INSERT INTO amenities VALUES(?,?,?,?,?)",
                            (node.id, lon, lat, encoded, updated),
                        )

                def way(self, way):
                    tags = {t.k: t.v for t in way.tags if t.k in KEYS}
                    if (
                        not walkable(tags)
                        or len(way.nodes) < 2
                        or any(not n.location.valid() for n in way.nodes)
                    ):
                        return
                    coordinates = [(n.lon, n.lat) for n in way.nodes]
                    if not (
                        min(p[0] for p in coordinates) <= east
                        and max(p[0] for p in coordinates) >= west
                        and min(p[1] for p in coordinates) <= north
                        and max(p[1] for p in coordinates) >= south
                    ):
                        return
                    if not region.intersects(LineString(coordinates)):
                        return
                    db.execute(
                        "INSERT INTO ways VALUES(?,?,?)",
                        (way.id, json.dumps(tags), way.timestamp.isoformat()),
                    )
                    db.executemany(
                        "INSERT OR IGNORE INTO nodes VALUES(?,?,?,?,?)",
                        [
                            (n.ref, n.lon, n.lat, "{}", way.timestamp.isoformat())
                            for n in way.nodes
                        ],
                    )
                    db.executemany(
                        "INSERT INTO links VALUES(?,?,?,?)",
                        [
                            (a.ref, b.ref, way.id, i)
                            for i, (a, b) in enumerate(
                                zip(way.nodes, list(way.nodes)[1:], strict=False)
                            )
                        ],
                    )

            with db:
                Handler().apply_file(str(source), locations=True, idx="flex_mem")
                # Remove tagged nodes that are not part of a routable way. Amenities remain separately.
                db.execute(
                    "DELETE FROM nodes WHERE id NOT IN (SELECT a FROM links UNION SELECT b FROM links)"
                )
                metadata = {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "input": str(source),
                    "source_sha256": sha256(source),
                    "boundary_sha256": sha256(boundary_path),
                    "boundary_relation": 449696,
                    "bounds": boundary.bounds,
                    "nodes": db.execute("SELECT count(*) FROM nodes").fetchone()[0],
                    "ways": db.execute("SELECT count(*) FROM ways").fetchone()[0],
                    "links": db.execute("SELECT count(*) FROM links").fetchone()[0],
                    "amenities": db.execute(
                        "SELECT count(*) FROM amenities"
                    ).fetchone()[0],
                    "license": "ODbL",
                    "attribution": "© OpenStreetMap contributors",
                }
                db.executemany(
                    "INSERT INTO metadata VALUES(?,?)",
                    [(k, json.dumps(v)) for k, v in metadata.items()],
                )
            if (
                metadata["links"] == 0
                or db.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            ):
                raise ValueError("Niepoprawny lub pusty graf pieszy.")
        candidate.replace(output)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=ROOT / "data/raw/malopolskie-latest.osm.pbf"
    )
    parser.add_argument(
        "--boundary", type=Path, default=ROOT / "data/raw/krakow-boundary.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/routes/city.sqlite3"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            build_graph(args.input, args.boundary, args.output),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
