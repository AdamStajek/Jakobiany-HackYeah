import { test, expect } from "@playwright/test";
import { emptyConstraints } from "../../src/data/types";

test("AI miejsc stosuje frazę i wymagania dopiero po zatwierdzeniu", async ({
  page,
}) => {
  const searches: Record<string, unknown>[] = [];
  await page.route("**/api/v1/places/search", (route) => {
    searches.push(route.request().postDataJSON());
    return route.fulfill({
      json: {
        items: [],
        next_cursor: null,
        total_count: 0,
        warnings: [],
        attribution: [],
      },
    });
  });
  await page.route("**/api/v1/places/interpret", (route) => {
    expect(route.request().postDataJSON().description).toBe(
      "Kawiarnia bez schodów",
    );
    return route.fulfill({
      json: {
        query: "kawiarnia",
        constraints: {
          ...emptyConstraints,
          max_steps: 0,
          require_step_free_access: true,
        },
        summary: "Kawiarnia bez schodów",
        questions: [],
      },
    });
  });
  await page.goto("/search");
  await page.locator(".ai-search > summary").click();
  await page.getByLabel("Opisz, czego szukasz").fill("Kawiarnia bez schodów");
  await page.getByRole("button", { name: "Przygotuj wyszukiwanie" }).click();
  await expect(page.getByText("Fraza: kawiarnia")).toBeVisible();
  expect(searches.some((body) => body.query === "kawiarnia")).toBe(false);
  await page.getByRole("button", { name: "Zastosuj wyszukiwanie" }).click();
  await expect(page).toHaveURL(/q=kawiarnia/);
  await expect
    .poll(() => searches.at(-1))
    .toMatchObject({
      query: "kawiarnia",
      constraints: { max_steps: 0, require_step_free_access: true },
    });
});

test("AI trasy wyszukuje prawdziwe punkty i wymaga ich wyboru", async ({
  page,
}) => {
  await page.route("**/api/v1/routes/interpret", (route) =>
    route.fulfill({
      json: {
        origin_query: "Rynek Główny",
        destination_query: "Wawel",
        constraints: {
          ...emptyConstraints,
          max_steps: 0,
          require_step_free_access: true,
        },
        summary: "Trasa bez schodów",
        questions: [],
      },
    }),
  );
  await page.route("**/api/v1/routes/points?*", (route) => {
    const name = new URL(route.request().url()).searchParams.get("query")!;
    return route.fulfill({
      json: {
        items: [
          {
            id: name === "Wawel" ? "osm-wawel" : "osm-rynek",
            name,
            address: null,
            location: { lat: 50.06, lon: 19.94 },
          },
        ],
        next_cursor: null,
      },
    });
  });
  let planBody: Record<string, unknown> | null = null;
  await page.route("**/api/v1/routes/plan", (route) => {
    planBody = route.request().postDataJSON();
    return route.fulfill({
      json: { routes: [], warnings: [], attribution: [] },
    });
  });
  await page.goto("/route");
  await page.locator(".ai-search > summary").click();
  await page
    .getByLabel("Opisz, czego szukasz")
    .fill("Z Rynku Głównego na Wawel bez schodów");
  await page.getByRole("button", { name: "Przygotuj wyszukiwanie" }).click();
  await page.getByRole("button", { name: "Zastosuj wyszukiwanie" }).click();
  await expect(page.getByLabel("Skąd", { exact: true })).toHaveValue(
    "Rynek Główny",
  );
  await expect(page.getByLabel("Dokąd", { exact: true })).toHaveValue("Wawel");
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  expect(planBody).toBeNull();
  await expect(
    page.getByText(
      "Wybierz początek i cel trasy z wyników wyszukiwania lub na mapie.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Rynek Główny", exact: true }).click();
  await page.getByRole("button", { name: "Wawel", exact: true }).click();
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect
    .poll(() => planBody)
    .toMatchObject({
      origin: { place_id: "osm-rynek" },
      destination: { place_id: "osm-wawel" },
      constraints: { max_steps: 0, require_step_free_access: true },
    });
});
