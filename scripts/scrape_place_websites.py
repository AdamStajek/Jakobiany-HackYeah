"""Scrape place websites and update SQLite; retain a JSON snapshot for replay."""

import argparse
import json
import re
import socket
import sqlite3
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from ipaddress import ip_address
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = (
    "SwojaDroga/0.1 (Krakow accessibility research; contact: open-data project)"
)
MAX_BYTES = 1_000_000


def public_url(url: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        return all(
            ip_address(info[4][0]).is_global
            for info in socket.getaddrinfo(
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        )
    except (OSError, ValueError):
        return False


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        if not public_url(new_url):
            raise URLError("Redirect to a non-public host refused")
        return super().redirect_request(request, fp, code, message, headers, new_url)


class PlacePage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.jsonld = []
        self.title = []
        self._title = False
        self._jsonld = False
        self._script = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key and attrs.get("content"):
                self.meta[key] = attrs["content"].strip()
        elif tag == "title":
            self._title = True
        elif tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self._jsonld = True
            self._script = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._title = False
        elif tag == "script" and self._jsonld:
            self.jsonld.append("".join(self._script))
            self._jsonld = False

    def handle_data(self, data):
        if self._title:
            self.title.append(data)
        if self._jsonld:
            self._script.append(data)


def structured_values(
    doc: PlacePage, place: dict | None = None, shared: bool = False
) -> dict:
    # Never merge fields from unrelated JSON-LD entities (publisher, branch, event).
    candidates = []

    def visit(value):
        if isinstance(value, dict):
            types = value.get("@type", [])
            types = [types] if isinstance(types, str) else types
            if any(
                key in value
                for key in (
                    "openingHours",
                    "openingHoursSpecification",
                    "telephone",
                    "address",
                    "geo",
                )
            ) and not set(types or []) & {
                "Person",
                "Event",
                "WebSite",
                "WebPage",
                "BreadcrumbList",
            }:
                candidates.append(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for script in doc.jsonld:
        try:
            visit(json.loads(script))
        except (json.JSONDecodeError, RecursionError):
            continue
    selected = []
    for value in candidates:
        if place:
            geo = value.get("geo") or {}
            address = value.get("address") or {}
            try:
                from hackyeah.place_enrichment import distance_m

                nearby = (
                    distance_m(
                        place["lat"],
                        place["lon"],
                        float(geo["latitude"]),
                        float(geo["longitude"]),
                    )
                    < 150
                )
            except (KeyError, ValueError, TypeError):
                nearby = False
            street = (
                address.get("streetAddress", "")
                if isinstance(address, dict)
                else str(address)
            )
            address_match = bool(
                place.get("street")
                and place.get("housenumber")
                and place["street"].casefold() in street.casefold()
                and re.search(
                    r"(?<!\w)" + re.escape(place["housenumber"]) + r"(?!\w)",
                    street,
                    re.I,
                )
            )
            if nearby or address_match:
                selected.append(value)
    if not selected and not shared and len(candidates) == 1:
        # OSM directly links this URL to this place; do not accept an explicit foreign location.
        value = candidates[0]
        if not value.get("geo") and not value.get("address"):
            selected = candidates
    if len(selected) != 1:
        return {}
    value = selected[0]
    result = {
        k: value[k].strip()
        for k in ("telephone", "accessibilitySummary", "description", "name")
        if isinstance(value.get(k), str) and value[k].strip()
    }
    hours = value.get("openingHours")
    if isinstance(hours, list):
        hours = "; ".join(x for x in hours if isinstance(x, str))
    if isinstance(hours, str) and hours.strip():
        result["openingHours"] = hours.strip()
    elif value.get("openingHoursSpecification"):
        # Keep structured dates, exceptions and overnight periods without guessing an OSM expression.
        result["openingHours"] = json.dumps(
            value["openingHoursSpecification"], ensure_ascii=False
        )
    return result


def scrape(url: str, place: dict | None = None, shared: bool = False) -> dict:
    if "://" not in url:
        url = "https://" + url
    if not public_url(url):
        raise ValueError("URL is not a public HTTP(S) host")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with build_opener(SafeRedirect()).open(request, timeout=12) as response:
        if not public_url(response.geturl()):
            raise ValueError("Final URL is not a public HTTP(S) host")
        if "text/html" not in response.headers.get_content_type():
            raise ValueError("Website did not return HTML")
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("Website exceeded 1 MB")
    doc = PlacePage()
    doc.feed(body.decode("utf-8", errors="replace"))
    values = structured_values(doc, place, shared)
    return {
        "source_url": response.geturl(),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "title": values.get("name")
        or doc.meta.get("og:title")
        or " ".join(doc.title).strip()
        or None,
        "description": values.get("description")
        or doc.meta.get("og:description")
        or doc.meta.get("description"),
        "telephone": values.get("telephone"),
        "opening_hours": values.get("openingHours"),
        "accessibility_summary": values.get("accessibilitySummary"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/krakow.sqlite3")
    parser.add_argument("--output", type=Path, default=ROOT / "data/place-web.json")
    parser.add_argument("--limit", type=int, default=0, help="Maximum places; 0 = all")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--snapshot-only", action="store_true")
    parser.add_argument(
        "--refresh", action="store_true", help="Also revisit successfully scraped URLs"
    )
    parser.add_argument("--place-id", action="append", default=[])
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()
    if args.limit < 0 or args.delay < 0 or args.workers < 1:
        parser.error("--limit/--delay must be non-negative; --workers positive")
    from hackyeah.place_enrichment import effective_places, ensure_schema
    from scripts.import_place_web_data import import_records

    with closing(
        sqlite3.connect(args.database.resolve().as_uri() + "?mode=rw", uri=True)
    ) as db:
        ensure_schema(db)
        rows = effective_places(db)
        visited = {
            row[0]
            for row in db.execute("SELECT place_id, retrieved_at FROM place_web_data")
            if datetime.fromisoformat(row[1]) > datetime.now(UTC) - timedelta(days=7)
        }
    groups = defaultdict(list)
    for row in rows:
        if not row.get("website"):
            continue
        url = row["website"].strip()
        if "://" not in url:
            url = "https://" + url
        row["website"] = url
        groups[url.rstrip("/")].append(row)
    wanted = set(args.place_id)
    selected = [
        row
        for group in groups.values()
        for row in group
        if (not wanted or row["id"] in wanted)
        and (args.refresh or row["id"] not in visited)
    ]
    if args.limit:
        selected = selected[: args.limit]
    hosts = defaultdict(list)
    for row in selected:
        hosts[urlsplit(row["website"]).netloc].append(row)

    def scrape_host(rows):
        results, errors = [], []
        # Sequential per host: delay also applies to different branch URLs on a chain's website.
        cache = {}
        for row in rows:
            url = row["website"]
            shared = len(groups[url.rstrip("/")]) > 1
            # Shared chain homepages carry no reliable branch-specific details.
            if shared and urlsplit(url).path in ("", "/"):
                continue
            try:
                if url not in cache:
                    cache[url] = scrape(url, row, shared)
                    time.sleep(args.delay)
                elif shared:
                    continue
                results.append({"place_id": row["id"], **cache[url]})
            except (OSError, URLError, ValueError, TimeoutError) as error:
                errors.append({"place_id": row["id"], "url": url, "error": str(error)})
        return results, errors

    records, errors = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(scrape_host, rows) for rows in hosts.values()]
        for job in as_completed(jobs):
            fetched, failures = job.result()
            if fetched and not args.snapshot_only:
                import_records(args.database, fetched)
            records.extend(fetched)
            errors.extend(failures)
            print(f"Zapisano: {len(records)}; błędy: {len(errors)}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(args.output)
    args.output.with_suffix(".errors.json").write_text(
        json.dumps(errors, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"Zapisano {len(records)} rekordów do {args.output}"
        + (" i SQLite" if not args.snapshot_only else "")
    )


if __name__ == "__main__":
    main()
