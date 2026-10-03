import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.test import TestModel

from hackyeah.main import app
from hackyeah.search_ai import place_agent, route_agent


class SearchAITests(unittest.TestCase):
    def setUp(self):
        for target in (
            "hackyeah.main.initialize",
            "hackyeah.confidence.recalculate_all",
        ):
            startup = patch(target)
            startup.start()
            self.addCleanup(startup.stop)

    def test_proposals_use_validated_outputs(self):
        constraints = {
            "max_steps": 0,
            "max_threshold_cm": None,
            "max_slope_percent": None,
            "min_entrance_width_cm": None,
            "max_distance_without_rest_m": None,
            "require_step_free_access": True,
            "require_accessible_toilet": None,
            "allowed_surfaces": None,
        }
        for mode, agent, fields in (
            ("places", place_agent, {"query": "kawiarnia"}),
            (
                "routes",
                route_agent,
                {"origin_query": "Rynek Główny", "destination_query": "Wawel"},
            ),
        ):
            with self.subTest(mode=mode):
                output = {
                    **fields,
                    "constraints": constraints,
                    "summary": "Bez schodów",
                    "questions": [],
                }
                with (
                    patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
                    agent.override(model=TestModel(custom_output_args=output)),
                    TestClient(app) as client,
                ):
                    response = client.post(
                        f"/api/v1/{mode}/interpret",
                        json={"description": "Bez schodów", "constraints": constraints},
                    )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["constraints"]["max_steps"], 0)
                for field, value in fields.items():
                    self.assertEqual(response.json()[field], value)
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_missing_key_and_provider_failure_are_sanitized(self):
        constraints = {
            field: None
            for field in (
                "max_steps",
                "max_threshold_cm",
                "max_slope_percent",
                "min_entrance_width_cm",
                "max_distance_without_rest_m",
                "require_step_free_access",
                "require_accessible_toilet",
                "allowed_surfaces",
            )
        }
        for mode, agent in (("places", place_agent), ("routes", route_agent)):
            for key in ("", "test-key"):
                with (
                    self.subTest(mode=mode, key=key),
                    patch.dict(os.environ, {"OPENAI_API_KEY": key}),
                    patch.object(
                        agent,
                        "run",
                        new=AsyncMock(
                            side_effect=ModelHTTPError(429, "test", "private prompt")
                        ),
                    ),
                    TestClient(app) as client,
                ):
                    response = client.post(
                        f"/api/v1/{mode}/interpret",
                        json={
                            "description": "private prompt",
                            "constraints": constraints,
                        },
                    )
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(
                        response.json()["error"]["code"], "DEPENDENCY_UNAVAILABLE"
                    )
                    self.assertNotIn("private prompt", response.text)
                    invalid = client.post(
                        f"/api/v1/{mode}/interpret",
                        json={"description": "", "constraints": constraints},
                    )
                    self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":
    unittest.main()
