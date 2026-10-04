import type { Mission } from "./api";

type Location = { lat: number; lon: number } | null;

export function missionDistance(mission: Mission, origin: Location): number {
  if (!origin || !mission.location) return Infinity;
  const rad = Math.PI / 180;
  const lat = (mission.location.lat - origin.lat) * rad;
  const lon = (mission.location.lon - origin.lon) * rad;
  const a =
    Math.sin(lat / 2) ** 2 +
    Math.cos(origin.lat * rad) *
      Math.cos(mission.location.lat * rad) *
      Math.sin(lon / 2) ** 2;
  return 6371000 * 2 * Math.asin(Math.sqrt(Math.min(1, a)));
}

export function sortMissions(
  missions: Mission[],
  sort: "points" | "distance",
  origin: Location,
): Mission[] {
  return [...missions].sort((a, b) => {
    if (sort === "distance" && origin) {
      const distanceA = missionDistance(a, origin);
      const distanceB = missionDistance(b, origin);
      if (distanceA !== distanceB) return distanceA - distanceB;
    }
    return (
      b.points - a.points || a.priority - b.priority || a.id.localeCompare(b.id)
    );
  });
}
