import { test, expect } from "@playwright/test";
import type { RoutePlan } from "../../src/data/api";

const assessment = {
  status: "meets_requirements" as const,
  summary: "Spełnia ograniczenia na danych demonstracyjnych.",
  reasons: [],
};
function response(stepFree = false): RoutePlan {
  const coordinates: [number, number][] = stepFree
    ? [
        [19.9373, 50.0617],
        [19.9325, 50.0605],
        [19.9354, 50.0543],
      ]
    : [
        [19.9373, 50.0617],
        [19.9354, 50.0543],
      ];
  return {
    routes: [
      {
        id: "calculated-route",
        distance_m: stepFree ? 1000 : 800,
        estimated_duration_s: stepFree ? 900 : 720,
        assessment,
        geometry: { type: "LineString", coordinates },
        computed_at: "2026-10-03T10:00:00Z",
        facts: [],
        segments: coordinates.slice(1).map((point, index) => ({
          id: `segment-${index}`,
          distance_m: stepFree ? 500 : 800,
          instruction:
            stepFree && index === 0 ? "Idź do Plant." : "Idź do Wawelu.",
          geometry: {
            type: "LineString",
            coordinates: [coordinates[index], point],
          },
          assessment,
          facts: [],
          barriers: [],
          rest_points: [],
          temporary_difficulties: [],
        })),
      },
    ],
    warnings: ["Prototyp: syntetyczna sieć centrum Krakowa."],
    attribution: [],
  };
}

test("kule lub wózek automatycznie ustawiają brak schodów i limit nachylenia", async ({
  page,
}) => {
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/v1/routes/plan", (route) => {
    requests.push(route.request().postDataJSON());
    return route.fulfill({ json: response(true) });
  });
  await page.goto("/route");
  const mobility = page.getByLabel("Poruszam się o kulach lub na wózku");
  await mobility.check();
  await expect(page.getByLabel("Unikaj schodów")).toBeChecked();
  await expect(page.getByLabel("Maks. nachylenie (%)")).toHaveValue("5");
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0]).toMatchObject({
    constraints: {
      max_steps: 0,
      require_step_free_access: true,
      max_slope_percent: 5,
    },
  });
  await mobility.uncheck();
  await expect(page.getByLabel("Unikaj schodów")).not.toBeChecked();
  await expect(page.getByLabel("Maks. nachylenie (%)")).toHaveValue("");
  await page.getByLabel("Maks. nachylenie (%)").fill("3");
  await mobility.check();
  await expect(page.getByLabel("Maks. nachylenie (%)")).toHaveValue("3");
});

