import io
import sqlite3
import time
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import BadZipFile, ZipFile

from fastapi.testclient import TestClient
from google.transit import gtfs_realtime_pb2 as gtfs
from pydantic import ValidationError

from hackyeah import models as m
from hackyeah.main import app
from hackyeah.mobility_data import (
    realtime,
    refresh_parking,
    refresh_schedule,
    seconds,
)
from hackyeah.mobility_routing import (
    Connection,
    Journey,
    active_services,
    connections_for,
    plan_car,
    plan_transit,
    scan_connections,
    segment,
    trip_connections,
)


def archive():
    data = io.BytesIO()
    with ZipFile(data, "w") as z:
        for name, content in {
            "stops": "stop_id,stop_name,stop_lat,stop_lon,wheelchair_boarding\na,Start,50.06,19.93,1\nb,Koniec,50.06,19.94,1\nc,Przesiadka,50.06,19.95,1\n",
            "routes": "route_id,route_short_name,route_type\nr,1,0\n",
            "trips": "route_id,service_id,trip_id,trip_headsign,shape_id,wheelchair_accessible\nr,s,t,Koniec,shape,1\n",
            "calendar": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\ns,1,1,1,1,1,1,1,20260101,20261231\n",
            "calendar_dates": "service_id,date,exception_type\ns,20261005,2\n",
            # Nonconsecutive sequences and service times after midnight are valid GTFS.
            "stop_times": "trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type\nt,25:00:00,25:00:00,a,10,0,0\nt,25:10:00,25:10:00,b,20,0,0\nt,25:20:00,25:20:00,c,30,0,0\n",
            "shapes": "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\nshape,50.06,19.93,1\nshape,50.061,19.935,2\nshape,50.06,19.94,3\nshape,50.06,19.95,4\n",
        }.items():
            z.writestr(f"{name}.txt", content)
    return data.getvalue()


def connection(trip="A:t", a="A:a", b="A:b", dep=100, arr=200, **values):
    return Connection(
        trip=trip,
        sequence=10,
        target_sequence=20,
        a=a,
        b=b,
        departure=dep,
        arrival=arr,
        pickup=0,
        dropoff=0,
        line="1",
        headsign="Koniec",
        shape="A:shape",
        wheelchair=1,
        delay=None,
        service_day="20261004",
        **values,
    )


class MobilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "schedule.sqlite3"
        with patch("hackyeah.mobility_data.download", return_value=archive()):
            refresh_schedule(self.path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.stops = {r["id"]: dict(r) for r in self.db.execute("SELECT * FROM stops")}

    def test_feed_namespaces_calendar_exceptions_and_overnight(self):
        self.assertEqual(self.db.execute("SELECT count(*) FROM stops").fetchone()[0], 9)
        self.assertIn("A:s", active_services(self.db, datetime(2026, 10, 4).date()))
        self.assertNotIn("A:s", active_services(self.db, datetime(2026, 10, 5).date()))
        # 22:30 UTC = 00:30 the next day in Kraków; 25:00 belongs to the previous service day.
        departure = datetime(2026, 10, 4, 22, 30, tzinfo=UTC)
        connections = connections_for(self.db, departure, {})
        self.assertEqual(len(connections), 6)
        self.assertEqual(connections[0].target_sequence, 20)
        self.assertEqual(
            datetime.fromtimestamp(connections[0].departure, UTC).isoformat(),
            "2026-10-04T23:00:00+00:00",
        )
        self.assertEqual(seconds("25:30:00"), 91800)

    def test_rt_delays_absolute_times_no_data_cancellation_and_skipped_stop(self):
        rows = [
            dict(r)
            for r in self.db.execute(
                "SELECT c.*,t.headsign,t.shape,t.wheelchair,r.line FROM connections c JOIN trips t ON t.id=c.trip JOIN routes r ON r.id=t.route WHERE c.trip='A:t' ORDER BY c.sequence"
            )
        ]
        update = gtfs.TripUpdate()
        update.trip.trip_id = "t"
        s = update.stop_time_update.add(stop_sequence=10)
        s.departure.delay = 120
        adjusted = trip_connections(rows, 0, update, "20261004")
        self.assertEqual(adjusted[0].departure, 90120)
        self.assertEqual(adjusted[1].delay, 120)
        s.departure.Clear()
        s.departure.time = 89940
        self.assertEqual(trip_connections(rows, 0, update, "20261004")[0].delay, -60)
        update.stop_time_update.add(stop_sequence=20, schedule_relationship=2)
        self.assertIsNone(trip_connections(rows, 0, update, "20261004")[1].delay)
        update.stop_time_update[1].schedule_relationship = 1
        adjusted = trip_connections(rows, 0, update, "20261004")
        self.assertEqual(adjusted[0].dropoff, 1)
        self.assertEqual(adjusted[1].pickup, 1)
        update.trip.schedule_relationship = 3
        self.assertEqual(trip_connections(rows, 0, update, "20261004"), [])
        update.trip.start_date = "20261003"
        self.assertEqual(len(trip_connections(rows, 0, update, "20261004")), 2)

    def test_transfer_missed_due_to_delay_and_staying_aboard_skipped_stop(self):
        first = connection()
        next_trip = connection("A:u", "A:b", "A:c", 250, 300)
        initial = {"A:a": Journey(0, None, "walk")}
        reached = scan_connections([first, next_trip], initial, {}, self.stops)
        self.assertEqual(reached["A:c"].time, 300)
        delayed = replace(first, arrival=240)
        self.assertNotIn(
            "A:c", scan_connections([delayed, next_trip], initial, {}, self.stops)
        )
        skipped = replace(first, dropoff=1)
        continuation = replace(
            next_trip, trip="A:t", pickup=1, sequence=20, target_sequence=30
        )
        reached = scan_connections([skipped, continuation], initial, {}, self.stops)
        self.assertNotIn("A:b", reached)
        self.assertIn("A:c", reached)
        inaccessible = replace(first, wheelchair=2)
        self.assertNotIn(
            "A:b", scan_connections([inaccessible], initial, {}, self.stops, True)
        )

    def test_rt_stale_feed_is_not_used(self):
        feed = gtfs.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(time.time()) - 600
        with (
            patch(
                "hackyeah.mobility_data.download", return_value=feed.SerializeToString()
            ),
            patch.dict("hackyeah.mobility_data._rt_cache", {}, clear=True),
        ):
            self.assertIsNone(realtime("A", "TripUpdates"))

    def test_failed_refresh_preserves_schedule(self):
        before = self.path.read_bytes()
        with patch("hackyeah.mobility_data.download", side_effect=OSError("offline")):
            with self.assertRaises(OSError):
                refresh_schedule(self.path)
        self.assertEqual(before, self.path.read_bytes())
        with patch("hackyeah.mobility_data.download", return_value=b"invalid ZIP"):
            with self.assertRaises(BadZipFile):
                refresh_schedule(self.path)
        self.assertEqual(before, self.path.read_bytes())

    def test_parking_pagination_and_wgs84(self):
        path = Path(self.directory.name) / "parking.json"
        import json

        pages = [
            {
                "features": [
                    {
                        "attributes": {"OBJECTID": 1, "punkt_adresowy": "Zamkowa 1"},
                        "geometry": {"x": 19.93, "y": 50.06},
                    }
                ],
                "exceededTransferLimit": True,
            },
            {
                "features": [
                    {
                        "attributes": {"OBJECTID": 2, "punkt_adresowy": "Piltza 55"},
                        "geometry": {"x": 19.89, "y": 50.01},
                    }
                ]
            },
        ]
        with patch(
            "hackyeah.mobility_data.download",
            side_effect=[json.dumps(p).encode() for p in pages],
        ) as request:
            refresh_parking(path)
        self.assertIn("resultOffset=1", request.call_args_list[1].args[0])
        items = json.loads(path.read_text())["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["location"], {"lat": 50.06, "lon": 19.93})

    def test_transit_full_route_uses_schedule_and_pedestrian_legs(self):
        request = m.RoutePlanRequest(
            origin=m.Coordinates(lat=50.06, lon=19.93),
            destination=m.Coordinates(lat=50.06, lon=19.95),
            mode="transit",
            departure_at=datetime(2026, 10, 4, 22, 30, tzinfo=UTC),
        )

        def foot(_request, _graph, start, finish):
            seg = segment("walk", [start, finish], "Podejdź pieszo.")
            route = m.Route(
                id="walk",
                distance_m=seg.distance_m,
                estimated_duration_s=60,
                geometry=seg.geometry,
                segments=[seg],
                facts=seg.facts,
                assessment=seg.assessment,
                computed_at=datetime.now(UTC),
            )
            return m.RoutePlanResponse(routes=[route], warnings=[], attribution=[])

        def nearby(_request, _graph, _stops, point, arriving):
            return {"A:c" if arriving else "A:a": foot(request, None, point, point)}

        with (
            patch(
                "hackyeah.mobility_routing.ensure_data", return_value=(self.path, [])
            ),
            patch("hackyeah.mobility_routing.get_graph", return_value=object()),
            patch("hackyeah.mobility_routing.walk_leg", side_effect=foot),
            patch("hackyeah.mobility_routing.nearby_walks", side_effect=nearby),
        ):
            result = plan_transit(request)
        self.assertEqual(result.routes[0].mode, "transit")
        transit = next(s for s in result.routes[0].segments if s.mode == "transit")
        self.assertEqual(transit.line, "1")
        self.assertIsNone(transit.delay_s)
        self.assertEqual(transit.from_stop, "Start")
        self.assertEqual(transit.to_stop, "Przesiadka")
        self.assertEqual(result.routes[0].estimated_duration_s, 3060)

    def test_car_ends_at_parking_only_if_requested(self):
        start, goal = (19.93, 50.06), (19.95, 50.06)
        parking = m.MobilityPoint(
            id="zdmk:1",
            name="Parking",
            kind="parking",
            location=m.Coordinates(lon=19.949, lat=50.06),
        )
        source = m.Source(
            type="other",
            label="ZDMK",
            url="https://example.test",
            license=None,
            retrieved_at=datetime.now(UTC),
        )

        def drive(a, b):
            return {
                "routes": [
                    {
                        "distance": 1400,
                        "duration": 180,
                        "geometry": {"coordinates": [a, b]},
                        "legs": [{"steps": []}],
                    }
                ]
            }

        request = m.RoutePlanRequest(
            origin=m.Coordinates(lon=start[0], lat=start[1]),
            destination=m.Coordinates(lon=goal[0], lat=goal[1]),
            mode="car",
        )
        with (
            patch("hackyeah.mobility_routing.driving", side_effect=drive) as route,
            patch(
                "hackyeah.mobility_routing.parking_points",
                return_value=([parking], [], source),
            ) as points,
        ):
            direct = plan_car(request)
            points.assert_not_called()
            route.assert_called_with(start, goal)
            self.assertIsNone(direct.routes[0].parking)
            request.accessible_parking = True
            parked = plan_car(request)
            route.assert_called_with(
                start, (parking.location.lon, parking.location.lat)
            )
        self.assertEqual(parked.routes[0].parking.id, "zdmk:1")
        self.assertEqual(parked.routes[0].geometry.coordinates[-1], (19.949, 50.06))

    def test_request_rejects_parking_in_pedestrian_mode_and_api_dispatch(self):
        with self.assertRaises(ValidationError):
            m.RoutePlanRequest(
                origin={"place_id": "rynek"},
                destination={"place_id": "wawel"},
                accessible_parking=True,
            )
        body = {
            "origin": {"place_id": "rynek"},
            "destination": {"place_id": "wawel"},
            "mode": "car",
            "accessible_parking": True,
        }
        response = m.RoutePlanResponse(
            routes=[], warnings=["Brak miejsc"], attribution=[]
        )
        # No lifespan: these read-only endpoints don't need account/database initialization.
        with patch("hackyeah.api.plan_mobility_route", return_value=response) as plan:
            result = TestClient(app).post("/api/v1/routes/plan", json=body)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(plan.call_args.args[0].mode, "car")
        self.assertTrue(plan.call_args.args[0].accessible_parking)


if __name__ == "__main__":
    unittest.main()
