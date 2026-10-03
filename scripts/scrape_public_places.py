"""Fetch Kraków MSIP/BIP and OSM-linked Wikidata; automatically enrich SQLite."""

import argparse
import json
import re
import sqlite3
import time
import unicodedata
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from hackyeah.place_enrichment import (
    distance_m,
    effective_places,
    ensure_schema,
    import_records,
)

ROOT = Path(__file__).resolve().parents[1]
MSIP = "https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium/"
BIP = "https://www.bip.krakow.pl/?dok_id=83400"
USER_AGENT = "SwojaDroga/0.1 (Krakow public place catalogue)"
LAYERS = {
    "WT_WC_2023": [0],
    "K17_KULTURA": [0],
    "Miejskie_Instytucje_Kultury": [0, 1, 2, 3, 4],
    "WT_OBIEKTY_HOTELOWE_KOH": [0],
    "WT_OBIEKTY_NOCLEGOWE_KON": [0],
    "zabytki_do_pobrania": [0, 1],
    "jestemAKTYWNY": list(range(14)),
}


def fetch(url: str, cache: Path, cached: bool) -> bytes:
    if cached and cache.exists():
        return cache.read_bytes()
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                data = response.read(25_000_001)
            break
        except HTTPError as error:
            if error.code not in {429, 502, 503, 504} or attempt == 2:
                raise
            delay = error.headers.get("Retry-After", "10")
            time.sleep(min(60, max(5, int(delay) if delay.isdigit() else 10)))
        except OSError:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    if len(data) > 25_000_000:
        raise ValueError("Response exceeds 25 MB")
    cache.parent.mkdir(parents=True, exist_ok=True)
    part = cache.with_suffix(cache.suffix + ".part")
    part.write_bytes(data)
    part.replace(cache)
    return data


def normalized(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", (value or "").casefold().replace("ł", "l"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\b(?:ulica|ul|aleja|al|osiedle|os|imienia|im)\b\.?", " ", text)
    return " ".join(re.findall(r"\w+", text))


def match_place(data: dict, places: list[dict]) -> tuple[str | None, str | None]:
    candidates = []
    registry = re.match(
        r"(?:A[-/ ]?)?(\d+)\b", str(data.get("heritage_register", "")), re.I
    )
    for place in places:
        if data.get("lat") is None or data.get("lon") is None:
            continue
        distance = distance_m(place["lat"], place["lon"], data["lat"], data["lon"])
        if distance > 150:
            continue
        name, other = normalized(data.get("name")), normalized(place.get("name"))
        similar = bool(
            name
            and other
            and (name == other or SequenceMatcher(None, name, other).ratio() >= 0.82)
        )
        address_match = bool(
            data.get("street")
            and data.get("housenumber")
            and normalized(data["street"]) == normalized(place.get("street"))
            and normalized(str(data["housenumber"]))
            == normalized(place.get("housenumber"))
        )
        if (
            name
            in {
                "dom",
                "kamienica",
                "hotel",
                "biblioteka",
                "muzeum",
                "budynek",
                "oficyna",
            }
            and not address_match
        ):
            similar = False
        website_match = bool(
            data.get("website")
            and place.get("website")
            and data["website"]
            .rstrip("/")
            .removeprefix("https://")
            .removeprefix("http://")
            .removeprefix("www.")
            == place["website"]
            .rstrip("/")
            .removeprefix("https://")
            .removeprefix("http://")
            .removeprefix("www.")
        )
        local_registry = re.match(
            r"(?:A[-/ ]?)?(\d+)\b", str(place.get("_heritage_register", "")), re.I
        )
        if registry and local_registry and registry[1] == local_registry[1]:
            candidates.append((place["id"], "heritage_register_and_location"))
            continue
        if (
            similar
            and (distance < 60 or address_match)
            or website_match
            and address_match
        ):
            candidates.append(
                (place["id"], "name_and_location" if similar else "website_and_address")
            )
    # Duplicate OSM outlines/points and nearby same-brand outlets need manual reconciliation.
    return candidates[0] if len(candidates) == 1 else (None, None)