test("planer otrzymuje punkty i potrzeby; mapa, szczegóły i nawigacja używają odpowiedzi API", async ({
  page,
}) => {
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/v1/routes/plan", (route) => {
    const body = route.request().postDataJSON();
    requests.push(body);
    return route.fulfill({
      json: response(body.constraints.require_step_free_access === true),
    });
  });
  await page.goto("/route");
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByRole("heading", { name: "12 min", exact: true }),
  ).toBeVisible();
  expect(requests[0]).toMatchObject({
    origin: { place_id: "rynek" },
    destination: { place_id: "wawel" },
    constraints: { max_steps: null },
  });
  const line = page.locator(".map-canvas path.leaflet-interactive").first();
  await expect(line).toBeAttached();
  const directPath = await line.getAttribute("d");
  await page.getByLabel("Unikaj schodów").check();
  await expect(
    page.getByRole("link", { name: "Szczegóły trasy", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByRole("heading", { name: "15 min", exact: true }),
  ).toBeVisible();
  expect(requests[1]).toMatchObject({
    constraints: { max_steps: 0, require_step_free_access: true },
  });
  await expect(line).not.toHaveAttribute("d", directPath!);
  await page
    .getByRole("link", { name: "Szczegóły trasy", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Idź do Plant.", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Idź do Plant.", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Podgląd nawigacji", exact: true })
    .click();
  await expect(page.getByText("Podgląd kroku 1 z 2")).toBeVisible();
  await page.getByRole("button", { name: "Następny krok" }).click();
  await expect(
    page.getByRole("heading", { name: "Idź do Wawelu.", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Podgląd kroku 2 z 2")).toBeVisible();
  await expect(page.getByRole("button", { name: "Następny krok" })).toHaveCount(
    0,
  );
  expect(requests).toHaveLength(2);
});

test("punkt spoza grafu i błąd API nie pokazują zastępczej trasy; można ponowić planowanie", async ({
  page,
}) => {
  let requests = 0;
  await page.route("**/api/v1/places/outside", (route) =>
    route.fulfill({ json: { name: "Miejsce poza siecią" } }),
  );
  await page.route("**/api/v1/routes/plan", (route) => {
    requests++;
    if (requests === 1) {
      expect(route.request().postDataJSON().destination).toEqual({
        place_id: "outside",
      });
      return route.fulfill({
        json: {
          routes: [],
          warnings: ["Punkt poza grafem demonstracyjnym."],
          attribution: [],
        },
      });
    }
    if (requests === 2)
      return route.fulfill({
        status: 503,
        json: { error: { message: "Planer chwilowo niedostępny." } },
      });
    expect(route.request().postDataJSON().origin).toEqual({
      place_id: "planty",
    });
    return route.fulfill({ json: response() });
  });
  await page.goto("/route?to=outside");
  await expect(
    page.getByRole("combobox", { name: "Dokąd", exact: true }),
  ).toContainText("Miejsce poza siecią");
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByText("Punkt poza grafem demonstracyjnym.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Szczegóły trasy" })).toHaveCount(
    0,
  );
  await expect(
    page.locator(".map-canvas path.leaflet-interactive"),
  ).toHaveCount(0);
  await page
    .getByRole("combobox", { name: "Dokąd", exact: true })
    .selectOption("wawel");
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "Planer chwilowo niedostępny.",
  );
  await page
    .getByRole("combobox", { name: "Skąd", exact: true })
    .selectOption("planty");
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByRole("link", { name: "Szczegóły trasy", exact: true }),
  ).toBeVisible();
});

test("trasa bez odcinków i brak zapisanej trasy są obsługiwane", async ({
  page,
}) => {
  await page.goto("/navigation?route=missing");
  await expect(
    page.getByRole("heading", { name: "Brak zaplanowanej trasy" }),
  ).toBeVisible();
  await page.route("**/api/v1/routes/plan", (route) => {
    const plan = response();
    plan.routes[0].distance_m = 0;
    plan.routes[0].estimated_duration_s = 0;
    plan.routes[0].segments = [];
    plan.routes[0].geometry.coordinates = [
      [19.9373, 50.0617],
      [19.9373, 50.0617],
    ];
    return route.fulfill({ json: plan });
  });
  await page.goto("/route");
  await page
    .getByRole("combobox", { name: "Dokąd", exact: true })
    .selectOption("rynek");
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await page.getByRole("link", { name: "Uruchom podgląd nawigacji" }).click();
  await expect(
    page.getByRole("heading", { name: "Jesteś w punkcie docelowym." }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Następny krok" })).toHaveCount(
    0,
  );
});

test("wybór miejsc z całego miasta i dowolnych współrzędnych na mapie", async ({
  page,
}) => {
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/v1/routes/points?**", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: "node/123",
            name: "Muzeum w Nowej Hucie",
            address: "os. Centrum E 1",
            location: { lat: 50.072, lon: 20.037 },
          },
        ],
        next_cursor: null,
      },
    }),
  );
  await page.route("**/api/v1/places/node%2F123", (route) =>
    route.fulfill({ json: { name: "Muzeum w Nowej Hucie" } }),
  );
  await page.route("**/api/v1/routes/plan", (route) => {
    requests.push(route.request().postDataJSON());
    return route.fulfill({ json: response() });
  });
  await page.goto("/route");
  await page.getByLabel("Wyszukaj cel", { exact: true }).fill("Nowa Huta");
  await page
    .getByRole("button", { name: "Muzeum w Nowej Hucie", exact: false })
    .click();
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByRole("link", { name: "Szczegóły trasy", exact: true }),
  ).toBeVisible();
  expect(requests[0].destination).toEqual({ place_id: "node/123" });
  await page.getByRole("button", { name: "Wskaż początek na mapie" }).click();
  await page.locator(".map-canvas").click({ position: { x: 120, y: 180 } });
  await expect(
    page.getByRole("combobox", { name: "Skąd", exact: true }),
  ).toHaveValue("map-origin");
  await page.getByRole("button", { name: "Wskaż cel na mapie" }).click();
  await page.locator(".map-canvas").click({ position: { x: 170, y: 240 } });
  await expect(
    page.getByRole("combobox", { name: "Dokąd", exact: true }),
  ).toHaveValue("map-destination");
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByRole("link", { name: "Szczegóły trasy", exact: true }),
  ).toBeVisible();
  expect(requests[1].origin).toMatchObject({
    lat: expect.any(Number),
    lon: expect.any(Number),
  });
  expect(requests[1].destination).toMatchObject({
    lat: expect.any(Number),
    lon: expect.any(Number),
  });
});

