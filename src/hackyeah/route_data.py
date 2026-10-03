"""Export OSM route topology and accessibility evidence without a database."""

import argparse
import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from hackyeah.models import (
    ROUTE_ATTRIBUTES,
    Fact,
    LineString,
    Point,
    RouteDataFeature,
    RouteDataProperties,
    Source,
)

DOWNLOAD_URL = "https://download.bbbike.org/osm/bbbike/Cracow/Cracow.osm.pbf"
# Envelope from data/raw/Cracow.poly; not an administrative boundary.
BOUNDS = (19.76, 49.96, 20.16, 50.14)
HIGHWAYS = {
    "footway",
    "path",
    "pedestrian",
    "steps",
    "living_street",
    "residential",
    "service",
    "unclassified",
    "track",
    "tertiary",
    "tertiary_link",
    "secondary",
    "secondary_link",
    "primary",
    "primary_link",
    "cycleway",
}
TAG_KEYS = {
    "highway",
    "foot",
    "access",
    "wheelchair",
    "sidewalk",
    "sidewalk:left",
    "sidewalk:right",
    "oneway:foot",
    "name",
    "surface",
    "smoothness",
    "lit",
    "step_count",
    "barrier",
    "kerb",
    "kerb:height",
    "height",
    "ramp",
    "ramp:wheelchair",
    "ramp:stroller",
    "ramp:bicycle",
    "incline",
    "width",
    "bridge",
    "tunnel",
    "layer",
    "level",
    "crossing",
}
SMOOTHNESS = {
    "excellent",
    "good",
    "intermediate",
    "bad",
    "very_bad",
    "horrible",
    "very_horrible",
    "impassable",
}
SURFACES = {
    "paved": "paved",
    "asphalt": "asphalt",
    "concrete": "paved",
    "concrete:plates": "paved",
    "paving_stones": "paved",
    "sett": "cobblestone",
    "cobblestone": "cobblestone",
    "gravel": "gravel",
    "fine_gravel": "gravel",
    "ground": "ground",
    "earth": "ground",
    "dirt": "ground",
}
UNITS = {"steps_count": "count", "threshold_height_cm": "cm", "kerb_height_cm": "cm"}


def height_cm(raw: str | None) -> float | None:
    """OSM heights default to metres. Reject approximate or ambiguous values."""
    if raw is None:
        return None
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(cm|m|mm)?\s*", raw)
    if match is None:
        return None
    value = float(match[1]) * {None: 100, "m": 100, "cm": 1, "mm": 0.1}[match[2]]
    return value if math.isfinite(value) else None


def extract_facts(
    tags: dict[str, str], object_id: str, updated_at: datetime, retrieved_at: datetime
) -> list[Fact]:
    values: dict[str, int | float | bool | str | None] = dict.fromkeys(ROUTE_ATTRIBUTES)
    count = tags.get("step_count", "")
    if re.fullmatch(r"\d+", count):
        values["steps_count"] = int(count)
    if tags.get("highway") == "steps" or tags.get("barrier") == "step":
        values["steps_present"] = True
    elif values["steps_count"] is not None:
        values["steps_present"] = int(count) > 0
    kerb = tags.get("kerb")
    values["kerb_height_cm"] = height_cm(tags.get("kerb:height"))
    if values["kerb_height_cm"] is None and tags.get("barrier") == "kerb":
        values["kerb_height_cm"] = height_cm(tags.get("height"))
    if kerb == "raised":
        values["raised_kerb"] = True
    elif kerb in {"flush", "no"}:
        values["raised_kerb"] = False
    # A bicycle/stroller ramp is not evidence of a usable mobility ramp.
    ramp = tags.get("ramp:wheelchair")
    if ramp in {"yes", "no"}:
        values["ramp_available"] = ramp == "yes"
    elif tags.get("ramp") == "no":
        values["ramp_available"] = False
    surface = tags.get("surface")
    if surface:
        values["surface"] = SURFACES.get(surface, "other")
    if tags.get("smoothness") in SMOOTHNESS:
        values["smoothness"] = tags["smoothness"]
    if tags.get("lit") in {"yes", "no"}:
        values["lighting_available"] = tags["lit"] == "yes"
    # No reliable threshold measurement tag in this source; keep it unknown.
    source = Source(
        type="osm",
        label="OpenStreetMap",
        url=f"https://www.openstreetmap.org/{object_id}",
        license="ODbL",
        retrieved_at=retrieved_at,
    )
    return [
        Fact.model_validate(
            {
                "id": f"osm/{object_id}/{attribute}",
                "attribute": attribute,
                "value": value,
                "unit": UNITS.get(attribute),
                "status": "unconfirmed",
                "confidence_percent": None,
                "observed_at": None,
                "updated_at": updated_at,
                "valid_until": None,
                "sources": [source] if value is not None else [],
                "unconfirmed_reason": "pending_verification"
                if value is not None
                else "missing",
            }
        )
        for attribute, value in sorted(values.items())
    ]


