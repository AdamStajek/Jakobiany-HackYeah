import json
import sqlite3
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from hackyeah import models as m
from hackyeah.city_routing import CityGraph, plan_city_route
from hackyeah.main import app


class CityRoutingTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "graph.sqlite3"
        self.nodes = {
            1: (19.93, 50.06),
            2: (19.931, 50.06),
            3: (19.932, 50.06),
            4: (19.93, 50.061),
            5: (19.932, 50.061),
        }
        self.now = datetime.now(UTC).isoformat()

    def graph(
        self, direct=None, detour=None, node_tags=None, amenities=None, links=None
    ):
        self.path.unlink(missing_ok=True)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript("""
                CREATE TABLE metadata(key,value);
                CREATE TABLE nodes(id,lon,lat,tags,updated);
                CREATE TABLE ways(id,tags,updated);
                CREATE TABLE links(a,b,way,position);
                CREATE TABLE amenities(id,lon,lat,tags,updated);
            """)
            defaults = {
                "highway": "footway",
                "surface": "asphalt",
                "lit": "yes",
                "incline": "2%",
                "width": "2",
            }
            db.execute(
                "INSERT INTO metadata VALUES('generated_at',?)", (json.dumps(self.now),)
            )
            db.executemany(
                "INSERT INTO nodes VALUES(?,?,?,?,?)",
                [
                    (
                        node,
                        *point,
                        json.dumps((node_tags or {}).get(node, {})),
                        self.now,
                    )
                    for node, point in self.nodes.items()
                ],
            )
            db.executemany(
                "INSERT INTO ways VALUES(?,?,?)",
                [
                    (10, json.dumps(defaults | (direct or {})), self.now),
                    (20, json.dumps(defaults | (detour or {})), self.now),
                ],
            )
            db.executemany(
                "INSERT INTO links VALUES(?,?,?,?)",
                links
                or [
                    (1, 2, 10, 0),
                    (2, 3, 10, 1),
                    (1, 4, 20, 0),
                    (4, 5, 20, 1),
                    (5, 3, 20, 2),
                ],
            )
            for node, tags in (amenities or {}).items():
                db.execute(
                    "INSERT INTO amenities VALUES(?,?,?,?,?)",
                    (node, *self.nodes[node], json.dumps(tags), self.now),
                )
            db.commit()
        return CityGraph(self.path)

    def request(self, **constraints):
        return m.RoutePlanRequest(
            origin=m.Coordinates(lon=19.93, lat=50.06),
            destination=m.Coordinates(lon=19.932, lat=50.06),
            constraints=m.Constraints.model_validate(
                {field: None for field in m.Constraints.model_fields} | constraints
            ),
        )

    def test_step_free_detour_and_way_step_count_not_repeated_per_piece(self):
        graph = self.graph(direct={"highway": "steps", "step_count": "6"})
        direct = plan_city_route(self.request(), graph).routes[0]
        detour = plan_city_route(
            self.request(max_steps=0, require_step_free_access=True), graph
        ).routes[0]
        self.assertLess(direct.distance_m, detour.distance_m)
        self.assertIn(self.nodes[4], detour.geometry.coordinates)
        self.assertEqual(
            sum(e.steps for e in graph.edges if e.way == 10 and e.a < e.b), 6
        )
        self.assertEqual(detour.assessment.status, "uncertain")
        self.assertTrue(all(f.status == "unconfirmed" for f in detour.facts))
        self.assertEqual(detour.geometry.coordinates[0], self.nodes[1])
        self.assertEqual(detour.geometry.coordinates[-1], self.nodes[3])

    def test_walk_returns_fastest_with_stairs_and_constrained_detour(self):
        from hackyeah.mobility_routing import plan_mobility_route

        graph = self.graph(direct={"highway": "steps", "step_count": "6"})
        with patch("hackyeah.mobility_routing.get_graph", return_value=graph):
            result = plan_mobility_route(
                self.request(max_steps=0, require_step_free_access=True)
            )
        routes = {route.variant: route for route in result.routes}
        self.assertEqual(set(routes), {"fastest", "constrained"})
        self.assertLess(
            routes["fastest"].estimated_duration_s,
            routes["constrained"].estimated_duration_s,
        )
        self.assertIn(self.nodes[4], routes["constrained"].geometry.coordinates)
        self.assertNotIn(self.nodes[4], routes["fastest"].geometry.coordinates)
        self.assertEqual(
            routes["fastest"].assessment.status, "does_not_meet_requirements"
        )
        self.assertTrue(
            any(
                "Schody" in reason.message
                for reason in routes["fastest"].assessment.reasons
            )
        )

    def test_fastest_still_available_when_step_free_route_is_missing(self):
        from hackyeah.mobility_routing import plan_mobility_route

        graph = self.graph(
            direct={"highway": "steps", "step_count": "6"},
            links=[(1, 2, 10, 0), (2, 3, 10, 1)],
        )
        with patch("hackyeah.mobility_routing.get_graph", return_value=graph):
            result = plan_mobility_route(self.request(max_steps=0))
        self.assertEqual([route.variant for route in result.routes], ["fastest"])

    def test_step_free_slope_limit_excludes_steep_ways_and_nodes(self):
        request = self.request(
            max_steps=0, require_step_free_access=True, max_slope_percent=5
        )
        for graph in (
            self.graph(direct={"incline": "-12%"}),
            self.graph(node_tags={2: {"incline": "12%"}}),
        ):
            route = plan_city_route(request, graph).routes[0]
            self.assertIn(self.nodes[4], route.geometry.coordinates)
            self.assertNotIn(self.nodes[2], route.geometry.coordinates)
        graph = self.graph(direct={"incline": "12%"}, detour={"incline": "12%"})
        self.assertEqual(plan_city_route(request, graph).routes, [])
        graph = self.graph(direct={"incline": "5%"})
        self.assertIn(
            self.nodes[2],
            plan_city_route(request, graph).routes[0].geometry.coordinates,
        )

    def test_profile_prefers_lit_smooth_paved_less_steep_path_and_low_kerbs(self):
        for tags, constraints in [
            ({"lit": "no"}, {"require_lighting": True}),
            ({"surface": "gravel"}, {"allowed_surfaces": ["asphalt"]}),
            ({"smoothness": "bad"}, {"allowed_smoothness": ["good"]}),
            ({"incline": "12%"}, {"max_slope_percent": 3}),
            ({"width": "0.5"}, {"min_entrance_width_cm": 100}),
        ]:
            with self.subTest(tags=tags):
                graph = self.graph(direct=tags, detour={"smoothness": "good"})
                result = plan_city_route(self.request(**constraints), graph)
                self.assertIn(self.nodes[4], result.routes[0].geometry.coordinates)
        graph = self.graph(node_tags={2: {"barrier": "kerb", "kerb:height": "0.2"}})
        result = plan_city_route(self.request(max_kerb_height_cm=2), graph)
        self.assertIn(self.nodes[4], result.routes[0].geometry.coordinates)

    def test_rest_and_accessible_toilet_can_justify_detour(self):
        self.nodes.update({4: (19.9305, 50.0605), 5: (19.9315, 50.0605)})
        for amenities, constraints in [
            (
                {4: {"amenity": "bench"}, 5: {"amenity": "bench"}},
                {"max_distance_without_rest_m": 100},
            ),
            (
                {4: {"amenity": "toilets", "toilets:wheelchair": "yes"}},
                {"require_accessible_toilet": True},
            ),
        ]:
            with self.subTest(constraints=constraints):
                result = plan_city_route(
                    self.request(**constraints), self.graph(amenities=amenities)
                )
                self.assertIn(self.nodes[4], result.routes[0].geometry.coordinates)

    def test_unknowns_allow_uncertain_route_and_unavoidable_inconvenience_is_reported(
        self,
    ):
        graph = self.graph(direct={"surface": "gravel"}, detour={"surface": "gravel"})
        route = plan_city_route(
            self.request(allowed_surfaces=["asphalt"]), graph
        ).routes[0]
        self.assertEqual(route.assessment.status, "does_not_meet_requirements")
        self.assertTrue(
            any(
                reason.code == "OSM_INCONVENIENCE"
                for reason in route.assessment.reasons
            )
        )
        unknown = self.graph(
            direct={"surface": "", "incline": "up"},
            detour={"surface": "", "incline": "up"},
        )
        self.assertEqual(
            plan_city_route(
                self.request(allowed_surfaces=["asphalt"], max_slope_percent=3), unknown
            )
            .routes[0]
            .assessment.status,
            "uncertain",
        )

    def test_oneway_foot_access_barriers_and_same_edge_projection(self):
        graph = self.graph(direct={"oneway:foot": "yes"}, detour={"oneway:foot": "yes"})
        request = m.RoutePlanRequest(
            origin=m.Coordinates(lon=19.9318, lat=50.06),
            destination=m.Coordinates(lon=19.9312, lat=50.06),
        )
        self.assertEqual(plan_city_route(request, graph).routes, [])
        request.origin, request.destination = request.destination, request.origin
        route = plan_city_route(request, graph).routes[0]
        self.assertLess(route.distance_m, 50)
        self.assertAlmostEqual(route.geometry.coordinates[0][0], 19.9312)
        graph = self.graph(
            node_tags={2: {"access": "no"}}, links=[(1, 2, 10, 0), (2, 3, 10, 1)]
        )
        self.assertEqual(plan_city_route(self.request(), graph).routes, [])
        far = self.request()
        far.origin = m.Coordinates(lon=20.2, lat=50.12)
        self.assertEqual(plan_city_route(far, graph).routes, [])

    def test_api_uses_city_graph_and_passes_constraints(self):
        graph = self.graph(direct={"highway": "steps", "step_count": "6"})
        with (
            patch("hackyeah.city_routing.get_graph", return_value=graph),
            patch("hackyeah.mobility_routing.get_graph", return_value=graph),
            patch("hackyeah.api.get_weather", side_effect=OSError("offline")),
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/v1/routes/plan",
                json=self.request(
                    require_step_free_access=True, max_steps=0
                ).model_dump(mode="json"),
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            list(self.nodes[4]), response.json()["routes"][0]["geometry"]["coordinates"]
        )
        self.assertEqual(response.json()["attribution"][0]["license"], "ODbL")

    def test_saved_profile_is_loaded_before_search(self):
        from types import SimpleNamespace

        graph = self.graph(direct={"highway": "steps", "step_count": "6"})
        constraints = self.request(
            require_step_free_access=True, max_steps=0
        ).constraints
        body = self.request().model_dump(mode="json")
        body.pop("constraints")
        body["profile_id"] = "saved-profile"
        with (
            patch("hackyeah.city_routing.get_graph", return_value=graph),
            patch("hackyeah.mobility_routing.get_graph", return_value=graph),
            patch("hackyeah.api.get_weather", side_effect=OSError("offline")),
            patch(
                "hackyeah.api.auth.require_session",
                return_value=SimpleNamespace(id="user-id"),
            ),
            patch(
                "hackyeah.profiles.get",
                return_value=SimpleNamespace(constraints=constraints),
            ) as profile,
            TestClient(app) as client,
        ):
            response = client.post("/api/v1/routes/plan", json=body)
        profile.assert_called_once_with("user-id", "saved-profile")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            list(self.nodes[4]), response.json()["routes"][0]["geometry"]["coordinates"]
        )


if __name__ == "__main__":
    unittest.main()
