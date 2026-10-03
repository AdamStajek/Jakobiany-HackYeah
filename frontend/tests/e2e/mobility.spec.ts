import { test, expect } from "@playwright/test";
import type { RoutePlan, TravelMode } from "../../src/data/api";

const assessment = {
  status: "uncertain" as const,
  summary: "Dostępność wymaga sprawdzenia.",
  reasons: [],
};
const parking = {
  id: "zdmk:1",
  name: "Zamkowa 1",
  kind: "parking" as const,
  location: { lat: 50.0532, lon: 19.9294 },
  line: null,
  updated_at: null,
};
function plan(mode: TravelMode, useParking = false): RoutePlan {
  const geometry = {
    type: "LineString" as const,
    coordinates: [
      [19.9373, 50.0617],
      useParking ? [19.9294, 50.0532] : [19.9354, 50.0543],
    ] as [number, number][],
  };
  return {
    routes: [
      {
        id: `route-${mode}`,
        mode,
        parking: useParking ? parking : null,
        distance_m: 1500,
        estimated_duration_s: 600,
        computed_at: "2026-10-04T10:00:00Z",
        geometry,
        assessment,
        facts: [],
        segments: [
          {
            id: "segment",
            mode,
            geometry,
            distance_m: 1500,
            assessment,
            facts: [],
            barriers: [],
            rest_points: [],
            temporary_difficulties: [],
            instruction:
              mode === "transit"
                ? "Linia 52 → Czerwone Maki. Wsiądź: Teatr Bagatela; wysiądź: Wawel."
                : "Jedź do celu.",
            line: mode === "transit" ? "52" : null,
            from_stop: "Teatr Bagatela",
            to_stop: "Wawel",
            departure_at: mode === "transit" ? "2026-10-04T10:00:00Z" : null,
            arrival_at: "2026-10-04T10:10:00Z",
            delay_s: mode === "transit" ? 120 : null,
          },
        ],
      },
    ],
    warnings: [],
    attribution: [],
  };
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/routes/mobility?**", (route) => {
    const kind = new URL(route.request().url()).searchParams.get("kind");
    const items =
      kind === "parking"
        ? [parking]
        : kind === "vehicles"
          ? [
              {
                ...parking,
                id: "vehicle:1",
                name: "Pojazd 52",
                kind: "vehicle",
                line: "52",
              },
            ]
          : [
              {
                ...parking,
                id: "stop:1",
                name: "Teatr Bagatela",
                kind: "stop",
              },
            ];
    return route.fulfill({ json: { items, warnings: [], attribution: [] } });
  });
});

test("ikony wybierają środek transportu; opóźnienie jest widoczne także w szczegółach", async ({
  page,
}) => {
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/v1/routes/plan", (route) => {
    const body = route.request().postDataJSON();
    requests.push(body);
    return route.fulfill({ json: plan(body.mode, body.accessible_parking) });
  });
  await page.goto("/route");
  await expect(
    page.getByRole("button", { name: "Pieszo", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Komunikacja miejska", exact: true })
    .click();
  await expect(page.locator(".mobility-stop").first()).toBeAttached();
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByText("Opóźnienie 2 min", { exact: false }),
  ).toBeVisible();
  expect(requests[0]).toMatchObject({
    mode: "transit",
    accessible_parking: false,
    origin: { place_id: "rynek" },
    destination: { place_id: "wawel" },
  });
  await page
    .getByRole("link", { name: "Szczegóły trasy", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: /Linia 52/ })).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Opóźnienie 2 min", { exact: false }),
  ).toBeVisible();
});

test("samochód prowadzi do celu albo do wskazanego parkingu OZN; zmiana trybu usuwa wynik", async ({
  page,
}) => {
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/v1/routes/plan", (route) => {
    const body = route.request().postDataJSON();
    requests.push(body);
    return route.fulfill({ json: plan(body.mode, body.accessible_parking) });
  });
  await page.goto("/route");
  await page.getByRole("button", { name: "Samochód", exact: true }).click();
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByRole("link", { name: "Szczegóły trasy" }),
  ).toBeVisible();
  expect(requests[0]).toMatchObject({ mode: "car", accessible_parking: false });
  await page
    .getByLabel(
      "Prowadź do miejsca parkingowego dla osób z niepełnosprawnościami",
    )
    .check();
  await expect(page.getByRole("link", { name: "Szczegóły trasy" })).toHaveCount(
    0,
  );
  await expect(page.locator(".mobility-parking").first()).toBeAttached();
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(page.getByText("Samochód · Parking: Zamkowa 1")).toBeVisible();
  expect(requests[1]).toMatchObject({ mode: "car", accessible_parking: true });
  await page.getByRole("button", { name: "Pieszo", exact: true }).click();
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByRole("link", { name: "Szczegóły trasy" }),
  ).toBeVisible();
  expect(requests[2]).toMatchObject({
    mode: "walk",
    accessible_parking: false,
  });
});

test("wybrany czas wyjazdu trafia do API; brak telemetrii nie udaje punktualnego kursu", async ({
  page,
}) => {
  let body: Record<string, unknown> = {};
  await page.route("**/api/v1/routes/plan", (route) => {
    body = route.request().postDataJSON();
    const result = plan("transit");
    result.routes[0].segments[0].delay_s = null;
    return route.fulfill({ json: result });
  });
  await page.goto("/route");
  await page
    .getByRole("button", { name: "Komunikacja miejska", exact: true })
    .click();
  await page.getByLabel("Wyjazd", { exact: false }).fill("2026-10-04T12:00");
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByText("Według rozkładu", { exact: false }),
  ).toBeVisible();
  expect(typeof body.departure_at).toBe("string");
  expect(body.mode).toBe("transit");
  await expect(
    page.getByText("Dane bieżące: punktualnie", { exact: false }),
  ).toHaveCount(0);
});