def website(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    parsed = urlsplit(value)
    return (
        value
        if parsed.scheme in {"http", "https"}
        and parsed.hostname
        and "." in parsed.hostname
        else None
    )


def msip_data(attrs: dict, geometry: dict) -> dict:
    lower = {k.lower(): v for k, v in attrs.items()}

    def first(*keys):
        return next(
            (lower[k] for k in keys if lower.get(k) not in (None, "", " ")), None
        )

    data = {
        "name": first("ob_nazwa", "name", "nazwa", "user_typol"),
        "street": first("ulica", "street"),
        "housenumber": first("nr_ad_xy", "building", "nr_bud"),
        "postcode": first("kod", "postal_code"),
        "city": first("miasto", "city"),
        "address": first("adres", "adres_cwoh", "user_adres"),
        "website": website(
            first("strona_www", "www_link", "website", "web_adres", "www_txt")
        ),
        "phone": first("nr_tel"),
        "email": first("email"),
        "opening_hours": first("godz_otw"),
        "description": first("opis"),
        "bip": website(first("bip")),
        "capacity": first("mn_liczba", "total_beds"),
        "rooms": first("po_liczba"),
        "stars": first("kat_txt"),
        "heritage_register": first("user_num_1"),
        "inception": first("user_datow"),
        "architect": first("user_autor"),
        "source_updated_at": first("data_akt", "gpt_date", "aktualnosc", "import_d"),
        "raw_attributes": attrs,
    }
    if geometry and "x" in geometry and "y" in geometry:
        data.update(lat=geometry["y"], lon=geometry["x"])
    return {k: v for k, v in data.items() if v is not None and v != ""}


def msip_records(places: list[dict], raw: Path, cached: bool, services=None):
    for service in services or LAYERS:
        layers = LAYERS[service]
        for layer in layers:
            base = f"{MSIP}{service}/MapServer/{layer}"
            # Older ArcGIS layers do not support resultOffset. Fetch IDs, then bounded chunks.
            ids_cache = raw / f"msip-{service}-{layer}-ids.json"
            ids_response = json.loads(
                fetch(
                    base
                    + "/query?"
                    + urlencode({"f": "json", "where": "1=1", "returnIdsOnly": "true"}),
                    ids_cache,
                    cached,
                )
            )
            if "objectIds" not in ids_response:
                raise ValueError(f"MSIP {service}/{layer}: {ids_response}")
            ids = sorted(ids_response["objectIds"] or [])
            for offset in range(0, len(ids), 250):
                params = urlencode(
                    {
                        "f": "json",
                        "objectIds": ",".join(map(str, ids[offset : offset + 250])),
                        "outFields": "*",
                        "outSR": 4326,
                        "returnGeometry": "true",
                    }
                )
                cache = raw / f"msip-{service}-{layer}-{offset}.json"
                response = json.loads(fetch(base + "/query?" + params, cache, cached))
                if (
                    "error" in response
                    or "features" not in response
                    or response.get("exceededTransferLimit")
                ):
                    raise ValueError(
                        f"MSIP {service}/{layer}: incomplete or failed response"
                    )
                records = []
                for feature in response["features"]:
                    attrs = feature["attributes"]
                    data = msip_data(attrs, feature.get("geometry"))
                    key = next(
                        (
                            v
                            for k, v in attrs.items()
                            if k.lower()
                            in {"objectid", "fid", "objectid_12", "esri_oid"}
                        ),
                        None,
                    )
                    if key is None:
                        raise ValueError(f"MSIP missing object ID: {service}/{layer}")
                    place_id, method = match_place(data, places)
                    if service == "WT_WC_2023":
                        data.update(toilet_data(attrs))
                        candidates = [
                            p["id"]
                            for p in places
                            if p.get("_amenity") == "toilets"
                            and "lat" in data
                            and distance_m(p["lat"], p["lon"], data["lat"], data["lon"])
                            < 25
                        ]
                        place_id = candidates[0] if len(candidates) == 1 else None
                        method = "unique_toilet_within_25m" if place_id else None
                    records.append(
                        {
                            "source": "msip",
                            "source_id": f"{service}/{layer}/{key}",
                            "place_id": place_id,
                            "match_method": method,
                            "source_url": base
                            + "/query?"
                            + urlencode(
                                {
                                    "f": "pjson",
                                    "objectIds": key,
                                    "outFields": "*",
                                    "outSR": 4326,
                                }
                            ),
                            "retrieved_at": datetime.fromtimestamp(
                                cache.stat().st_mtime, UTC
                            ).isoformat(),
                            "license": "Gmina Miejska Kraków — publiczne dane MSIP; warunki portalu",
                            "data": data,
                        }
                    )
                yield records
                print(f"MSIP {service}/{layer}: {offset + len(records)}", flush=True)
                time.sleep(0.2)


def toilet_data(attrs: dict) -> dict:
    """Only explicit yes/no claims; conditional accessibility stays in the description."""
    value = str(attrs.get("nplnsprw") or "").strip().casefold()
    observations = []
    affirmative = {
        "tak",
        "tak, po stronie damskiej",
        "tak, po stronie męskiej",
        "tak, oddzielnie",
        "tak, pomiędzy toaletą damską a męską",
    }
    if value in affirmative | {"nie"}:
        observations.append(
            {"attribute": "accessible_toilet", "value": value in affirmative}
        )
    return {
        "name": "Toaleta publiczna — " + str(attrs.get("miejsce") or ""),
        "accessibility_observations": observations,
        "accessibility_summary": "; ".join(
            f"{label}: {attrs[key]}"
            for key, label in (
                ("nplnsprw", "Dostępność"),
                ("rodz_npl", "Dostosowanie"),
                ("status", "Stan"),
                ("uwagi", "Uwagi"),
            )
            if attrs.get(key)
        ),
        "opening_hours": "; ".join(
            str(attrs[k]) for k in ("dni", "godziny", "sezon") if attrs.get(k)
        ),
    }


class LibraryTable(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], [], None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag == "td":
            self.cell = []
        elif tag in {"br", "p"} and self.cell is not None:
            self.cell.append("\n")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append(
                "\n".join(
                    " ".join(line.split())
                    for line in "".join(self.cell).splitlines()
                    if line.strip()
                )
            )
            self.cell = None
        elif tag == "tr" and len(self.row) == 6:
            self.rows.append(self.row)


def library_records(places: list[dict], raw: Path, cached: bool) -> list[dict]:
    cache = raw / "bip-libraries.html"
    doc = LibraryTable()
    doc.feed(fetch(BIP, cache, cached).decode("utf-8"))
    records = []
    for branch, _, address, phone, email, hours in doc.rows:
        number = re.search(r"Filia nr\s*(\d+)", branch, re.I)
        if not number and branch != "BG":
            continue
        # Match branch number only within Biblioteka Kraków, with an address cross-check.
        candidates = []
        for place in places:
            name = place.get("name") or ""
            if "bibliotek" not in name.casefold() or "krak" not in name.casefold():
                continue
            if number and not re.search(
                r"\b(?:nr\.?\s*|filia\s*)" + number[1] + r"\b", name, re.I
            ):
                continue
            if not number and "główn" not in name.casefold():
                continue
            if place.get("housenumber") and not re.search(
                r"(?<!\w)" + re.escape(place["housenumber"]) + r"(?!\w)", address
            ):
                continue
            if (
                place.get("street")
                and normalized(place["street"]).split()[-1]
                not in normalized(address).split()
            ):
                continue
            candidates.append(place["id"])
        records.append(
            {
                "source": "bip_libraries",
                "source_id": number[1] if number else "BG",
                "place_id": candidates[0] if len(candidates) == 1 else None,
                "match_method": "library_branch_and_address"
                if len(candidates) == 1
                else None,
                "source_url": BIP,
                "retrieved_at": datetime.fromtimestamp(
                    cache.stat().st_mtime, UTC
                ).isoformat(),
                "license": "Informacja publiczna — BIP Miasta Krakowa / Biblioteka Kraków",
                "data": {
                    "name": "Biblioteka Kraków — " + branch,
                    "address": address,
                    "phone": phone,
                    "email": email,
                    "opening_hours": hours,
                    "opening_hours_format": "source_text",
                },
            }
        )
    if not records:
        raise ValueError("BIP library table missing; existing data preserved")
    return records


def wikidata_records(db: sqlite3.Connection, raw: Path, cached: bool):
    linked = {}
    for place_id, tags in db.execute(
        "SELECT p.id, o.tags_json FROM places p JOIN osm_objects o ON p.id=o.id"
    ):
        entity = json.loads(tags).get("wikidata", "")
        if re.fullmatch(r"Q[1-9]\d*", entity):
            linked.setdefault(entity, []).append(place_id)
    ids = sorted(linked)
    for start in range(0, len(ids), 50):
        batch = ids[start : start + 50]
        params = urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "format": "json",
                "props": "labels|descriptions|claims|sitelinks",
                "languages": "pl|en",
                "sitefilter": "plwiki|enwiki",
            }
        )
        # Include IDs in cache key so changed ordering cannot import the wrong cached batch.
        import hashlib

        key = hashlib.sha256("|".join(batch).encode()).hexdigest()[:16]
        cache = raw / f"wikidata-{key}.json"
        response = json.loads(
            fetch("https://www.wikidata.org/w/api.php?" + params, cache, cached)
        )
        if "entities" not in response:
            raise ValueError(f"Wikidata: {response.get('error', 'missing entities')}")
        records = []
        for entity_id, entity in response["entities"].items():
            if "missing" in entity or entity_id not in linked:
                continue
            claims = entity.get("claims", {})

            def values(prop, claims=claims):
                return [
                    claim["mainsnak"]["datavalue"]["value"]
                    for claim in claims.get(prop, [])
                    if claim.get("rank") != "deprecated"
                    and "datavalue" in claim.get("mainsnak", {})
                    and "P582" not in claim.get("qualifiers", {})
                ]

            if any(isinstance(x, dict) and x.get("id") == "Q5" for x in values("P31")):
                continue  # A gravestone's erroneous person link must not become place details.
            data = {"wikidata": entity_id}
            for attr, key in (("name", "labels"), ("description", "descriptions")):
                value = entity.get(key, {}).get("pl") or entity.get(key, {}).get("en")
                if value:
                    data[attr] = value["value"]
            for prop, attr in {
                "P856": "website",
                "P1329": "phone",
                "P968": "email",
                "P18": "image_filename",
                "P1435": "heritage_status",
                "P1619": "official_opening_date",
                "P571": "inception",
                "P84": "architect",
                "P3723": "heritage_register",
                "P6375": "street_address",
            }.items():
                found = values(prop)
                if len(found) == 1:
                    data[attr] = found[0]
                elif found:
                    data[attr + "_values"] = found
            if "website" in data:
                data["website"] = website(data["website"])
            for site, entry in entity.get("sitelinks", {}).items():
                data[site] = entry.get("url") or entry.get("title")
            for place_id in linked[entity_id]:
                records.append(
                    {
                        "source": "wikidata",
                        "source_id": entity_id + ":" + place_id,
                        "place_id": place_id,
                        "match_method": "osm_wikidata_id",
                        "source_url": "https://www.wikidata.org/wiki/" + entity_id,
                        "retrieved_at": datetime.fromtimestamp(
                            cache.stat().st_mtime, UTC
                        ).isoformat(),
                        "license": "CC0",
                        "data": data,
                    }
                )
        yield records
        time.sleep(1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/krakow.sqlite3")
    parser.add_argument("--output", type=Path, default=ROOT / "data/public-places.json")
    parser.add_argument("--raw", type=Path, default=ROOT / "data/raw/enrichment")
    parser.add_argument(
        "--source", choices=["msip", "bip", "wikidata", "toilets"], action="append"
    )
    parser.add_argument("--cached", action="store_true")
    parser.add_argument("--snapshot-only", action="store_true")
    args = parser.parse_args()
    records, failures = [], []
    with closing(
        sqlite3.connect(args.database.resolve().as_uri() + "?mode=rw", uri=True)
    ) as db:
        ensure_schema(db)
        places = effective_places(db)
        tags = {
            row[0]: json.loads(row[1])
            for row in db.execute("SELECT id, tags_json FROM osm_objects")
        }
        for place in places:
            place["_heritage_register"] = tags.get(place["id"], {}).get("ref:nid", "")
            place["_amenity"] = tags.get(place["id"], {}).get("amenity")
        sources = [
            item
            for source in args.source or ["msip", "bip", "wikidata"]
            for item in (
                list(LAYERS)
                if source == "msip"
                else ["WT_WC_2023"]
                if source == "toilets"
                else [source]
            )
        ]
        for source in sources:
            try:
                batches = (
                    msip_records(places, args.raw, args.cached, [source])
                    if source in LAYERS
                    else [library_records(places, args.raw, args.cached)]
                    if source == "bip"
                    else wikidata_records(db, args.raw, args.cached)
                )
                for batch in batches:
                    if not args.snapshot_only:
                        import_records(args.database, batch)
                    records.extend(batch)
                print(f"Ukończono {source}", flush=True)
            except (OSError, ValueError) as error:
                failures.append({"source": source, "error": str(error)})
                print(f"Błąd {source}: {error}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    part = args.output.with_suffix(".part")
    part.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    part.replace(args.output)
    summary = {
        "records": len(records),
        "matched_places": len({r["place_id"] for r in records if r.get("place_id")}),
        "sources": dict(Counter(r["source"] for r in records)),
        "failures": failures,
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
