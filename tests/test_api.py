import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from hackyeah.main import app
from hackyeah.models import Constraints, Fact, Observation, PlaceDetails

CONSTRAINTS = {
    "max_steps": 0,
    "max_threshold_cm": None,
    "max_slope_percent": None,
    "min_entrance_width_cm": None,
    "max_distance_without_rest_m": None,
    "require_step_free_access": True,
    "require_accessible_toilet": None,
    "allowed_surfaces": None,
}
PROFILE = {"name": "Profil", "description": "", "constraints": CONSTRAINTS}
OBSERVATION = {"attribute": "entrance_width_cm", "value": 90}
REPORT = {
    "target": {"type": "place", "id": "p1"},
    "kind": "missing_data",
    "observations": [OBSERVATION],
}


class APIContractTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "api.sqlite3"
        sqlite3.connect(path).close()
        environment = patch.dict(os.environ, {"DATABASE_PATH": str(path)})
        environment.start()
        self.addCleanup(environment.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_remaining_operations_are_stubs(self):
        cases = [
            ("POST", "/places/search", {"query": "Apteka"}),
            ("GET", "/places/p1", None),
        ]
        for method, path, body in cases:
            with self.subTest(method=method, path=path):
                kwargs = (
                    {"files": {"file": ("photo.png", b"stub", "image/png")}}
                    if path == "/photos"
                    else {"json": body}
                )
                response = self.client.request(method, "/api/v1" + path, **kwargs)
                self.assertEqual(response.status_code, 501, response.text)
                error = response.json()["error"]
                self.assertEqual(error["code"], "NOT_IMPLEMENTED")
                self.assertEqual(error["details"], [])
                self.assertEqual(error["request_id"], response.headers["X-Request-ID"])

    def test_openapi_success_and_error_schemas(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        operations = [
            operation
            for path in schema["paths"].values()
            for operation in path.values()
        ]
        self.assertEqual(len(operations), 23)
        for operation in operations:
            self.assertIn("501", operation["responses"])
            self.assertIn("422", operation["responses"])
            self.assertIn("ErrorResponse", str(operation["responses"]["422"]))
            self.assertTrue(
                any(
                    status in operation["responses"] for status in ("200", "201", "204")
                )
            )
        self.assertIn(
            "multipart/form-data",
            schema["paths"]["/api/v1/photos"]["post"]["requestBody"]["content"],
        )
        self.assertNotIn(
            "content",
            schema["paths"]["/api/v1/profiles/{id}"]["delete"]["responses"]["204"],
        )

    def test_invalid_payloads(self):
        cases = [
            (
                "POST",
                "/auth/register",
                {"email": "bad", "password": "secret", "display_name": ""},
            ),
            ("POST", "/profiles", {**PROFILE, "unknown": True}),
            ("PATCH", "/profiles/p1", {}),
            ("PATCH", "/profiles/p1", {"constraints": None}),
            ("PATCH", "/reports/r1", {"observations": None}),
            ("POST", "/places/search", {"query": "Apteka", "radius_m": 100}),
            (
                "POST",
                "/places/search",
                {"query": "Apteka", "constraints": CONSTRAINTS, "profile_id": "p1"},
            ),
            (
                "POST",
                "/routes/plan",
                {"origin": {"lat": 91, "lon": 19}, "destination": {"place_id": "p1"}},
            ),
            (
                "POST",
                "/routes/plan",
                {
                    "origin": {"lat": 50, "lon": 19, "place_id": "p1"},
                    "destination": {"place_id": "p1"},
                },
            ),
            (
                "POST",
                "/reports",
                {
                    "target": {"type": "place", "id": "p1"},
                    "kind": "correction",
                    "description": "Opis",
                },
            ),
            (
                "POST",
                "/reports",
                {"target": {"type": "place", "id": "p1"}, "kind": "missing_data"},
            ),
            (
                "PUT",
                "/owner/places/p1/declaration",
                {
                    "observations": [OBSERVATION, OBSERVATION],
                    "observed_at": "2026-10-01T12:00:00Z",
                },
            ),
        ]
        for method, path, body in cases:
            with self.subTest(path=path, body=body):
                response = self.client.request(method, "/api/v1" + path, json=body)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
                self.assertNotIn("input", response.text)
        response = self.client.get("/api/v1/profiles?limit=101")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["details"][0]["code"], "OUT_OF_RANGE")
        self.assertEqual(self.client.post("/api/v1/photos").status_code, 422)

    def test_errors_do_not_expose_password(self):
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "secret"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("secret", response.text)
        malformed = self.client.post(
            "/api/v1/profiles",
            content="{",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(malformed.json()["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(self.client.get("/").json()["error"]["code"], "NOT_FOUND")

    def test_nullable_constraints_are_required_and_preserve_values(self):
        constraints = Constraints.model_validate(CONSTRAINTS)
        self.assertEqual(constraints.model_dump(exclude_unset=True), CONSTRAINTS)
        for body in [
            {},
            {**CONSTRAINTS, "max_steps": 1},
            {**CONSTRAINTS, "allowed_surfaces": []},
            {**CONSTRAINTS, "max_steps": True},
        ]:
            with self.subTest(body=body), self.assertRaises(ValidationError):
                Constraints.model_validate(body)

    def test_observation_types_match_attributes(self):
        for attribute, value in [
            ("steps_count", True),
            ("steps_count", 1.5),
            ("entrance_width_cm", -1),
            ("ramp_available", 1),
            ("surface", "sand"),
            ("slope_percent", float("inf")),
        ]:
            with (
                self.subTest(attribute=attribute, value=value),
                self.assertRaises(ValidationError),
            ):
                Observation(attribute=attribute, value=value)
        for attribute, value in [
            ("steps_count", 0),
            ("ramp_available", False),
            ("surface", "paved"),
            ("entrance_width_cm", 90),
            ("slope_percent", None),
        ]:
            self.assertEqual(Observation(attribute=attribute, value=value).value, value)

    def test_response_nullable_fields_remain_required(self):
        required = set(Fact.model_json_schema()["required"])
        self.assertTrue(
            {
                "value",
                "observed_at",
                "valid_until",
                "confidence_percent",
                "unconfirmed_reason",
            }
            <= required
        )

    def test_places_require_five_accessibility_categories(self):
        categories = {
            "steps_count": "count",
            "threshold_height_cm": "cm",
            "elevator_available": None,
            "entrance_width_cm": "cm",
            "accessible_toilet": None,
        }
        facts = [
            {
                "id": attribute,
                "attribute": attribute,
                "value": None,
                "unit": unit,
                "status": "unconfirmed",
                "confidence_percent": None,
                "observed_at": None,
                "updated_at": "2026-10-01T12:00:00Z",
                "valid_until": None,
                "sources": [],
                "unconfirmed_reason": "missing",
            }
            for attribute, unit in categories.items()
        ]
        place = {
            "id": "p1",
            "name": "Miejsce",
            "category": "other",
            "address": None,
            "location": {"lat": 50, "lon": 19},
            "distance_m": None,
            "assessment": {
                "status": "uncertain",
                "summary": "Brak danych",
                "reasons": [],
            },
            "facts": facts,
            "barriers": [],
            "updated_at": "2026-10-01T12:00:00Z",
            "attribution": [],
        }
        self.assertEqual(len(PlaceDetails.model_validate(place).facts), 5)
        for index in range(len(facts)):
            with (
                self.subTest(missing=facts[index]["attribute"]),
                self.assertRaises(ValidationError),
            ):
                PlaceDetails.model_validate(
                    {**place, "facts": facts[:index] + facts[index + 1 :]}
                )


if __name__ == "__main__":
    unittest.main()
