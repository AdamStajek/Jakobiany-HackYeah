"""Scrape public, OSM-linked place websites into a JSON snapshot."""

import argparse
import json
import socket
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from ipaddress import ip_address
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "SwojaDroga/0.1 (Krakow accessibility research; contact: open-data project)"
MAX_BYTES = 1_000_000


def public_url(url: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        return all(
            ip_address(info[4][0]).is_global
            for info in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
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


def structured_values(doc: PlacePage) -> dict:
    result = {}

    def visit(value):
        if isinstance(value, dict):
            for key in ("telephone", "openingHours", "accessibilitySummary", "description", "name"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    result.setdefault(key, candidate.strip())
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
    return result


def scrape(url: str) -> dict:
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
    values = structured_values(doc)
    return {
        "source_url": url,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "title": values.get("name") or doc.meta.get("og:title") or " ".join(doc.title).strip() or None,
        "description": values.get("description") or doc.meta.get("og:description") or doc.meta.get("description"),
        "telephone": values.get("telephone"),
        "opening_hours": values.get("openingHours"),
        "accessibility_summary": values.get("accessibilitySummary"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/krakow.sqlite3")
    parser.add_argument("--output", type=Path, default=ROOT / "data/place-web.json")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--place-id", action="append", default=[])
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()
    if args.limit < 1 or args.delay < 0:
        parser.error("--limit must be positive and --delay non-negative")
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect(args.database)) as db:
        query = "SELECT id, website FROM places WHERE website IS NOT NULL ORDER BY id"
        rows = db.execute(query).fetchall()
    if args.place_id:
        wanted = set(args.place_id)
        rows = [row for row in rows if row[0] in wanted]
    records = []
    for index, (place_id, url) in enumerate(rows[: args.limit]):
        try:
            records.append({"place_id": place_id, **scrape(url)})
            print(f"OK {place_id}", flush=True)
        except (OSError, HTTPError, URLError, ValueError, TimeoutError) as error:
            print(f"Pominięto {place_id}: {error}", flush=True)
        if index + 1 < min(len(rows), args.limit):
            time.sleep(args.delay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(args.output)
    print(f"Zapisano {len(records)} rekordów do {args.output}")


if __name__ == "__main__":
    main()