test("opcja kul lub wózka w profilu ustawia ograniczenia planera", async ({
  page,
}) => {
  let planRequest: Record<string, unknown> | null = null;
  await page.route("**/api/v1/routes/plan", (route) => {
    planRequest = route.request().postDataJSON();
    return route.fulfill({ json: response(true) });
  });
  await page.goto("/profile/setup");
  await page.getByRole("button", { name: "Wybierz potrzeby ręcznie" }).click();
  await page.getByLabel("Poruszam się o kulach lub na wózku").check();
  await expect(page.getByLabel("Maksymalna liczba stopni")).toHaveValue("0");
  await expect(page.getByLabel("Maksymalne nachylenie (%)")).toHaveValue("5");
  await page
    .getByRole("button", { name: "Zapisz profil", exact: true })
    .click();
  await page.getByRole("link", { name: "Wyznacz trasę", exact: true }).click();
  await expect(
    page.getByLabel("Poruszam się o kulach lub na wózku"),
  ).toBeChecked();
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect
    .poll(() => planRequest)
    .toMatchObject({
      constraints: {
        max_steps: 0,
        require_step_free_access: true,
        max_slope_percent: 5,
      },
    });
});

test("opis profilu jest interpretowany, zatwierdzany i przekazywany do planera", async ({
  page,
}) => {
  let planRequest: Record<string, unknown> | null = null;
  await page.route("**/api/v1/needs/interpret", (route) => {
    expect(route.request().postDataJSON().description).toBe(
      "Unikam schodów i nieoświetlonych ulic.",
    );
    return route.fulfill({
      json: {
        constraints: {
          max_steps: 0,
          require_step_free_access: true,
          require_lighting: true,
          max_threshold_cm: null,
          max_slope_percent: null,
          min_entrance_width_cm: null,
          max_distance_without_rest_m: null,
          require_accessible_toilet: null,
          allowed_surfaces: null,
        },
        summary: "Bez schodów, z oświetleniem.",
        questions: [],
        requires_confirmation: true,
      },
    });
  });
  await page.route("**/api/v1/routes/plan", (route) => {
    planRequest = route.request().postDataJSON();
    return route.fulfill({ json: response(true) });
  });
  await page.goto("/profile/setup");
  await page
    .getByLabel("Opisz swoje potrzeby")
    .fill("Unikam schodów i nieoświetlonych ulic.");
  await page.getByRole("button", { name: "Dalej", exact: true }).click();
  await expect(
    page.getByLabel("Unikaj nieoświetlonych odcinków"),
  ).toBeChecked();
  await expect(page.getByLabel("Potrzebuję wejścia bez stopni")).toBeChecked();
  await page.getByRole("button", { name: "Zapisz profil" }).click();
  await page.getByRole("link", { name: "Wyznacz trasę", exact: true }).click();
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByRole("heading", { name: "15 min", exact: true }),
  ).toBeVisible();
  expect(planRequest).toMatchObject({
    constraints: {
      max_steps: 0,
      require_step_free_access: true,
      require_lighting: true,
    },
  });
});

test("dwa warianty piesze pokazują niedogodności i przełączają szczegóły", async ({
  page,
}) => {
  await page.route("**/api/v1/routes/plan", (route) => {
    const result = response(true);
    result.routes[0].variant = "constrained";
    const fastest = response().routes[0];
    fastest.id = "fastest-route";
    fastest.variant = "fastest";
    fastest.assessment = {
      status: "does_not_meet_requirements",
      summary: "Najszybsza trasa prowadzi przez schody.",
      reasons: [
        {
          code: "OSM_INCONVENIENCE",
          message: "Schody: 6 stopni.",
          fact_ids: [],
        },
      ],
    };
    result.routes.push(fastest);
    return route.fulfill({ json: result });
  });
  await page.goto("/route");
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(
    page.getByRole("button", { name: /Trasa z uwzględnieniem ograniczeń/ }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByText("Schody: 6 stopni.", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Najszybsza trasa/ }).click();
  await expect(
    page.getByRole("heading", { name: "12 min", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Szczegóły trasy", exact: true })
    .click();
  await expect(page).toHaveURL(/route\/fastest-route\/details/);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Idź do Wawelu.", exact: true }),
  ).toBeVisible();
});
