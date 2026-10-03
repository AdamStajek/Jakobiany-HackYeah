import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from hackyeah import models as m
from hackyeah.main import app
from hackyeah.routing import demo_graph, plan_route, walking_duration


class RoutingTests(unittest.TestCase):
    def setUp(self):
        weather = patch("hackyeah.api.get_weather", side_effect=OSError("offline test"))
        weather.start()
        self.addCleanup(weather.stop)
        self.nodes, self.edges = demo_graph()
        self.constraints = {field: None for field in m.Constraints.model_fields}

    def plan(self, **constraints):
        request = m.RoutePlanRequest(
            origin=m.PlaceReference(place_id="rynek"),
            destination=m.PlaceReference(place_id="wawel"),
            constraints=m.Constraints.model_validate(self.constraints | constraints),
        )
        return plan_route(request, self.nodes, self.edges)

    def test_shortest_and_step_free_detour(self):
        direct = self.plan().routes[0]
        detour = self.plan(require_step_free_access=True, max_steps=0).routes[0]
        self.assertEqual([s.id for s in direct.segments], ["rynek-wawel"])
        self.assertEqual(
            [s.id for s in detour.segments], ["rynek-planty", "planty-wawel"]
        )
        self.assertGreater(detour.distance_m, direct.distance_m)

    def test_constraints_and_missing_or_stale_facts(self):
        for constraints in (
            {"allowed_surfaces": ["gravel"]},
            {"max_slope_percent": 1},
            {"min_entrance_width_cm": 200},
            {"require_accessible_toilet": True},
            {"max_distance_without_rest_m": 100},
        ):
            with self.subTest(constraints=constraints):
                self.assertEqual(self.plan(**constraints).routes, [])
        self.assertTrue(self.plan(max_distance_without_rest_m=750).routes)
        for _, _, segment in self.edges:
            for fact in segment.facts:
                if fact.attribute == "lighting_available":
                    fact.valid_until = datetime.now(UTC) - timedelta(seconds=1)
        self.assertEqual(self.plan(require_lighting=True).routes, [])

    def test_total_steps_and_active_barrier(self):
        for _, _, segment in self.edges:
            for fact in segment.facts:
                if fact.attribute == "steps_count":
                    fact.value = 2
        self.assertEqual(self.plan(max_steps=1).routes, [])
        self.edges[0][2].barriers.append(
            m.Barrier(
                id="closed",
                kind="temporary",
                description="Zamknięcie",
                location=self.nodes["rynek"],
                fact_ids=[],
                starts_at=None,
                ends_at=None,
                status="confirmed",
            )
        )
        self.assertEqual(self.plan(max_steps=2).routes, [])
        self.assertTrue(self.plan(max_steps=4).routes)

    def test_longer_route_can_be_faster(self):
        direct = self.edges[0][2]
        for fact in direct.facts:
            if fact.attribute == "surface":
                fact.value = "ground"
            elif fact.attribute == "smoothness":
                fact.value = "bad"
            elif fact.attribute == "slope_percent":
                fact.value = 10
        route = self.plan().routes[0]
        self.assertEqual(
            [segment.id for segment in route.segments], ["rynek-planty", "planty-wawel"]
        )
        self.assertGreater(route.distance_m, direct.distance_m)
        self.assertLess(
            route.estimated_duration_s, walking_duration(direct, datetime.now(UTC))[0]
        )
        self.assertAlmostEqual(
            route.estimated_duration_s,
            sum(
                walking_duration(segment, datetime.now(UTC))[0]
                for segment in route.segments
            ),
        )
        constrained = self.plan(max_distance_without_rest_m=750).routes[0]
        self.assertAlmostEqual(
            constrained.estimated_duration_s, route.estimated_duration_s + 60
        )

    def test_time_estimate_defaults_and_penalties(self):
        segment = self.edges[2][2]
        now = datetime.now(UTC)
        base, assumed = walking_duration(segment, now)
        self.assertFalse(assumed)
        for fact in segment.facts:
            if fact.attribute == "steps_count":
                fact.value = 10
        self.assertAlmostEqual(walking_duration(segment, now)[0], base + 15)
        for fact in segment.facts:
            if fact.attribute == "surface":
                fact.status = "unconfirmed"
        slower, assumed = walking_duration(segment, now)
        self.assertTrue(assumed)
        self.assertGreater(slower, base)
        for _, _, edge in self.edges:
            for fact in edge.facts:
                if fact.attribute == "slope_percent":
                    fact.valid_until = now - timedelta(seconds=1)
        self.assertTrue(
            any("domyślnymi" in warning for warning in self.plan().warnings)
        )
        self.assertEqual(self.plan(max_slope_percent=10).routes, [])

    def test_impassable_segments_are_excluded(self):
        for _, _, segment in self.edges:
            for fact in segment.facts:
                if fact.attribute == "smoothness":
                    fact.value = "impassable"
        self.assertEqual(self.plan().routes, [])

    def test_profile_and_api(self):
        now = datetime.now(UTC)
        profile = m.Profile(
            id="demo",
            name="Bez schodów",
            description="",
            constraints=m.Constraints.model_validate(
                self.constraints | {"max_steps": 0}
            ),
            created_at=now,
            updated_at=now,
        )
        request = m.RoutePlanRequest(
            origin=self.nodes["rynek"],
            destination=m.PlaceReference(place_id="wawel"),
            profile_id="demo",
        )
        self.assertEqual(
            len(
                plan_route(request, self.nodes, self.edges, {"demo": profile})
                .routes[0]
                .segments
            ),
            2,
        )
        self.assertEqual(plan_route(request, self.nodes, self.edges).routes, [])
        # The old tiny graph remains a unit fixture; the public endpoint now delegates to the city planner.
        fixture = self.plan(max_steps=0)
        with (
            patch("hackyeah.api.plan_city_route", return_value=fixture),
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/v1/routes/plan",
                json={
                    "origin": {"place_id": "rynek"},
                    "destination": {"place_id": "wawel"},
                    "constraints": self.constraints | {"max_steps": 0},
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["routes"][0]["segments"]), 2)


if __name__ == "__main__":
    unittest.main()
