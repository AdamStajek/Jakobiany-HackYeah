import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.beforeEach(async ({ page }) => {
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
});

test("układy ekranów i równa siatka kategorii", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  for (const path of [
    "/",
    "/search",
    "/route",
    "/report",
    "/profile",
    "/profile/setup",
    "/missions",
    "/login",
    "/register",
    "/places/new",
    "/place/node%2F1",
  ]) {
    await page.goto(path);
    await expect(page.locator("h1")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      path,
    ).toBe(true);
    if (path === "/") {
      const cards = await page.locator(".category").evaluateAll((nodes) =>
        nodes.map((node) => ({
          width: node.getBoundingClientRect().width,
          height: node.getBoundingClientRect().height,
        })),
      );
      expect(
        Math.max(...cards.map((c) => c.width)) -
          Math.min(...cards.map((c) => c.width)),
      ).toBeLessThan(2);
      expect(
        Math.max(...cards.map((c) => c.height)) -
          Math.min(...cards.map((c) => c.height)),
      ).toBeLessThan(2);
    }
    if (path === "/report") {
      for (const heading of await page.locator(".report-options h2").all()) {
        expect((await heading.boundingBox())!.width).toBeGreaterThan(150);
      }
    }
    await page.screenshot({
      path: testInfo.outputPath(`${path.replaceAll("/", "-") || "home"}.png`),
      fullPage: true,
    });
  }
  expect(errors).toEqual([]);
});

test("menu, filtry, mapa i opcjonalne wyszukiwanie AI", async ({ page }) => {
  await page.goto("/search");
  await expect(page.locator(".place-card")).toHaveCount(1);
  await expect(page.locator(".place-card .status")).toBeVisible();
  await expect(page.locator(".results-heading")).toContainText("1 wynik");
  await expect(page.locator(".results-pagination")).toHaveCount(0);
  await expect(page.getByLabel("Opisz, czego szukasz")).toBeHidden();
  await page.locator(".ai-search > summary").click();
  await expect(page.getByLabel("Opisz, czego szukasz")).toBeVisible();
  await page.locator(".ai-search > summary").click();
  const menu = page.getByRole("button", { name: "Menu", exact: true });
  if (await menu.isVisible()) {
    expect(await menu.evaluate((node) => getComputedStyle(node).color)).toBe(
      "rgb(6, 47, 45)",
    );
    await menu.click();
    await expect(menu).toHaveAttribute("aria-expanded", "true");
    await page.keyboard.press("Escape");
    await expect(menu).toHaveAttribute("aria-expanded", "false");
  }
  const filters = page.getByRole("button", { name: "Filtry", exact: true });
  if (await filters.isVisible()) {
    await expect(page.locator("#search-filters")).toBeHidden();
    await filters.click();
    await expect(page.locator("#search-filters")).toBeVisible();
    await filters.click();
    await expect(page.locator("#search-filters")).toBeHidden();
    await page.getByRole("button", { name: "Mapa", exact: true }).click();
  }
  await expect(page.locator(".place-marker")).toBeVisible();
  await page.locator(".place-marker").click();
  await expect(page.locator(".map-popup")).toContainText("Muzeum integracyjne");
});

test("nowe miejsce: powrót po logowaniu i wskazanie mapą", async ({
  page,
}, testInfo) => {
  await page.goto("/places/new");
  await page
    .getByRole("link", { name: "Zaloguj się, aby zgłosić miejsce" })
    .click();
  await page
    .getByRole("link", { name: "Nie masz konta? Zarejestruj się" })
    .click();
  await page.getByLabel("Imię", { exact: true }).fill("Anna");
  await page
    .getByLabel("E-mail", { exact: true })
    .fill(`ux-${testInfo.project.name}-${Date.now()}@example.com`);
  await page.getByLabel("Hasło", { exact: true }).fill("browser-test-password");
  await page.getByRole("button", { name: "Utwórz konto", exact: true }).click();
  await expect(page).toHaveURL(/\/places\/new$/);
  await page
    .getByLabel("Nazwa miejsca", { exact: true })
    .fill("Biblioteka testowa");
  await page.getByLabel("Kategoria", { exact: true }).fill("Biblioteki");
  await page
    .getByLabel("Adres", { exact: true })
    .fill("Kraków, Rynek Główny 1");
  await page
    .getByRole("button", { name: "Wskaż miejsce na mapie", exact: true })
    .click();
  await expect(page.locator(".map-canvas")).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await page.getByRole("button", { name: "Wybierz środek mapy" }).click();
  await expect(page.getByLabel("Szerokość geograficzna")).toBeFocused();
  await expect(page.getByLabel("Szerokość geograficzna")).not.toHaveValue("");
  await expect(page.getByLabel("Długość geograficzna")).not.toHaveValue("");
  await expect(page.locator(".new-place-map")).toHaveCount(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("new-place-form.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Wyślij do weryfikacji" }).click();
  await expect(
    page.locator(".new-place-page").getByRole("status"),
  ).toContainText("Zgłoszenie zapisane");
  await expect(
    page.getByRole("heading", { name: "Biblioteka testowa" }),
  ).toBeVisible();
});
