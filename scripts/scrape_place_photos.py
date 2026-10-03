"""Import licensed Commons photo URLs and attribution for OSM/Wikidata-linked places."""

import argparse
import hashlib
import json
import re
import sqlite3
import time
from collections import defaultdict
from contextlib import closing
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlencode

from hackyeah.place_enrichment import ensure_schema, import_records
from scripts.scrape_public_places import ROOT, fetch


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, value):
        self.parts.append(value)


def plain(value: str) -> str:
    parser = PlainText()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())


def photo_data(page: dict) -> dict | None:
    infos = page.get("imageinfo", [])
    if not infos:
        return None
    info = infos[0]
    if info.get("mime") not in {"image/jpeg", "image/png", "image/webp"}:
        return None
    meta = info.get("extmetadata", {})
    license_name = plain(meta.get("LicenseShortName", {}).get("value", ""))
    license_url = meta.get("LicenseUrl", {}).get("value", "")
    if license_url.startswith("//"):
        license_url = "https:" + license_url
    # Commons contains some non-free/restricted material: only explicit reusable licenses here.
    if not (
        re.fullmatch(
            r"CC BY(?:-SA)? [1-4]\.0(?: [a-z-]+)?|CC BY(?:-SA)? 2\.5(?: [a-z-]+)?|CC0|Public domain",
            license_name,
            re.I,
        )
    ):
        return None
    artist = plain(meta.get("Artist", {}).get("value", ""))
    if not artist:
        return None
    return {
        "url": info.get("thumburl") or info["url"],
        "original_url": info["url"],
        "source_url": info["descriptionurl"],
        "title": page["title"].removeprefix("File:"),
        "author": artist,
        "credit": plain(meta.get("Credit", {}).get("value", "")),
        "license": license_name,
        "license_url": license_url or None,
        "description": plain(meta.get("ImageDescription", {}).get("value", "")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/krakow.sqlite3")
    parser.add_argument("--raw", type=Path, default=ROOT / "data/raw/enrichment")
    parser.add_argument("--output", type=Path, default=ROOT / "data/place-photos.json")
    parser.add_argument("--cached", action="store_true")
    parser.add_argument("--snapshot-only", action="store_true")
    args = parser.parse_args()
    files = defaultdict(set)
    with closing(
        sqlite3.connect(args.database.resolve().as_uri() + "?mode=rw", uri=True)
    ) as db:
        ensure_schema(db)
        for place_id, tags_json in db.execute(
            "SELECT p.id, o.tags_json FROM places p JOIN osm_objects o ON o.id=p.id"
        ):
            tags = json.loads(tags_json)
            value = tags.get("wikimedia_commons", "")
            if value.startswith("File:"):
                files[value].add(place_id)
            image = tags.get("image", "")
            if image.startswith("https://commons.wikimedia.org/wiki/File:"):
                files[unquote(image.split("/wiki/", 1)[1])].add(place_id)
        for place_id, raw in db.execute(
            "SELECT place_id, data_json FROM external_place_data WHERE source='wikidata' AND place_id IS NOT NULL"
        ):
            data = json.loads(raw)
            names = (
                [data["image_filename"]]
                if data.get("image_filename")
                else data.get("image_filename_values", [])
            )
            for name in names:
                if isinstance(name, str):
                    files["File:" + name].add(place_id)
    titles = sorted(files)
    records, failed = [], []
    for offset in range(0, len(titles), 20):
        batch = titles[offset : offset + 20]
        key = hashlib.sha256("|".join(batch).encode()).hexdigest()[:16]
        cache = args.raw / f"commons-{key}.json"
        url = "https://commons.wikimedia.org/w/api.php?" + urlencode(
            {
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "titles": "|".join(batch),
                "iiprop": "url|extmetadata|mime",
                "iiurlwidth": 960,
                "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|Credit|ImageDescription",
                "iiextmetadatalanguage": "pl",
                "redirects": 1,
            }
        )
        try:
            response = json.loads(fetch(url, cache, args.cached))
            query = response["query"]
            aliases = {
                entry["from"]: entry["to"]
                for name in ("normalized", "redirects")
                for entry in query.get(name, [])
            }
            targets = defaultdict(set)
            for title in batch:
                target, visited = title, set()
                while target in aliases and target not in visited:
                    visited.add(target)
                    target = aliases[target]
                targets[target].update(files[title])
            fetched = []
            for page in query["pages"].values():
                photo = photo_data(page)
                if not photo:
                    continue
                for place_id in targets[page["title"]]:
                    fetched.append(
                        {
                            "source": "commons",
                            "source_id": str(page["pageid"]) + ":" + place_id,
                            "place_id": place_id,
                            "match_method": "osm_or_wikidata_image",
                            "source_url": photo["source_url"],
                            "license": photo["license"],
                            "retrieved_at": datetime.fromtimestamp(
                                cache.stat().st_mtime, UTC
                            ).isoformat(),
                            "data": {"photo": photo},
                        }
                    )
            if not args.snapshot_only:
                import_records(args.database, fetched)
            records.extend(fetched)
            print(
                f"Zdjęcia: {len(records)}; sprawdzone pliki: {offset + len(batch)}/{len(titles)}",
                flush=True,
            )
        except (OSError, ValueError, KeyError) as error:
            failed.append({"offset": offset, "error": str(error)})
            print(f"Błąd Commons: {error}", flush=True)
        time.sleep(1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    part = args.output.with_suffix(".part")
    part.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    part.replace(args.output)
    summary = {
        "photos": len(records),
        "places": len({r["place_id"] for r in records}),
        "failures": failed,
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
