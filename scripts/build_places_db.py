"""Rebuild OSM places in SQLite, preserving temporary and backend data."""

import argparse
import json
import math
import re
import sqlite3
import tempfile
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import osmium
from shapely import STRtree, from_wkt, make_valid
from shapely.geometry import LineString, Point, Polygon, box, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize_full, unary_union

from hackyeah.database import preserve_backend_data
from hackyeah.temporary_store import preserve_temporary_data
from scripts.download_osm import ROOT, sha256

CATEGORIES = {
    "hotel": "Hotele",
    "museum": "Muzea",
    "government": "Urzędy",
    "grocery": "Sklepy spożywcze",
    "post_office": "Poczty",
    "bank": "Banki",
    "garden": "Ogrody",
    "historic": "Zabytki",
    "viewpoint": "Punkty widokowe",
    "library": "Biblioteki",
    "cinema": "Kina",
    "theatre": "Teatry",
    "community_centre": "Domy kultury",
    "senior_club": "Kluby seniora",
}
FIELDS = {
    "steps_count": ("Liczba stopni wejściowych", "count"),
    "threshold_height_cm": ("Wysokość progu", "cm"),
    "elevator_available": ("Winda", None),
    "entrance_width_cm": ("Szerokość wejścia", "cm"),
    "accessible_toilet": ("Toaleta dostosowana", None),
    "wheelchair": ("Ogólna ocena wheelchair", None),
    "wheelchair_description": ("Opis dostępności na wózku", None),
    "toilet_wheelchair": ("Ocena dostępności toalety (także limited)", None),
    "toilets_available": ("Obecność toalety", None),
    "stairs_present": ("Obecność schodów", None),
    "entrance_step_height_cm": ("Wysokość stopnia wejściowego (nie progu)", "cm"),
    "ramp_available": ("Podjazd dla wózków", None),
    "surface": ("Nawierzchnia", None),
    "slope_percent": ("Nachylenie", "percent"),
    "rest_area_available": ("Miejsce odpoczynku", None),
    "distance_without_rest_m": ("Odległość bez odpoczynku", "m"),
    "automatic_door": ("Automatyczne drzwi wejściowe", None),
    "tactile_paving": ("Nawierzchnia dotykowa", None),
    "hearing_loop": ("Pętla indukcyjna", None),
    "blind_description": ("Opis dla osób niewidomych", None),
    "deaf_description": ("Opis dla osób niesłyszących", None),
    "tactile_writing_braille": ("Oznaczenia Braille'a", None),
}


@dataclass
class OSMObject:
    id: str
    osm_type: str
    osm_id: int
    tags: dict[str, str]
    geometry: BaseGeometry
    modified_at: str | None = None
    version: int | None = None


@dataclass
class Evidence:
    attribute: str
    value: object
    object_id: str
    tag_key: str
    raw_value: str
    scope: str
    method: str = "tag"


def classify(tags: dict[str, str]) -> list[str]:
    categories = []
    tourism, amenity = tags.get("tourism"), tags.get("amenity")
    if tourism in {"hotel", "museum", "viewpoint"}:
        categories.append(tourism)
    if amenity in {"post_office", "bank", "library", "cinema", "theatre"}:
        categories.append(amenity)
    if tags.get("office") == "government" or amenity == "townhall":
        categories.append("government")
    if tags.get("shop") in {"supermarket", "convenience", "grocery", "greengrocer"}:
        categories.append("grocery")
    if tags.get("leisure") == "garden":
        categories.append("garden")
    if tags.get("historic") not in {None, "no"} or tags.get("heritage") not in {
        None,
        "no",
    }:
        categories.append("historic")
    senior_audience = "senior" in tags.get("community_centre:for", "").split(";")
    senior_facility = tags.get("social_facility") in {
        "day_care",
        "outreach",
        "community_centre",
    } and "senior" in tags.get("social_facility:for", "").split(";")
    senior_name = re.search(
        r"(?:klub(?:u)? senior|centrum (?:aktywności|aktywizacji) senior)",
        tags.get("name", ""),
        re.I,
    )
    club = tags.get("club") in {"senior", "seniors"}
    if (
        club
        or senior_facility
        or senior_audience
        or (
            senior_name
            and (
                amenity in {"community_centre", "social_centre", "social_facility"}
                or "club" in tags
            )
        )
    ):
        categories.append("senior_club")
    if (
        amenity in {"community_centre", "arts_centre", "social_centre"}
        and "senior_club" not in categories
    ):
        categories.append("community_centre")
    return categories