def export_routes(pbf: Path, output: Path) -> dict:
    # Optional data dependency; FastAPI itself doesn't need osmium/shapely.
    import osmium
    from shapely.geometry import LineString as ShapeLine
    from shapely.geometry import box

    output.parent.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC)
    counts: Counter = Counter()
    coverage: Counter = Counter()
    region = box(*BOUNDS)
    temporary = output.with_suffix(output.suffix + ".tmp")

    class Exporter(osmium.SimpleHandler):
        def write(self, obj, geometry, node_ids):
            tags = {tag.k: tag.v for tag in obj.tags if tag.k in TAG_KEYS}
            kind = "node" if isinstance(geometry, Point) else "way"
            identifier = f"{kind}/{obj.id}"
            facts = extract_facts(tags, identifier, obj.timestamp, retrieved_at)
            feature = RouteDataFeature(
                id=f"osm/{identifier}",
                geometry=geometry,
                properties=RouteDataProperties(
                    node_ids=node_ids, tags=tags, facts=facts
                ),
            )
            stream.write(feature.model_dump_json() + "\n")
            counts[kind] += 1
            for fact in facts:
                if fact.value is not None:
                    coverage[fact.attribute] += 1
            if tags.get("highway") == "steps":
                counts["stairs"] += 1
            if tags.get("lit") == "no":
                counts["unlit"] += 1

        def node(self, node):
            if not node.location.valid():
                return
            lon, lat = node.location.lon, node.location.lat
            if not (BOUNDS[0] <= lon <= BOUNDS[2] and BOUNDS[1] <= lat <= BOUNDS[3]):
                return
            tags = dict(node.tags)
            if (
                tags.get("barrier") in {"kerb", "step"}
                or "kerb" in tags
                or any(
                    k in tags
                    for k in ("kerb:height", "step_count", "ramp:wheelchair", "lit")
                )
            ):
                self.write(node, Point(type="Point", coordinates=(lon, lat)), [node.id])

        def way(self, way):
            tags = dict(way.tags)
            if tags.get("highway") not in HIGHWAYS or tags.get("area") == "yes":
                return
            if tags.get("foot") in {"no", "private"}:
                return
            if tags.get("access") in {"no", "private"} and tags.get("foot") not in {
                "yes",
                "designated",
                "permissive",
            }:
                return
            if any(not n.location.valid() for n in way.nodes):
                counts["skipped_missing_geometry"] += 1
                return
            coordinates = [(n.lon, n.lat) for n in way.nodes]
            if len(coordinates) < 2 or not ShapeLine(coordinates).intersects(region):
                return
            self.write(
                way,
                LineString(type="LineString", coordinates=coordinates),
                [n.ref for n in way.nodes],
            )

    try:
        with temporary.open("w", encoding="utf-8") as stream:
            Exporter().apply_file(str(pbf), locations=True, idx="flex_mem")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    manifest = {
        "generated_at": retrieved_at.isoformat(),
        "input": str(pbf),
        "bounds": BOUNDS,
        "counts": dict(counts),
        "known_facts": dict(coverage),
        "license": "ODbL",
        "attribution": "© OpenStreetMap contributors",
        "source_url": "https://www.openstreetmap.org/copyright",
        "warnings": [
            "Obszar jest prostokątem, nie granicą administracyjną Krakowa.",
            "OSM nie zapewnia kompletności; wszystkie pobrane fakty wymagają weryfikacji.",
            "Sieć jest materiałem wejściowym; nie jest gotową trasą ani gwarancją dostępu pieszego.",
        ],
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/Cracow.osm.pbf"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/routes/network.geojsonl")
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Refresh the BBBike Kraków extract first.",
    )
    args = parser.parse_args()
    if args.download:
        args.input.parent.mkdir(parents=True, exist_ok=True)
        # Replace the last good input only after a complete, parseable download.
        import osmium

        with TemporaryDirectory(dir=args.input.parent) as directory:
            downloaded = Path(directory) / "download.osm.pbf"
            with (
                urlopen(DOWNLOAD_URL, timeout=120) as response,
                downloaded.open("wb") as target,
            ):
                while chunk := response.read(1024 * 1024):
                    target.write(chunk)
            osmium.SimpleHandler().apply_file(str(downloaded))
            downloaded.replace(args.input)
    print(
        json.dumps(export_routes(args.input, args.output), ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
