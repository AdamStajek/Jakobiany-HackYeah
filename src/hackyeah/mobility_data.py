"""Official ZTP schedules and ZDMK parking data; atomic, daily refreshes."""

import csv
import io
import json
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

from google.protobuf.message import DecodeError
from google.transit import gtfs_realtime_pb2 as gtfs

from hackyeah import models as m

ZTP = "https://gtfs.ztp.krakow.pl/"
FEEDS = ("A", "M", "T")
PARKING = "https://services-eu1.arcgis.com/svTzSt3AvH7sK6q9/arcgis/rest/services/Miejsca_postojowe_OZN/FeatureServer/0"
PARKING_MAP = "https://gmk-2.maps.arcgis.com/apps/instant/nearby/index.html?appid=57ff3986574a4c26a9d0466e0870b9b3"
_refresh_lock = Lock()
_rt_lock = Lock()
_rt_cache: dict[tuple[str, str], tuple[float, Any]] = {}
_last_attempt: dict[str, float] = {}


def data_directory() -> Path:
    return Path(
        os.getenv(
            "MOBILITY_DATA_PATH", Path(__file__).resolve().parents[2] / "data/mobility"
        )
    )


def download(url: str, limit: int = 150_000_000) -> bytes:
    with urlopen(
        Request(url, headers={"User-Agent": "SwojaDroga/1.0"}), timeout=30
    ) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Przekroczony limit danych źródła.")
    return data


def seconds(value: str) -> int:
    hour, minute, second = map(int, value.split(":"))
    if hour < 0 or not 0 <= minute < 60 or not 0 <= second < 60:
        raise ValueError("Niepoprawny czas GTFS.")
    return hour * 3600 + minute * 60 + second


def import_gtfs(db: sqlite3.Connection, feed: str, content: bytes) -> None:
    """Prefix IDs: the three feeds may reuse the same identifiers."""
    with ZipFile(io.BytesIO(content)) as archive:

        def rows(name):
            if name + ".txt" not in archive.namelist():
                return
            with archive.open(name + ".txt") as raw:
                yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))

        def identifier(value):
            return f"{feed}:{value}" if value else ""

        db.executemany(
            "INSERT INTO stops VALUES(?,?,?,?,?,?)",
            (
                (
                    identifier(r["stop_id"]),
                    r["stop_name"],
                    float(r["stop_lon"]),
                    float(r["stop_lat"]),
                    int(r.get("wheelchair_boarding") or 0),
                    identifier(r.get("parent_station", "")),
                )
                for r in rows("stops")
                if r.get("stop_lon")
                and r.get("stop_lat")
                and r.get("location_type", "0") in ("", "0")
            ),
        )
        db.executemany(
            "INSERT INTO routes VALUES(?,?,?)",
            (
                (
                    identifier(r["route_id"]),
                    r.get("route_short_name")
                    or r.get("route_long_name")
                    or r["route_id"],
                    int(r["route_type"]),
                )
                for r in rows("routes")
            ),
        )
        db.executemany(
            "INSERT INTO trips VALUES(?,?,?,?,?,?)",
            (
                (
                    identifier(r["trip_id"]),
                    identifier(r["service_id"]),
                    identifier(r["route_id"]),
                    r.get("trip_headsign", ""),
                    identifier(r.get("shape_id", "")),
                    int(r.get("wheelchair_accessible") or 0),
                )
                for r in rows("trips")
            ),
        )
        db.executemany(
            "INSERT INTO calendar VALUES(?,?,?,?)",
            (
                (
                    identifier(r["service_id"]),
                    r["start_date"],
                    r["end_date"],
                    "".join(
                        r[d]
                        for d in (
                            "monday",
                            "tuesday",
                            "wednesday",
                            "thursday",
                            "friday",
                            "saturday",
                            "sunday",
                        )
                    ),
                )
                for r in rows("calendar")
            ),
        )
        db.executemany(
            "INSERT INTO exceptions VALUES(?,?,?)",
            (
                (identifier(r["service_id"]), r["date"], int(r["exception_type"]))
                for r in rows("calendar_dates")
            ),
        )
        db.executemany(
            "INSERT INTO times VALUES(?,?,?,?,?,?,?,?)",
            (
                (
                    identifier(r["trip_id"]),
                    int(r["stop_sequence"]),
                    identifier(r["stop_id"]),
                    seconds(r["arrival_time"]),
                    seconds(r["departure_time"]),
                    int(r.get("pickup_type") or 0),
                    int(r.get("drop_off_type") or 0),
                    float(r["shape_dist_traveled"])
                    if r.get("shape_dist_traveled")
                    else None,
                )
                for r in rows("stop_times")
            ),
        )
        db.executemany(
            "INSERT INTO shapes VALUES(?,?,?,?,?)",
            (
                (
                    identifier(r["shape_id"]),
                    int(r["shape_pt_sequence"]),
                    float(r["shape_pt_lon"]),
                    float(r["shape_pt_lat"]),
                    float(r["shape_dist_traveled"])
                    if r.get("shape_dist_traveled")
                    else None,
                )
                for r in rows("shapes")
            ),
        )
        db.executemany(
            "INSERT INTO transfers VALUES(?,?,?,?)",
            (
                (
                    identifier(r["from_stop_id"]),
                    identifier(r["to_stop_id"]),
                    int(r["transfer_type"]),
                    int(r.get("min_transfer_time") or 0),
                )
                for r in rows("transfers")
            ),
        )