def is_feature(tags: dict[str, str]) -> bool:
    return (
        tags.get("entrance") not in {None, "no"}
        or tags.get("highway") in {"steps", "elevator"}
        or tags.get("amenity") in {"toilets", "bench"}
        or tags.get("leisure") == "picnic_table"
    )


def load_boundary(path: Path) -> BaseGeometry:
    payload = json.loads(path.read_text())
    elements = payload["elements"]
    relation = next(
        e for e in elements if e["type"] == "relation" and e["id"] == 449696
    )
    if (
        relation["tags"].get("boundary") != "administrative"
        or relation["tags"].get("name") != "Kraków"
    ):
        raise ValueError("Źródło nie zawiera granicy administracyjnej Krakowa.")
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in elements if e["type"] == "node"}
    ways = {e["id"]: e["nodes"] for e in elements if e["type"] == "way"}
    rings = {}
    for role in ("outer", "inner"):
        lines = [
            LineString([nodes[n] for n in ways[m["ref"]]])
            for m in relation["members"]
            if m["type"] == "way" and m["role"] == role
        ]
        polygons, cuts, dangles, invalid = polygonize_full(lines)
        if not (cuts.is_empty and dangles.is_empty and invalid.is_empty):
            raise ValueError("Niekompletna geometria granicy Krakowa.")
        rings[role] = unary_union(polygons)
    boundary = rings["outer"].difference(rings["inner"])
    if boundary.is_empty or not boundary.is_valid:
        raise ValueError("Niepoprawna granica Krakowa.")
    return boundary


def read_extract(
    path: Path, boundary: BaseGeometry
) -> tuple[dict[str, OSMObject], dict]:
    objects: dict[str, OSMObject] = {}
    stats: Counter = Counter()
    factory = osmium.geom.WKTFactory()
    with osmium.io.Reader(str(path)) as reader:
        snapshot_at = reader.header().get("osmosis_replication_timestamp") or None
        extent = reader.header().box()
        extract_bounds = (
            [
                extent.bottom_left.lon,
                extent.bottom_left.lat,
                extent.top_right.lon,
                extent.top_right.lat,
            ]
            if extent.valid()
            else None
        )
    if extract_bounds and not box(*extract_bounds).covers(boundary):
        raise ValueError(
            "Wyciąg OSM nie obejmuje całej granicy Krakowa; wybierz pełny wyciąg Małopolski."
        )
    west, south, east, north = boundary.bounds
    keys = [
        "tourism",
        "amenity",
        "shop",
        "office",
        "leisure",
        "historic",
        "heritage",
        "club",
        "building",
        "entrance",
        "highway",
    ]
    processor = (
        osmium.FileProcessor(str(path))
        .with_locations()
        .with_areas()
        .with_filter(osmium.filter.KeyFilter(*keys))
    )
    for obj in processor:
        tags = dict(obj.tags)
        wanted = (
            bool(classify(tags))
            or is_feature(tags)
            or tags.get("building") not in {None, "no"}
        )
        if not wanted:
            continue
        geometry = None
        if obj.is_node():
            osm_type, osm_id = "node", obj.id
            if obj.location.valid():
                geometry = Point(obj.lon, obj.lat)
        elif obj.is_way():
            osm_type, osm_id = "way", obj.id
            coordinates = [(n.lon, n.lat) for n in obj.nodes if n.location.valid()]
            if len(coordinates) != len(obj.nodes):
                stats["incomplete_geometries"] += 1
                continue
            if (
                len(coordinates) >= 4
                and coordinates[0] == coordinates[-1]
                and tags.get("area") != "no"
                and tags.get("highway") not in {"steps", "elevator"}
            ):
                geometry = Polygon(coordinates)
            elif len(coordinates) >= 2:
                geometry = LineString(coordinates)
        elif obj.is_area():
            osm_type, osm_id = "way" if obj.from_way() else "relation", obj.orig_id()
            try:
                geometry = from_wkt(factory.create_multipolygon(obj))
            except RuntimeError:
                stats["incomplete_geometries"] += 1
                continue
        else:
            # Non-area relations do not have an unambiguous place geometry.
            if classify(tags):
                stats["relations_without_area_geometry"] += 1
            continue
        if geometry is None or geometry.is_empty:
            stats["incomplete_geometries"] += 1
            continue
        minx, miny, maxx, maxy = geometry.bounds
        if maxx < west or minx > east or maxy < south or miny > north:
            continue
        if not geometry.is_valid:
            geometry = make_valid(geometry)
            stats["repaired_geometries"] += 1
        key = f"{osm_type}/{osm_id}"
        objects[key] = OSMObject(
            key,
            osm_type,
            osm_id,
            tags,
            geometry,
            obj.timestamp.isoformat() if obj.version else None,
            obj.version or None,
        )
    return objects, {
        "snapshot_at": snapshot_at,
        "extract_bounds": extract_bounds,
        **stats,
    }


