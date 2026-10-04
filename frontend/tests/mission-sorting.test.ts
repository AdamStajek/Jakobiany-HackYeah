import { expect, it } from "vitest";
import type { Mission } from "../src/data/api";
import { missionDistance, sortMissions } from "../src/data/missionSorting";

it("sorts by descending points or ascending distance before pagination", () => {
  const origin = { lat: 50, lon: 20 };
  const missions = Array.from(
    { length: 23 },
    (_, index) =>
      ({
        id: String(index),
        points: index,
        priority: 2,
        location: { lat: 50 + index / 100, lon: 20 },
      }) as Mission,
  );
  const points = sortMissions(missions, "points", origin);
  expect(points.slice(0, 10).map((mission) => mission.points)).toEqual([
    22, 21, 20, 19, 18, 17, 16, 15, 14, 13,
  ]);
  expect(points.slice(20, 30)).toHaveLength(3);
  const unknown = { ...missions[0], id: "unknown", location: null };
  const distances = sortMissions(
    [unknown, ...missions].reverse(),
    "distance",
    origin,
  );
  expect(distances[0].id).toBe("0");
  expect(distances.at(-1)?.id).toBe("unknown");
  expect(missionDistance(missions[1], origin)).toBeCloseTo(1111.95, 1);
  expect(sortMissions(missions, "distance", null)).toEqual(points);
  expect(missions[0].id).toBe("0");
});
