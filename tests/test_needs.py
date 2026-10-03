import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.test import TestModel

from hackyeah.main import app
from hackyeah.models import InterpretResponse
from hackyeah.needs import needs_agent


class NeedsTests(unittest.TestCase):
    def test_interpret_returns_validated_constraints(self):
        output = {
            "constraints": {
                "max_steps": 0,
                "max_threshold_cm": None,
                "max_slope_percent": None,
                "min_entrance_width_cm": None,
                "max_distance_without_rest_m": 300,
                "require_step_free_access": True,
                "require_accessible_toilet": None,
                "allowed_surfaces": None,
            },
            "summary": "Bez schodów; odpoczynek co najwyżej co 300 metrów.",
            "questions": [],
            "requires_confirmation": True,
        }
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
            needs_agent.override(model=TestModel(custom_output_args=output)),
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/v1/needs/interpret",
                json={"description": "Bez schodów, odpoczynek co 300 m"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(), InterpretResponse.model_validate(output).model_dump()
        )
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_missing_key_returns_contract_error(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), TestClient(app) as client:
            response = client.post(
                "/api/v1/needs/interpret", json={"description": "Bez schodów"}
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "DEPENDENCY_UNAVAILABLE")

    def test_provider_error_does_not_expose_description(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
            patch.object(
                needs_agent,
                "run",
                new=AsyncMock(
                    side_effect=ModelHTTPError(429, "test", "private description")
                ),
            ),
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/v1/needs/interpret", json={"description": "Bez schodów"}
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "DEPENDENCY_UNAVAILABLE")
        self.assertNotIn("private description", response.text)

    def test_invalid_description_is_rejected_before_model_call(self):
        with TestClient(app) as client:
            for description in ("", "x" * 4001):
                response = client.post(
                    "/api/v1/needs/interpret", json={"description": description}
                )
                self.assertEqual(response.status_code, 422)
