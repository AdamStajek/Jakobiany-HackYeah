import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";
import type { MissionActivity } from "../../src/data/api";

const publicPaths = [
  "/",
  "/search",
  "/place/node%2F1",
  "/route",
  "/profile/setup",
  "/profile",
  "/report",
  "/report/problem?place=node%2F1",
  "/report/confirm?place=node%2F1",
  "/report/verify?place=node%2F1",
  "/missions",
  "/about",
  "/public-data",
  "/privacy",
  "/data-quality",
  "/login",
  "/register",
  "/review",
  "/settings",
  "/places/new",
  "/not-found",
];

async function scan(page: Page) {
  await page.evaluate(async () => {
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
    await Promise.all(
      document
        .getAnimations()
        .filter(
          (animation) =>
            animation.effect?.getComputedTiming().iterations !== Infinity,
        )
        .map((animation) => animation.finished.catch(() => {})),
    );
  });
  const result = await new AxeBuilder({ page })
    .withTags([
      "wcag2a",
      "wcag2aa",
      "wcag21a",
      "wcag21aa",
      "wcag22aa",
      "best-practice",
    ])
    .analyze();
  expect(
    result.violations.map(({ id, nodes }) => ({
      id,
      nodes: nodes.map(({ target, failureSummary }) => ({
        target,
        failureSummary,
      })),
    })),
    page.url(),
  ).toEqual([]);
}

async function fits(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    page.url(),
  ).toBe(true);
}

async function visit(page: Page, path: string) {
  await page.goto(path);
  await expect(page.locator("h1")).toBeVisible();
  // Settle the debounced searches before scanning the resulting content.
  await page.waitForTimeout(350);
}

async function register(page: Page) {
  await visit(page, "/register");
  await page.getByLabel("Imię", { exact: true }).fill("Anna");
  await page
    .getByLabel("E-mail", { exact: true })
    .fill(`a11y-${test.info().project.name}-${Date.now()}@example.com`);
  await page
    .getByLabel("Hasło", { exact: true })
    .fill("browser-accessibility-password");
  await page.getByRole("button", { name: "Utwórz konto", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Cześć, Anna!" }),
  ).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
});

test("WCAG A/AA: strony publiczne, nazwy i tytuły", async ({ page }) => {
  for (const path of publicPaths) {
    await visit(page, path);
    await fits(page);
    await expect(page).toHaveTitle(
      `${(await page.locator("h1").innerText()).replace(/\s+/g, " ").trim()} · Swoją Drogą`,
    );
    await scan(page);
  }
});

test("powiększenie tekstu do 200% i odstępy WCAG nie ucinają treści", async ({
  page,
}) => {
  for (const path of [
    "/",
    "/search",
    "/place/node%2F1",
    "/route",
    "/profile/setup",
    "/profile",
    "/missions",
    "/report",
    "/login",
    "/register",
    "/public-data",
  ]) {
    await visit(page, path);
    if (path === "/profile/setup")
      await page
        .getByRole("button", { name: "Wybierz potrzeby ręcznie" })
        .click();
    await page.addStyleTag({
      content: `
      html { font-size: 32px !important; }
      * { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; }
      p { margin-bottom: 2em !important; }
    `,
    });
    await fits(page);
    const clipped = await page.evaluate(() =>
      Array.from(document.querySelectorAll<HTMLElement>("body *"))
        .filter((node) => {
          if (
            !node.textContent?.trim() ||
            node.closest(".leaflet-container") ||
            node.matches(".sr-only, input, textarea, select, svg, svg *")
          )
            return false;
          const style = getComputedStyle(node);
          return (
            node.clientHeight > 0 &&
            ["hidden", "clip"].includes(style.overflowY) &&
            node.scrollHeight > node.clientHeight + 2
          );
        })
        .map((node) => node.className),
    );
    expect(clipped, path).toEqual([]);
  }
});