SCHEMA = """
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE stops(id TEXT PRIMARY KEY,name TEXT,lon REAL,lat REAL,wheelchair INTEGER,parent TEXT);
CREATE TABLE routes(id TEXT PRIMARY KEY,line TEXT,type INTEGER);
CREATE TABLE trips(id TEXT PRIMARY KEY,service TEXT,route TEXT,headsign TEXT,shape TEXT,wheelchair INTEGER);
CREATE TABLE calendar(service TEXT,start TEXT,end TEXT,weekdays TEXT);
CREATE TABLE exceptions(service TEXT,date TEXT,type INTEGER);
CREATE TABLE times(trip TEXT,sequence INTEGER,stop TEXT,arrival INTEGER,departure INTEGER,pickup INTEGER,dropoff INTEGER,shape_distance REAL,PRIMARY KEY(trip,sequence));
CREATE TABLE shapes(id TEXT,sequence INTEGER,lon REAL,lat REAL,distance REAL,PRIMARY KEY(id,sequence));
CREATE TABLE transfers(a TEXT,b TEXT,type INTEGER,minimum INTEGER);
CREATE INDEX service_trips ON trips(service);
CREATE INDEX exception_date ON exceptions(date);
"""


def refresh_schedule(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent, prefix=".gtfs-") as directory:
        candidate = Path(directory) / "schedule.sqlite3"
        with closing(sqlite3.connect(candidate)) as db:
            db.executescript(SCHEMA)
            with ThreadPoolExecutor(max_workers=3) as pool:
                for feed, content in zip(
                    FEEDS,
                    pool.map(download, [f"{ZTP}GTFS_KRK_{f}.zip" for f in FEEDS]),
                    strict=True,
                ):
                    import_gtfs(db, feed, content)
            db.executescript("""
                CREATE TABLE connections AS
                SELECT trip,sequence,stop a,
                    LEAD(stop) OVER w b,LEAD(sequence) OVER w target_sequence,departure,
                    LEAD(arrival) OVER w arrival,pickup,
                    LEAD(dropoff) OVER w dropoff,
                    shape_distance start_distance,
                    LEAD(shape_distance) OVER w end_distance
                FROM times WINDOW w AS (PARTITION BY trip ORDER BY sequence);
                DELETE FROM connections WHERE b IS NULL;
                CREATE INDEX connection_trip ON connections(trip);
                CREATE INDEX connection_departure ON connections(departure);
            """)
            db.execute(
                "INSERT INTO metadata VALUES('retrieved_at',?)",
                (datetime.now(UTC).isoformat(),),
            )
            if not db.execute("SELECT 1 FROM times LIMIT 1").fetchone():
                raise ValueError("Pusty rozkład ZTP.")
            db.commit()
        candidate.replace(path)