def length_cm(value: str, default_unit: str | None = "m") -> float | None:
    match = re.fullmatch(
        r"\s*(\d+(?:[.,]\d+)?)\s*(mm|cm|m|ft|in|\")?\s*", value.lower()
    )
    if not match:
        return None
    amount = float(match[1].replace(",", "."))
    unit = match[2] or default_unit
    factors = {"mm": 0.1, "cm": 1.0, "m": 100.0, "ft": 30.48, "in": 2.54, '"': 2.54}
    if unit is None:
        return 0.0 if amount == 0 else None
    result = amount * factors[unit]
    return round(result, 4) if math.isfinite(result) else None


def boolean(value: str) -> bool | None:
    return {"yes": True, "no": False, "designated": True}.get(value)


def observations(obj: OSMObject, scope: str = "place") -> list[Evidence]:
    tags = obj.tags
    values = []

    def add(attribute: str, tag: str, value: object, method: str = "tag") -> None:
        if value is not None:
            values.append(
                Evidence(attribute, value, obj.id, tag, tags[tag], scope, method)
            )

    def tag_bool(attribute: str, tag: str) -> None:
        if tag in tags:
            add(attribute, tag, boolean(tags[tag]))

    entrance = tags.get("entrance") not in {None, "no"}
    if scope in {"place", "entrance_on_outline"}:
        for tag in (
            "entrance:step_count",
            "step_count" if entrance else "entrance:step_count",
        ):
            if tag in tags and re.fullmatch(r"\d+", tags[tag]):
                if not any(v.tag_key == tag for v in values):
                    add("steps_count", tag, int(tags[tag]))
                    if int(tags[tag]) > 0:
                        add("stairs_present", tag, True)
        for tag in ("entrance:width", "wheelchair:entrance_width") + (
            ("door:width", "width", "maxwidth:physical") if entrance else ()
        ):
            if tag in tags:
                add("entrance_width_cm", tag, length_cm(tags[tag]))
        for tag in (
            "entrance:threshold:height",
            "door:threshold:height",
            "threshold:height",
        ):
            if tag in tags:
                add("threshold_height_cm", tag, length_cm(tags[tag], default_unit=None))
        if "wheelchair:step_height" in tags:
            add(
                "entrance_step_height_cm",
                "wheelchair:step_height",
                length_cm(tags["wheelchair:step_height"], default_unit=None),
            )
        if entrance:
            tag_bool("automatic_door", "automatic_door")
            if "door" in tags and tags["door"] == "automatic":
                add("automatic_door", "door", True)
        tag_bool("ramp_available", "ramp:wheelchair")
    if scope == "place":
        if tags.get("wheelchair") in {"yes", "no", "limited", "designated"}:
            add("wheelchair", "wheelchair", tags["wheelchair"])
        for attribute, keys in {
            "wheelchair_description": (
                "wheelchair:description:pl",
                "wheelchair:description",
                "wheelchair:description:en",
            ),
            "blind_description": ("blind:description:pl", "blind:description"),
            "deaf_description": ("deaf:description:pl", "deaf:description"),
        }.items():
            for tag in keys:
                if tags.get(tag):
                    add(attribute, tag, tags[tag])
                    break
        for tag in (
            "wheelchair:description",
            "wheelchair:description:en",
            "wheelchair:description:pl",
        ):
            description = tags.get(tag, "")
            match = re.fullmatch(
                r"\s*(\d+)\s+steps?\s+at\s+(?:the\s+)?entrance[.!]?\s*",
                description,
                re.I,
            )
            if match:
                add("steps_count", tag, int(match[1]), "explicit_description")
                if int(match[1]) > 0:
                    add("stairs_present", tag, True, "explicit_description")
        if "toilets:wheelchair" in tags:
            tag_bool("accessible_toilet", "toilets:wheelchair")
            if tags["toilets:wheelchair"] in {"yes", "no", "limited", "designated"}:
                add(
                    "toilet_wheelchair",
                    "toilets:wheelchair",
                    tags["toilets:wheelchair"],
                )
        tag_bool("toilets_available", "toilets")
        if tags.get("toilets") == "no":
            add("accessible_toilet", "toilets", False)
        for tag in ("elevator", "wheelchair:elevator"):
            tag_bool("elevator_available", tag)
        if "surface" in tags:
            add("surface", "surface", tags["surface"])
        if "incline" in tags:
            match = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(%|°)", tags["incline"])
            if match:
                slope = abs(float(match[1]))
                if match[2] == "°":
                    slope = (
                        100 * math.tan(math.radians(slope)) if slope < 90 else math.inf
                    )
                if math.isfinite(slope):
                    add("slope_percent", "incline", round(slope, 4))
        tag_bool("tactile_paving", "tactile_paving")
        tag_bool("hearing_loop", "hearing_loop")
        for tag in ("tactile_writing:braille:pl", "tactile_writing:braille"):
            tag_bool("tactile_writing_braille", tag)
    if scope in {"place", "within_place"}:
        if tags.get("highway") == "elevator":
            add("elevator_available", "highway", True, "mapped_feature")
        if tags.get("highway") == "steps":
            add("stairs_present", "highway", True, "mapped_feature")
        if tags.get("amenity") == "toilets":
            add("toilets_available", "amenity", True, "mapped_feature")
            tag_bool("accessible_toilet", "wheelchair")
        if tags.get("amenity") == "bench" or tags.get("leisure") == "picnic_table":
            tag = "amenity" if tags.get("amenity") == "bench" else "leisure"
            add("rest_area_available", tag, True, "mapped_feature")
    return values