test("klawiatura: skip link, nawigacja SPA, zakładki i menu", async ({
  page,
}) => {
  await visit(page, "/search");
  await page
    .getByRole("link", { name: "Przejdź do treści", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#content")).toBeFocused();
  await page
    .getByRole("heading", { name: "Muzeum integracyjne" })
    .getByRole("link")
    .focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("h1")).toBeFocused();
  await page.getByRole("tab", { name: "Dostępność", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "Informacje", exact: true }),
  ).toBeFocused();
  await expect(
    page.getByRole("tab", { name: "Informacje", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("End");
  await expect(
    page.getByRole("tab", { name: "Źródła danych", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Home");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("tabpanel")).toBeFocused();
  expect(
    await page
      .getByRole("tab")
      .evaluateAll(
        (nodes) =>
          nodes.filter((node) => (node as HTMLElement).tabIndex === 0).length,
      ),
  ).toBe(1);
  const menu = page.getByRole("button", { name: "Menu", exact: true });
  if (await menu.isVisible()) {
    await menu.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#main-navigation a").first()).toBeFocused();
    await scan(page);
    await page.keyboard.press("Escape");
    await expect(menu).toBeFocused();
    await expect(menu).toHaveAttribute("aria-expanded", "false");
  }
});

test("mapa: punkt klawiaturą, przyciski bez przeciągania i powrót fokusu", async ({
  page,
}) => {
  const plans: Record<string, unknown>[] = [];
  await page.route("**/api/v1/routes/plan", (route) => {
    plans.push(route.request().postDataJSON());
    return route.fulfill({
      json: {
        routes: [],
        warnings: ["Test: nie znaleziono trasy."],
        attribution: [],
      },
    });
  });
  await visit(page, "/route");
  await page.getByRole("button", { name: "Wskaż początek na mapie" }).click();
  await expect(page.locator(".map-canvas")).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "Wskaż początek na mapie" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Wskaż cel na mapie" }).click();
  await page.getByRole("button", { name: "Przesuń mapę na południe" }).click();
  await page.getByRole("button", { name: "Wybierz środek mapy" }).click();
  await expect(
    page.getByRole("button", { name: "Wskaż cel na mapie" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Pokaż trasę", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Nie znaleziono trasy");
  expect(plans[0]).toMatchObject({
    origin: { lat: expect.any(Number), lon: expect.any(Number) },
    destination: { lat: expect.any(Number), lon: expect.any(Number) },
  });
  expect(plans[0].origin).not.toEqual(plans[0].destination);
  await page.getByRole("button", { name: "Wskaż cel na mapie" }).click();
  await expect(page.locator(".map-canvas")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Wskaż cel na mapie" }),
  ).toBeFocused();
  await scan(page);

  await visit(page, "/search");
  await page
    .getByRole("button", { name: "Pokaż na mapie", exact: true })
    .first()
    .click();
  await expect(page.locator(".map-canvas")).toBeFocused();
  await page.locator(".place-marker").first().press("Enter");
  await expect(
    page.getByRole("button", { name: "Zamknij szczegóły znacznika" }),
  ).toBeFocused();
  await scan(page);
  await page.keyboard.press("Escape");
  await expect(page.locator(".place-marker").first()).toBeFocused();
});

test("zalogowany użytkownik: formularze, błędy, kroki i odpowiedź misji", async ({
  page,
}) => {
  await register(page);
  for (const path of [
    "/profile",
    "/report/problem?place=node%2F1",
    "/report/confirm?place=node%2F1",
    "/report/verify?place=node%2F1",
    "/missions",
  ]) {
    await visit(page, path);
    await scan(page);
    await fits(page);
  }
  await visit(page, "/report/problem");
  const placeInput = page.getByLabel("Miejsce do zgłoszenia", { exact: true });
  await placeInput.fill("Muzeum integracyjne");
  await page
    .getByRole("button", { name: "Muzeum integracyjne", exact: true })
    .click();
  await expect(placeInput).toBeFocused();
  await expect(page.locator(".search-results")).toHaveCount(0);
  await visit(page, "/report/problem?place=node%2F1");
  await page
    .getByRole("button", { name: "Wyślij zgłoszenie", exact: true })
    .click();
  await expect(page.getByLabel("Opisz problem", { exact: true })).toBeFocused();
  await expect(
    page.getByLabel("Opisz problem", { exact: true }),
  ).toHaveAttribute("aria-invalid", "true");
  await scan(page);
  await page
    .getByLabel("Opisz problem", { exact: true })
    .fill("Podjazd zamknięty z powodu remontu.");
  await page
    .getByRole("button", { name: "Wyślij zgłoszenie", exact: true })
    .click();
  await expect(page.locator("h1")).toHaveText("Dziękujemy za pomoc!");
  await scan(page);
  await visit(page, "/profile/setup");
  await page.getByRole("button", { name: "Wybierz potrzeby ręcznie" }).click();
  await expect(
    page.getByRole("heading", { name: "Wybierz i potwierdź swoje potrzeby" }),
  ).toBeFocused();
  await scan(page);
  await page
    .getByRole("button", { name: "Zapisz profil", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Twoje potrzeby są zapisane" }),
  ).toBeFocused();
  await scan(page);
  await visit(page, "/missions");
  await page.locator(".mission-card").first().click();
  await page
    .getByRole("button", { name: "Rozpocznij misję", exact: true })
    .click();
  await expect(
    page.getByLabel("Zdjęcie (wymagane)", { exact: true }),
  ).toBeVisible();
  await scan(page);

  await page
    .locator('input[type="file"]')
    .setInputFiles("tests/fixtures/evidence.png");
  const activity = (await (
    await page.request.get("/api/v1/missions/progress")
  ).json()) as MissionActivity;
  const pending = {
    ...activity.items[0],
    status: "pending" as const,
    ai_status: "pending",
    answer: "Wejście sprawdzono: brak stopni.",
    awarded_points: 0,
    report_id: "a11y-report",
  };
  // Test the pending UI without calling an external photo verification model.
  await page.route("**/api/v1/photos", (route) =>
    route.fulfill({ json: { id: "a11y-photo", status: "ready" } }),
  );
  await page.route("**/api/v1/missions/*/submit", (route) =>
    route.fulfill({ json: pending }),
  );
  await page.route("**/api/v1/missions/progress", (route) =>
    route.fulfill({ json: { items: [pending], points: 0 } }),
  );
  await page
    .getByRole("button", {
      name: "Wyślij odpowiedź do weryfikacji",
      exact: true,
    })
    .click();
  await expect(
    page.getByText("Przetwarzanie · 0 naliczonych punktów"),
  ).toBeVisible();
  await scan(page);
});

test("języki, kontrast, trwały komunikat i widoczność fokusu", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await visit(page, "/about");
  await page
    .getByRole("button", { name: "Switch to English", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("h1")).toHaveText("The best route is your own");
  await expect(page.locator("h1")).toHaveAttribute("lang", "en");
  await expect(page.locator(".prose p").first()).toHaveAttribute("lang", "pl");
  await scan(page);
  await page
    .getByRole("button", { name: "Switch to Polish", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("lang", "pl");
  await visit(page, "/settings");
  await page.getByLabel("Zwiększony kontrast").check();
  await page.getByLabel("Większy tekst").check();
  await fits(page);
  await scan(page);
  await page.getByLabel("Większy tekst").uncheck();
  await page.getByLabel("Zwiększony kontrast").uncheck();
  await page.route("**/api/v1/auth/session", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { message: "Test: sesja niedostępna." } },
    }),
  );
  await visit(page, "/login");
  await expect(page.locator(".toast")).toContainText(
    "Test: sesja niedostępna.",
  );
  await page.waitForTimeout(6000);
  await expect(page.locator(".toast")).toBeVisible();
  await scan(page);
  await page.getByRole("button", { name: "Zamknij komunikat" }).click();
  await expect(page.locator(".toast")).toHaveCount(0);
  await page.unroute("**/api/v1/auth/session");
  for (const path of ["/register", "/route", "/place/node%2F1"]) {
    await visit(page, path);
    const seen = new Set<string>();
    for (let index = 0; index < 70; index++) {
      await page.keyboard.press("Tab");
      const focus = await page.evaluate(() => {
        const node = document.activeElement as HTMLElement;
        if (!node || node === document.body) return null;
        const rect = node.getBoundingClientRect();
        const left = Math.max(0, rect.left),
          right = Math.min(innerWidth, rect.right);
        const top = Math.max(0, rect.top),
          bottom = Math.min(innerHeight, rect.bottom);
        const visible =
          right > left &&
          bottom > top &&
          [0.1, 0.5, 0.9].some((y) =>
            [0.1, 0.5, 0.9].some((x) => {
              const hit = document.elementFromPoint(
                left + (right - left) * x,
                top + (bottom - top) * y,
              );
              return hit === node || (hit !== null && node.contains(hit));
            }),
          );
        return { key: node.outerHTML.slice(0, 250), visible };
      });
      if (!focus) continue;
      expect(focus.visible, `${path}: ${focus.key}`).toBe(true);
      if (seen.has(focus.key)) break;
      seen.add(focus.key);
    }
  }
  expect(errors).toEqual([]);
});

test("komunikacja i parkingi: alternatywa tekstowa i wstrzymanie aktualizacji", async ({
  page,
}) => {
  await page.clock.install();
  let vehicleRequests = 0;
  await page.route("**/api/v1/routes/mobility?*", (route) => {
    const kind = new URL(route.request().url()).searchParams.get("kind");
    if (kind === "vehicles") vehicleRequests++;
    return route.fulfill({
      json: {
        items: [
          {
            id: `test-${kind}`,
            name:
              kind === "stops"
                ? "Przystanek Muzeum"
                : kind === "vehicles"
                  ? "Autobus 100"
                  : "Parking Muzeum",
            kind:
              kind === "stops"
                ? "stop"
                : kind === "vehicles"
                  ? "vehicle"
                  : "parking",
            location: { lat: 50.061, lon: 19.936 },
            line: kind === "vehicles" ? "100" : null,
            updated_at: "2026-10-04T08:00:00Z",
          },
        ],
        warnings: [],
        attribution: [],
      },
    });
  });
  await visit(page, "/route");
  await page
    .getByRole("button", { name: "Komunikacja miejska", exact: true })
    .click();
  await expect.poll(() => vehicleRequests).toBe(1);
  await page.locator(".map-data summary").click();
  await expect(page.locator(".map-data")).toContainText("Przystanek Muzeum");
  await expect(page.locator(".map-data")).toContainText("Autobus 100");
  await scan(page);
  await fits(page);
  await page
    .getByLabel("Automatycznie aktualizuj pozycje pojazdów (co 30 s)")
    .uncheck();
  await page.clock.fastForward(31000);
  expect(vehicleRequests).toBe(1);
  await expect(page.locator(".map-data")).toContainText("Autobus 100");
  await page
    .getByLabel("Automatycznie aktualizuj pozycje pojazdów (co 30 s)")
    .check();
  await expect.poll(() => vehicleRequests).toBe(2);
  await page.getByRole("button", { name: "Samochód", exact: true }).click();
  await page
    .getByLabel(
      "Prowadź do miejsca parkingowego dla osób z niepełnosprawnościami",
    )
    .check();
  await expect(page.locator(".map-data")).toContainText("Parking Muzeum");
  await scan(page);
  await fits(page);
});

test("wynik AI i instrukcje nawigacji mają dostępny fokus i kontrast", async ({
  page,
}) => {
  await page.route("**/api/v1/places/interpret", (route) =>
    route.fulfill({
      json: {
        query: "muzeum",
        constraints: {
          max_steps: 0,
          max_threshold_cm: null,
          max_slope_percent: null,
          min_entrance_width_cm: null,
          max_distance_without_rest_m: null,
          require_step_free_access: true,
          require_accessible_toilet: null,
          allowed_surfaces: null,
        },
        summary: "Muzeum bez schodów",
        questions: [],
      },
    }),
  );
  await visit(page, "/search");
  await page.locator(".ai-search > summary").click();
  await page.getByLabel("Opisz, czego szukasz").fill("Muzeum bez schodów");
  await page
    .locator(".ai-search")
    .getByRole("button", { name: "Szukaj", exact: true })
    .click();
  await expect(
    page.getByText("Wyszukiwanie zostało zastosowane.", { exact: false }),
  ).toBeVisible();
  await scan(page);
  const assessment = {
    status: "meets_requirements",
    summary: "Spełnia wymagania.",
    reasons: [],
  };
  const geometry = {
    type: "LineString",
    coordinates: [
      [19.936, 50.061],
      [19.937, 50.062],
    ],
  };
  await page.route("**/api/v1/routes/plan", (route) =>
    route.fulfill({
      json: {
        routes: [
          {
            id: "a11y-route",
            mode: "walk",
            variant: "constrained",
            distance_m: 400,
            estimated_duration_s: 300,
            assessment,
            geometry,
            computed_at: "2026-10-04T08:00:00Z",
            facts: [],
            segments: ["Idź prosto.", "Skręć w prawo."].map(
              (instruction, index) => ({
                id: `a11y-${index}`,
                instruction,
                mode: "walk",
                distance_m: 200,
                assessment,
                geometry,
                facts: [],
                barriers: [],
                rest_points: [],
                temporary_difficulties: [],
              }),
            ),
          },
        ],
        warnings: [],
        attribution: [],
      },
    }),
  );
  await visit(page, "/route");
  await page.getByRole("button", { name: "Wskaż początek na mapie" }).click();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Wskaż cel na mapie" }).click();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Pokaż trasę", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "Szczegóły trasy", exact: true }),
  ).toBeVisible();
  await scan(page);
  await fits(page);
  await page
    .getByRole("link", { name: "Szczegóły trasy", exact: true })
    .click();
  await scan(page);
  await fits(page);
  await page
    .getByRole("link", { name: "Podgląd nawigacji", exact: true })
    .click();
  await scan(page);
  await fits(page);
  await page
    .getByRole("button", { name: "Następny krok", exact: true })
    .click();
  await expect(page.locator("h1")).toHaveText("Skręć w prawo.");
  await expect(page.locator("h1")).toHaveAttribute("aria-live", "polite");
  await page.getByRole("button", { name: "Powiększ instrukcję" }).click();
  await scan(page);
  await fits(page);
});

test("moderator: komentarz, decyzja i fokus po usunięciu karty", async ({
  page,
  browser,
  baseURL,
}) => {
  await register(page);
  const description = `Miejsce dostępności ${test.info().project.name} ${Date.now()}`;
  await visit(page, "/places/new");
  await page.getByLabel("Nazwa miejsca", { exact: true }).fill(description);
  await page.getByLabel("Kategoria", { exact: true }).selectOption("Muzea");
  await page.getByRole("button", { name: "Wyślij do weryfikacji" }).click();
  await expect(page.getByLabel("Adres", { exact: true })).toBeFocused();
  await expect(page.getByLabel("Adres", { exact: true })).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await scan(page);
  await page
    .getByLabel("Adres", { exact: true })
    .fill("Kraków, Rynek Główny 1");
  await page.getByRole("button", { name: "Wskaż miejsce na mapie" }).click();
  await expect(page.locator(".map-canvas")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Szerokość geograficzna")).toBeFocused();
  await page.getByRole("button", { name: "Wyślij do weryfikacji" }).click();
  await expect(page.locator("#new-place-success")).toBeFocused();
  await scan(page);
  const context = await browser.newContext({
    baseURL,
    viewport: page.viewportSize() || undefined,
  });
  const moderator = await context.newPage();
  await moderator.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  try {
    await visit(moderator, "/login");
    await moderator
      .getByLabel("E-mail", { exact: true })
      .fill("moderator@example.com");
    await moderator
      .getByLabel("Hasło", { exact: true })
      .fill("moderator-test-password");
    await moderator
      .getByRole("button", { name: "Zaloguj się", exact: true })
      .click();
    await expect(
      moderator.getByRole("heading", { name: "Cześć, Moderator!" }),
    ).toBeVisible();
    await visit(moderator, "/review");
    const card = moderator
      .locator(".review-card")
      .filter({ hasText: description });
    await expect(card).toBeVisible();
    await scan(moderator);
    await fits(moderator);
    await card
      .getByLabel("Komentarz administratora")
      .fill("Sprawdzono opis zgłoszenia.");
    const mapButton = card.getByRole("button", {
      name: "Zmień położenie na mapie",
    });
    await mapButton.click();
    await expect(card.locator(".map-canvas")).toBeFocused();
    await moderator.keyboard.press("Escape");
    await expect(mapButton).toBeFocused();
    await mapButton.click();
    await moderator.keyboard.press("Enter");
    await expect(mapButton).toBeFocused();
    await card
      .getByRole("button", { name: "Zatwierdź miejsce", exact: true })
      .click();
    await expect(card).toHaveCount(0);
    await expect(moderator.locator("h1")).toBeFocused();
    await expect(moderator.locator(".toast")).toBeVisible();
    await scan(moderator);
  } finally {
    await context.close();
  }
});

test("orientacja pozioma i kolory systemowe zachowują obsługę klawiaturą", async ({
  page,
}) => {
  await page.setViewportSize({ width: 844, height: 390 });
  await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" });
  await visit(page, "/route");
  await fits(page);
  const choose = page.getByRole("button", { name: "Wskaż początek na mapie" });
  await choose.focus();
  await page.keyboard.press("Enter");
  const map = page.locator(".map-canvas");
  await expect(map).toBeFocused();
  expect(
    await map.evaluate((node) => getComputedStyle(node).outlineStyle),
  ).toBe("solid");
  await page.keyboard.press("Escape");
  await expect(choose).toBeFocused();
  await scan(page);
});

test("podpowiedzi punktów: wybór i Escape przywracają fokus", async ({
  page,
}) => {
  await page.route("**/api/v1/routes/points?*", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: "test-point",
            name: "Testowy punkt",
            address: "Kraków",
            location: { lat: 50.061, lon: 19.936 },
          },
        ],
        next_cursor: null,
      },
    }),
  );
  await visit(page, "/route");
  const input = page.getByLabel("Skąd", { exact: true });
  await input.fill("Testowy");
  const suggestion = page.getByRole("button", { name: "Testowy punkt Kraków" });
  await suggestion.focus();
  await page.keyboard.press("Escape");
  await expect(input).toBeFocused();
  await expect(suggestion).toHaveCount(0);
  await input.fill("Testowy punkt");
  await suggestion.click();
  await expect(input).toBeFocused();
  await expect(input).toHaveValue("Testowy punkt");
  await scan(page);
});