def refresh_parking(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items = []
    offset = 0
    while True:
        query = urlencode(
            {
                "where": "1=1",
                "outFields": "*",
                "outSR": 4326,
                "f": "json",
                "orderByFields": "OBJECTID",
                "resultOffset": offset,
                "resultRecordCount": 1000,
            }
        )
        page = json.loads(download(f"{PARKING}/query?{query}"))
        if "error" in page:
            raise ValueError("Błąd źródła parkingów ZDMK.")
        features = page["features"]
        for feature in features:
            attrs, point = feature["attributes"], feature["geometry"]
            items.append(
                m.MobilityPoint(
                    id=f"zdmk:{attrs['OBJECTID']}",
                    kind="parking",
                    name=attrs.get("punkt_adresowy") or "Miejsce postojowe OZN",
                    location=m.Coordinates(lon=point["x"], lat=point["y"]),
                )
            )
        if not page.get("exceededTransferLimit"):
            break
        if not features or offset > 100_000:
            raise ValueError("Niepełne dane parkingów.")
        offset += len(features)
    if not items:
        raise ValueError("Pusta mapa parkingów.")
    snapshot = {
        "retrieved_at": datetime.now(UTC).isoformat(),
        "items": [p.model_dump(mode="json") for p in items],
    }
    with TemporaryDirectory(dir=path.parent, prefix=".parking-") as directory:
        candidate = Path(directory) / "parking.json"
        candidate.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        candidate.replace(path)


def ensure_data(kind: str, force: bool = False) -> tuple[Path, list[str]]:
    path = data_directory() / (
        "schedule.sqlite3" if kind == "schedule" else "parking.json"
    )
    warnings = []
    with _refresh_lock:
        now = time.time()
        stale = not path.exists() or now - path.stat().st_mtime > 12 * 3600
        if force or (stale and now - _last_attempt.get(kind, 0) > 300):
            _last_attempt[kind] = now
            try:
                (refresh_schedule if kind == "schedule" else refresh_parking)(path)
            except (OSError, ValueError, KeyError, sqlite3.Error, BadZipFile):
                warnings.append(
                    "Nie udało się odświeżyć rozkładu ZTP."
                    if kind == "schedule"
                    else "Nie udało się odświeżyć mapy parkingów ZDMK."
                )
        if not path.exists():
            raise OSError("Brak pobranych danych miejskich.")
        if now - path.stat().st_mtime > 24 * 3600:
            warnings.append("Kopia danych miejskich jest starsza niż 24 godziny.")
    return path, warnings


def source(kind: str, retrieved: datetime) -> m.Source:
    return m.Source(
        type="other",
        label="ZTP Kraków — rozkład GTFS i dane rzeczywiste"
        if kind == "schedule"
        else "Gmina Miejska Kraków, ZDMK — miejsca postojowe OZN",
        url=ZTP if kind == "schedule" else PARKING_MAP,
        license=None,
        retrieved_at=retrieved,
    )


def parking_points() -> tuple[list[m.MobilityPoint], list[str], m.Source]:
    path, warnings = ensure_data("parking")
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    return (
        [m.MobilityPoint.model_validate(p) for p in snapshot["items"]],
        warnings,
        source("parking", datetime.fromisoformat(snapshot["retrieved_at"])),
    )


def realtime(feed: str, kind: str):
    key = (feed, kind)
    with _rt_lock:
        cached = _rt_cache.get(key)
        if cached and time.time() - cached[0] < 30:
            return cached[1]
    try:
        message = gtfs.FeedMessage()
        message.ParseFromString(download(f"{ZTP}{kind}_{feed}.pb", 20_000_000))
        if (
            not message.IsInitialized()
            or not message.header.HasField("timestamp")
            or not -60 <= time.time() - message.header.timestamp <= 180
        ):
            message = None
    except (OSError, ValueError, DecodeError):
        message = None
    with _rt_lock:
        _rt_cache[key] = (time.time(), message)
    return message


def realtime_updates():
    with ThreadPoolExecutor(max_workers=3) as pool:
        messages = list(pool.map(lambda f: realtime(f, "TripUpdates"), FEEDS))
    updates = {}
    for feed, message in zip(FEEDS, messages, strict=True):
        if message:
            for entity in message.entity:
                if entity.HasField("trip_update") and not entity.is_deleted:
                    if (
                        entity.trip_update.HasField("timestamp")
                        and not -60 <= time.time() - entity.trip_update.timestamp <= 180
                    ):
                        continue
                    updates[f"{feed}:{entity.trip_update.trip.trip_id}"] = (
                        entity.trip_update
                    )
    missing = [f for f, message in zip(FEEDS, messages, strict=True) if message is None]
    warnings = (
        [
            f"Brak świeżych opóźnień dla danych ZTP: {', '.join(missing)}. Dla tych kursów użyto rozkładu."
        ]
        if missing
        else []
    )
    return updates, warnings


def mobility_map(kind: str) -> m.MobilityMap:
    if kind == "parking":
        items, warnings, attribution = parking_points()
        return m.MobilityMap(items=items, warnings=warnings, attribution=[attribution])
    path, warnings = ensure_data("schedule")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        retrieved = datetime.fromisoformat(
            db.execute(
                "SELECT value FROM metadata WHERE key='retrieved_at'"
            ).fetchone()[0]
        )
        if kind == "stops":
            items = [
                m.MobilityPoint(
                    id=r[0],
                    name=r[1],
                    location=m.Coordinates(lon=r[2], lat=r[3]),
                    kind="stop",
                )
                for r in db.execute("SELECT id,name,lon,lat FROM stops")
            ]
        else:
            lines = dict(
                db.execute(
                    "SELECT trips.id,routes.line FROM trips JOIN routes ON trips.route=routes.id"
                )
            )
            items = []
            with ThreadPoolExecutor(max_workers=3) as pool:
                messages = list(
                    pool.map(lambda f: realtime(f, "VehiclePositions"), FEEDS)
                )
            for feed, message in zip(FEEDS, messages, strict=True):
                if message is None:
                    warnings.append(f"Pozycje pojazdów {feed} są chwilowo niedostępne.")
                    continue
                for entity in message.entity:
                    if entity.is_deleted or not entity.HasField("vehicle"):
                        continue
                    v = entity.vehicle
                    if (
                        not v.HasField("position")
                        or not v.HasField("timestamp")
                        or not -60 <= time.time() - v.timestamp <= 180
                    ):
                        continue
                    line = lines.get(f"{feed}:{v.trip.trip_id}")
                    items.append(
                        m.MobilityPoint(
                            id=f"{feed}:{entity.id}",
                            name=f"Pojazd {line or v.vehicle.label or v.vehicle.id}",
                            kind="vehicle",
                            line=line,
                            location=m.Coordinates(
                                lon=v.position.longitude, lat=v.position.latitude
                            ),
                            updated_at=datetime.fromtimestamp(v.timestamp, UTC),
                        )
                    )
    return m.MobilityMap(
        items=items, warnings=warnings, attribution=[source("schedule", retrieved)]
    )
