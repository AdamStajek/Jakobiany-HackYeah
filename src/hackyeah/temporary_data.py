"""Live weather forecasts and file-based ZDMK construction reports for Kraków."""

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from hackyeah import models as m

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
CONSTRUCTION_PAGE = "https://zdmk.krakow.pl/zestawienie-prac-w-miescie/"
CONSTRUCTION_URL = (
    "https://www.google.com/maps/d/kml?mid=1_iHhcnIv8THHQSyeLFPArE6k2zhIrtA&forcekml=1"
)
VARIABLES = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "snowfall",
    "snow_depth",
    "weather_code",
)
KML = {"k": "http://www.opengis.net/kml/2.2"}


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "hackyeah-route-conditions/0.1"})
    with urlopen(request, timeout=45) as response:
        data = response.read(10 * 1024 * 1024 + 1)
        expected = response.headers.get("Content-Length")
        if expected and len(data) != int(expected):
            raise ValueError("Niepełna odpowiedź źródła.")
    if not data or len(data) > 10 * 1024 * 1024:
        raise ValueError("Pusta lub zbyt duża odpowiedź źródła.")
    return data


def save_snapshot(snapshot: m.TemporaryDataSnapshot, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        temporary.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def forecast_url(location: m.Coordinates, days: int) -> str:
    return (
        WEATHER_URL
        + "?"
        + urlencode(
            {
                "latitude": location.lat,
                "longitude": location.lon,
                "hourly": ",".join(VARIABLES),
                "forecast_days": days,
                "timezone": "UTC",
                "temperature_unit": "celsius",
                "precipitation_unit": "mm",
            }
        )
    )


def parse_weather(
    payload: dict, retrieved_at: datetime, url: str, heat_c: float = 30
) -> m.TemporaryDataSnapshot:
    if not math.isfinite(heat_c):
        raise ValueError("Próg upału musi być skończony.")
    if payload.get("utc_offset_seconds") != 0:
        raise ValueError("Prognoza musi być w UTC.")
    hourly = payload["hourly"]
    times = hourly["time"]
    if not times:
        raise ValueError("Brak godzin prognozy.")
    expected_units = {
        "temperature_2m": "°C",
        "apparent_temperature": "°C",
        "precipitation": "mm",
        "snowfall": "cm",
        "snow_depth": "m",
        "weather_code": "wmo code",
    }
    for variable in VARIABLES:
        if len(hourly[variable]) != len(times):
            raise ValueError(f"Niespójna długość prognozy: {variable}.")
        if payload["hourly_units"].get(variable) != expected_units[variable]:
            raise ValueError(f"Nieoczekiwana jednostka: {variable}.")
    source = m.Source(
        type="weather",
        label="Open-Meteo",
        url=url,
        license="CC-BY-4.0",
        retrieved_at=retrieved_at,
    )
    location = m.Coordinates(lat=payload["latitude"], lon=payload["longitude"])
    valid_until = retrieved_at + timedelta(hours=3)
    hours = []
    items = []
    previous = None
    for index, timestamp in enumerate(times):
        start = datetime.fromisoformat(timestamp)
        if start.tzinfo is not None and start.utcoffset() != timedelta(0):
            raise ValueError("Znaczniki prognozy muszą być w UTC.")
        start = start.replace(tzinfo=UTC)
        if previous is not None and start - previous != timedelta(hours=1):
            raise ValueError(
                "Prognoza musi zawierać kolejne godziny bez luk i duplikatów."
            )
        previous = start
        temperature, apparent, precipitation, snowfall, depth, code = [
            hourly[k][index] for k in VARIABLES
        ]
        # Validate raw numbers before computing indicators (NaN/negative precipitation must not become 'safe').
        hour = m.WeatherHour.model_validate(
            {
                "location": location,
                "starts_at": start,
                "ends_at": start + timedelta(hours=1),
                "temperature_c": temperature,
                "apparent_temperature_c": apparent,
                "precipitation_starts_at": start - timedelta(hours=1),
                "precipitation_ends_at": start,
                "precipitation_mm": precipitation,
                "snowfall_cm": snowfall,
                "snow_depth_cm": None if depth is None else depth * 100,
                "weather_code": code,
                "heat_risk": None,
                "icing_risk": None,
                "snow_risk": None,
            }
        )
        temperatures = [v for v in (temperature, apparent) if v is not None]
        hour.heat_risk = (
            True
            if any(v >= heat_c for v in temperatures)
            else False
            if len(temperatures) == 2
            else None
        )
        freezing = code in {48, 56, 57, 66, 67}
        moisture = (precipitation is not None and precipitation > 0) or (
            depth is not None and depth > 0
        )
        hour.icing_risk = (
            True
            if freezing or (temperature is not None and temperature <= 0 and moisture)
            else None
        )
        snow_code = code in {71, 73, 75, 77, 85, 86}
        hour.snow_risk = (
            True
            if snow_code
            or (snowfall is not None and snowfall > 0)
            or (depth is not None and depth > 0)
            else False
            if snowfall is not None and depth is not None and code is not None
            else None
        )
        if hour.ends_at <= retrieved_at:
            continue
        hours.append(hour)
        for category, risk, description in (
            (
                "heat",
                hour.heat_risk,
                f"Ryzyko upału: temperatura lub odczuwalna ≥ {heat_c:g}°C.",
            ),
            (
                "icing",
                hour.icing_risk,
                "Ryzyko oblodzenia według prognozy; stan chodnika niepotwierdzony.",
            ),
            (
                "snow",
                hour.snow_risk,
                "Prognozowany opad lub pokrywa śnieżna; odśnieżenie chodnika nieznane.",
            ),
        ):
            if risk is True:
                items.append(
                    m.TemporaryDifficulty.model_validate(
                        {
                            "id": f"weather/{category}/{location.lat}/{location.lon}/{hour.starts_at.isoformat()}",
                            "category": category,
                            "description": description,
                            "geometry": {
                                "type": "Point",
                                "coordinates": (location.lon, location.lat),
                            },
                            "location_text": "Punkt siatki prognozy dla Krakowa; nie pomiar na chodniku.",
                            "starts_at": hour.starts_at,
                            "ends_at": hour.ends_at,
                            "updated_at": retrieved_at,
                            "valid_until": valid_until,
                            "status": "unconfirmed",
                            "unconfirmed_reason": "forecast",
                            "confidence_percent": None,
                            "sources": [source],
                            "weather": hour,
                        }
                    )
                )
    if not hours:
        raise ValueError("Brak aktualnych lub przyszłych godzin prognozy.")
    return m.TemporaryDataSnapshot(
        source="weather",
        heat_threshold_c=heat_c,
        generated_at=retrieved_at,
        valid_until=valid_until,
        items=items,
        weather_hours=hours,
        attribution=[source],
        warnings=[
            "Prognoza dla punktu siatki nie określa stanu konkretnego chodnika.",
            "Brak sygnału oblodzenia nie wyklucza lodu ani zamarzania wcześniejszych opadów.",
            "Wartości chwilowe dotyczą początku godziny; opady dotyczą osobnego, poprzedzającego okresu. Ryzyka są heurystyką na kolejną godzinę.",
        ],
    )


def parse_date(text: str | None, *, end: bool = False) -> datetime | None:
    if not text:
        return None
    try:
        date = datetime.strptime(text.strip(), "%d.%m.%Y")
    except ValueError:
        return None
    # Dates supplied by ZDMK are local days. End date includes the entire day.
    if end:
        date += timedelta(days=1)
    return date.replace(tzinfo=ZoneInfo("Europe/Warsaw")).astimezone(UTC)


def parse_construction(data: bytes, retrieved_at: datetime) -> m.TemporaryDataSnapshot:
    root = ET.fromstring(data)
    placemarks = root.findall(".//k:Placemark", KML)
    if not placemarks:
        raise ValueError("Brak rekordów mapy ZDMK; zachowano poprzednią kopię.")
    source = m.Source(
        type="other",
        label="ZDMK — mapa prac drogowych",
        url=CONSTRUCTION_PAGE,
        license=None,
        retrieved_at=retrieved_at,
    )
    valid_until = retrieved_at + timedelta(hours=24)
    items = []
    warnings = [
        "Mapa nie gwarantuje kompletności ani bieżącego stanu prac.",
        "Punkt remontu nie określa całego obszaru robót ani zamknięcia chodnika.",
        "Źródło nie podaje osobnej licencji zbioru; zachowano odnośnik i autorstwo ZDMK.",
    ]
    for placemark in placemarks:
        name = placemark.findtext("k:name", default="", namespaces=KML).strip()
        fields = {
            d.attrib["name"]: d.findtext("k:value", default="", namespaces=KML).strip()
            for d in placemark.findall("k:ExtendedData/k:Data", KML)
        }
        geometry = None
        coordinates = placemark.findtext("k:Point/k:coordinates", namespaces=KML)
        if coordinates:
            values = coordinates.strip().split()[0].split(",")
            geometry = m.Point(
                type="Point", coordinates=(float(values[0]), float(values[1]))
            )
        start = parse_date(fields.get("od"))
        end = parse_date(fields.get("do"), end=True)
        if start is not None and end is not None and end <= start:
            warnings.append(f"Niespójne daty rekordu {name}; okres pozostaje nieznany.")
            start = end = None
        if end is not None and end <= retrieved_at:
            continue
        description = fields.get("Zmiany organizacji ruchu", "")
        title = fields.get("Rodzaj prac", "Prace drogowe")
        identifier = hashlib.sha256(
            json.dumps(
                [
                    name,
                    fields.get("Lokalizacja szczegółowa"),
                    fields.get("od"),
                    coordinates,
                ],
                ensure_ascii=False,
            ).encode()
        ).hexdigest()[:20]
        items.append(
            m.TemporaryDifficulty(
                id=f"zdmk/{identifier}",
                category="construction",
                description=f"{name}: {title}. {description}".strip(),
                geometry=geometry,
                location_text=" — ".join(
                    v for v in (name, fields.get("Lokalizacja szczegółowa")) if v
                )
                or None,
                starts_at=start,
                ends_at=end,
                updated_at=retrieved_at,
                valid_until=valid_until,
                status="unconfirmed",
                unconfirmed_reason="pending_verification",
                confidence_percent=None,
                sources=[source],
                source_fields=fields,
            )
        )
    return m.TemporaryDataSnapshot(
        source="construction",
        generated_at=retrieved_at,
        valid_until=valid_until,
        items=items,
        attribution=[source],
        warnings=warnings,
    )


def get_weather(
    location: m.Coordinates, days: int = 3, heat_c: float = 30
) -> m.TemporaryDataSnapshot:
    """Fetch a fresh forecast per call; no disk cache or database writes."""
    url = forecast_url(location, days)
    return parse_weather(json.loads(fetch(url)), datetime.now(UTC), url, heat_c)


def main(source: str | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    if source is None:
        parser.add_argument("source", choices=("weather", "construction"))
    parser.add_argument(
        "--input", type=Path, help="Parse a local JSON/KML instead of fetching."
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Construction: write JSON without updating SQLite",
    )
    parser.add_argument(
        "--database", type=Path, help="Also import into an existing SQLite database."
    )
    if source != "construction":
        parser.add_argument("--lat", type=float, default=50.0614)
        parser.add_argument("--lon", type=float, default=19.9366)
        parser.add_argument("--days", type=int, choices=range(1, 8), default=3)
        parser.add_argument("--heat-c", type=float, default=30)
    args = parser.parse_args()
    selected = source or args.source
    output = args.output or Path(f"data/temporary/{selected}.json")
    now = datetime.now(UTC)
    if selected == "weather" and (args.database or args.output):
        parser.error("Pogoda jest wypisywana na stdout, bez zapisu do bazy ani pliku.")
    if selected == "weather":
        location = m.Coordinates(lat=args.lat, lon=args.lon)
        if not (49.96 <= location.lat <= 50.14 and 19.76 <= location.lon <= 20.16):
            parser.error("Punkt musi znajdować się w obsługiwanym obszarze Krakowa.")
        url = forecast_url(location, args.days)
        data = args.input.read_bytes() if args.input else fetch(url)
        snapshot = parse_weather(json.loads(data), now, url, args.heat_c)
    else:
        data = args.input.read_bytes() if args.input else fetch(CONSTRUCTION_URL)
        snapshot = parse_construction(data, now)
    if selected == "weather":
        print(snapshot.model_dump_json(indent=2))
        return
    save_snapshot(snapshot, output)
    if not args.snapshot_only:
        from hackyeah.temporary_store import import_snapshots

        import_snapshots(args.database or Path("data/krakow.sqlite3"), [snapshot])
    print(
        json.dumps(
            {
                "output": str(output),
                "items": len(snapshot.items),
                "weather_hours": len(snapshot.weather_hours),
                "valid_until": snapshot.valid_until.isoformat(),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