def consolidate(evidence: list[Evidence]) -> tuple[str | None, str]:
    encoded = {
        json.dumps(e.value, ensure_ascii=False, sort_keys=True, allow_nan=False)
        for e in evidence
    }
    if not encoded:
        return None, "missing"
    if len(encoded) > 1:
        return None, "conflicting"
    return encoded.pop(), "pending_verification"


def link_features(
    place: OSMObject, features: list[OSMObject], tree: STRtree
) -> list[tuple[OSMObject, str]]:
    if place.geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        return []
    links = []
    for index in tree.query(place.geometry):
        feature = features[int(index)]
        if feature.id == place.id or not place.geometry.covers(feature.geometry):
            continue
        if feature.tags.get("entrance") not in {None, "no"}:
            if (
                feature.geometry.geom_type == "Point"
                and place.geometry.boundary.distance(feature.geometry) < 1e-9
            ):
                links.append((feature, "entrance_on_outline"))
        else:
            links.append((feature, "within_place"))
    return links


def build_database(source: Path, boundary_path: Path, destination: Path) -> dict:
    boundary = load_boundary(boundary_path)
    print("Odczyt geometrii i tagów OSM...", flush=True)
    objects, stats = read_extract(source, boundary)
    places = [
        o
        for o in objects.values()
        if classify(o.tags) and boundary.covers(o.geometry.representative_point())
    ]
    if not places:
        raise ValueError(
            "Nie znaleziono miejsc w granicach Krakowa; baza nie zostanie zastąpiona."
        )
    features = [
        o
        for o in objects.values()
        if is_feature(o.tags) and boundary.intersects(o.geometry)
    ]
    buildings = [
        o
        for o in objects.values()
        if o.tags.get("building") not in {None, "no"}
        and o.geometry.geom_type in {"Polygon", "MultiPolygon"}
        and boundary.intersects(o.geometry)
    ]
    feature_tree = STRtree([o.geometry for o in features])
    building_tree = STRtree([o.geometry for o in buildings])
    print(f"Miejsca: {len(places)}; obiekty kontekstowe: {len(features)}.", flush=True)
    manifest_path = source.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest = {
        name: manifest[name]
        for name in (source.name, boundary_path.name)
        if name in manifest
    }
    metadata = {
        "schema_version": 1,
        "imported_at": datetime.now(UTC).isoformat(),
        "source": "OpenStreetMap",
        "license": "ODbL",
        "attribution": "© OpenStreetMap contributors",
        "source_manifest": manifest,
        "extract_filename": source.name,
        "extract_sha256": sha256(source),
        "boundary_sha256": sha256(boundary_path),
        "boundary_relation": 449696,
        "extract_stats": stats,
        "place_count": len(places),
        "location_rule": "OSM geometry representative point inside administrative boundary",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, suffix=".sqlite3", delete=False
    ) as file:
        temporary = Path(file.name)
    try:
        with closing(sqlite3.connect(temporary)) as db, db:
            db.executescript((Path(__file__).parent / "schema.sql").read_text())
            db.executemany("INSERT INTO categories VALUES (?, ?)", CATEGORIES.items())
            db.executemany(
                "INSERT INTO metadata VALUES (?, ?)",
                [(k, json.dumps(v, ensure_ascii=False)) for k, v in metadata.items()],
            )
            inserted = set()

            def store_object(obj: OSMObject) -> None:
                if obj.id in inserted:
                    return
                db.execute(
                    "INSERT INTO osm_objects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        obj.id,
                        obj.osm_type,
                        obj.osm_id,
                        f"https://www.openstreetmap.org/{obj.id}",
                        "ODbL",
                        obj.modified_at,
                        obj.version,
                        json.dumps(obj.tags, ensure_ascii=False),
                        json.dumps(mapping(obj.geometry)),
                    ),
                )
                inserted.add(obj.id)

            for place in places:
                store_object(place)
                tags = place.tags
                point = place.geometry.representative_point()
                db.execute(
                    "INSERT INTO places VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        place.id,
                        tags.get("name") or tags.get("name:pl") or tags.get("brand"),
                        point.y,
                        point.x,
                        tags.get("addr:street") or tags.get("addr:place"),
                        tags.get("addr:housenumber"),
                        tags.get("addr:postcode"),
                        tags.get("addr:city"),
                        tags.get("addr:unit"),
                        tags.get("website") or tags.get("contact:website"),
                        tags.get("phone") or tags.get("contact:phone"),
                        tags.get("opening_hours"),
                        tags.get("operator"),
                        tags.get("access"),
                    ),
                )
                db.executemany(
                    "INSERT INTO place_categories VALUES (?, ?)",
                    [(place.id, category) for category in classify(tags)],
                )
                links = link_features(place, features, feature_tree)
                # A building containing a POI does not establish ownership of its entrance/toilet.
                if place.geometry.geom_type == "Point":
                    candidates = [
                        buildings[int(i)]
                        for i in building_tree.query(place.geometry)
                        if buildings[int(i)].geometry.covers(place.geometry)
                    ]
                    if candidates:
                        building = min(candidates, key=lambda o: o.geometry.area)
                        links = [
                            (feature, "building_context")
                            for feature, _ in link_features(
                                building, features, feature_tree
                            )
                            if feature.id != place.id
                        ]
                evidence = observations(place)
                for feature, scope in links:
                    store_object(feature)
                    db.execute(
                        "INSERT OR IGNORE INTO place_features VALUES (?, ?, ?)",
                        (place.id, feature.id, scope),
                    )
                    if (
                        scope != "building_context"
                        and feature.tags.get("access") not in {"private", "no"}
                        and feature.tags.get("entrance")
                        not in {"emergency", "exit", "service"}
                    ):
                        evidence.extend(observations(feature, scope))
                for attribute, (_, unit) in FIELDS.items():
                    facts = [e for e in evidence if e.attribute == attribute]
                    value, reason = consolidate(facts)
                    db.execute(
                        "INSERT INTO accessibility_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            place.id,
                            attribute,
                            value,
                            unit,
                            "unconfirmed",
                            reason,
                            None,
                            None,
                        ),
                    )
                    for e in facts:
                        db.execute(
                            "INSERT OR IGNORE INTO fact_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                place.id,
                                attribute,
                                e.object_id,
                                e.tag_key,
                                e.raw_value,
                                json.dumps(e.value, ensure_ascii=False),
                                e.scope,
                                e.method,
                            ),
                        )
            preserve_temporary_data(destination, db)
            preserve_backend_data(destination, db)
            if (
                db.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or db.execute("PRAGMA foreign_key_check").fetchall()
            ):
                raise ValueError("Weryfikacja spójności bazy nie powiodła się.")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Zapisano {destination}", flush=True)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=ROOT / "data/raw/malopolskie-latest.osm.pbf"
    )
    parser.add_argument(
        "--boundary", type=Path, default=ROOT / "data/raw/krakow-boundary.json"
    )
    parser.add_argument("--database", type=Path, default=ROOT / "data/krakow.sqlite3")
    args = parser.parse_args()
    build_database(args.source, args.boundary, args.database)


if __name__ == "__main__":
    main()
