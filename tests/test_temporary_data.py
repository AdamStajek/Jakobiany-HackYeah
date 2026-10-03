import json
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pydantic import ValidationError

from hackyeah import models as m
from hackyeah.main import app
from hackyeah.temporary_data import (
    main,
    parse_construction,
    parse_date,
    parse_weather,
    save_snapshot,
)

NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)


def forecast():
    return {
        "utc_offset_seconds": 0,
        "latitude": 50.06,
        "longitude": 19.94,
        "hourly_units": {
            "temperature_2m": "°C",
            "apparent_temperature": "°C",
            "precipitation": "mm",
            "snowfall": "cm",
            "snow_depth": "m",
            "weather_code": "wmo code",
        },
        "hourly": {
            "time": ["2026-10-03T12:00", "2026-10-03T13:00", "2026-10-03T14:00"],
            "temperature_2m": [31, -1, 1],
            "apparent_temperature": [33, -3, 0],
            "precipitation": [0, 1, 0.5],
            "snowfall": [0, 0, 0.3],
            "snow_depth": [0, 0, 0.02],
            "weather_code": [0, 66, 71],
        },
    }


KML = b"""<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark><name>Chodnik testowy</name><ExtendedData>
<Data name="od"><value>03.10.2026</value></Data>
<Data name="do"><value>03.10.2026</value></Data>
<Data name="Zmiany organizacji ruchu"><value>Remont chodnika</value></Data>
</ExtendedData><Point><coordinates>19.94,50.06,0</coordinates></Point></Placemark>
<Placemark><name>Nieznany termin</name><ExtendedData>
<Data name="do"><value>do odwolania</value></Data></ExtendedData></Placemark>
<Placemark><name>Stary remont</name><ExtendedData>
<Data name="do"><value>01.10.2026</value></Data></ExtendedData></Placemark>
</Document></kml>"""


class TemporaryDataTests(unittest.TestCase):
    def test_weather_risks_units_intervals_and_missing_values(self):
        snapshot = parse_weather(forecast(), NOW, "https://api.open-meteo.com/test")
        self.assertEqual(
            [d.category for d in snapshot.items], ["heat", "icing", "snow"]
        )
        self.assertEqual(snapshot.weather_hours[2].snow_depth_cm, 2)
        self.assertEqual(snapshot.weather_hours[0].starts_at, NOW)
        self.assertEqual(
            snapshot.weather_hours[0].precipitation_starts_at, NOW - timedelta(hours=1)
        )
        self.assertEqual(snapshot.valid_until, NOW + timedelta(hours=3))
        self.assertEqual(snapshot.heat_threshold_c, 30)
        for item in snapshot.items:
            self.assertEqual(item.status, "unconfirmed")
            self.assertEqual(item.unconfirmed_reason, "forecast")
            self.assertIsNone(item.confidence_percent)
            self.assertEqual(item.sources[0].license, "CC-BY-4.0")
        data = forecast()
        for key in data["hourly"]:
            if key != "time":
                data["hourly"][key] = [None] * 3
        unknown = parse_weather(data, NOW, "https://api.open-meteo.com/test")
        self.assertEqual(unknown.items, [])
        self.assertTrue(
            all(
                h.heat_risk is None and h.icing_risk is None and h.snow_risk is None
                for h in unknown.weather_hours
            )
        )

    def test_bad_forecast_rejected_before_overwriting_output(self):
        for change in ("unit", "length", "negative", "nonfinite", "duplicate"):
            data = forecast()
            if change == "unit":
                data["hourly_units"]["snow_depth"] = "cm"
            elif change == "length":
                data["hourly"]["snowfall"].pop()
            elif change == "negative":
                data["hourly"]["snowfall"][0] = -1
            elif change == "nonfinite":
                data["hourly"]["temperature_2m"][0] = float("nan")
            else:
                data["hourly"]["time"][1] = data["hourly"]["time"][0]
            with self.subTest(change=change), self.assertRaises(ValueError):
                parse_weather(data, NOW, "https://api.open-meteo.com/test")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "weather.json"
            save_snapshot(
                parse_weather(forecast(), NOW, "https://api.open-meteo.com/test"),
                output,
            )
            original = output.read_bytes()
            with (
                patch("sys.argv", ["scrape_weather.py"]),
                patch("hackyeah.temporary_data.fetch", side_effect=OSError("offline")),
            ):
                with self.assertRaises(OSError):
                    main("weather")
            self.assertEqual(output.read_bytes(), original)
            m.TemporaryDataSnapshot.model_validate(json.loads(original))

    def test_construction_dates_unknown_access_and_expiry(self):
        snapshot = parse_construction(KML, NOW)
        self.assertEqual(len(snapshot.items), 2)
        item = snapshot.items[0]
        self.assertEqual(item.geometry.coordinates, (19.94, 50.06))
        self.assertEqual(item.starts_at, datetime(2026, 10, 2, 22, tzinfo=UTC))
        self.assertEqual(item.ends_at, datetime(2026, 10, 3, 22, tzinfo=UTC))
        self.assertEqual(item.pedestrian_access, "unknown")
        self.assertEqual(item.status, "unconfirmed")
        self.assertIsNone(snapshot.items[1].ends_at)
        self.assertIsNone(snapshot.items[1].geometry)
        self.assertIsNone(item.sources[0].license)
        self.assertEqual(
            parse_date("25.10.2026", end=True), datetime(2026, 10, 25, 23, tzinfo=UTC)
        )
        with self.assertRaises(ValueError):
            parse_construction(b'<kml xmlns="http://www.opengis.net/kml/2.2"/>', NOW)
        with self.assertRaises(ValidationError):
            m.TemporaryDifficulty.model_validate(
                {**item.model_dump(), "ends_at": item.starts_at}
            )

    def test_api_schema_exposes_temporary_categories(self):
        schemas = app.openapi()["components"]["schemas"]
        self.assertEqual(
            set(schemas["TemporaryDifficulty"]["properties"]["category"]["enum"]),
            {"heat", "icing", "snow", "construction"},
        )
        self.assertIn("temporary_difficulties", schemas["RouteSegment"]["properties"])
        for attribute in (
            "heat_risk",
            "icing_risk",
            "snow_risk",
            "construction_present",
        ):
            self.assertTrue(m.Observation(attribute=attribute, value=True).value)
            with self.assertRaises(ValidationError):
                m.Observation(attribute=attribute, value=1)


if __name__ == "__main__":
    unittest.main()
