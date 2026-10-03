import { test, expect } from "@playwright/test";
test("wyszukiwanie, szczegóły i zapis miejsca", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page
    .getByRole("textbox", { name: "Wyszukaj miejsce lub kategorię" })
    .fill("kawiarnia");
  await page.getByRole("button", { name: "Szukaj", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Znajdź swoje miejsce" }),
  ).toBeVisible();
  await page
    .getByRole("heading", { name: "Kawiarnia Pod Wawelem" })
    .getByRole("link")
    .click();
  await expect(
    page.getByRole("heading", { name: "Kawiarnia Pod Wawelem", level: 1 }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Zapisz", exact: true }).click();
  await page
    .getByRole("link", { name: "Zapisane miejsca", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "Kawiarnia Pod Wawelem" }),
  ).toBeVisible();
  await page.reload(); // odświeżenie celowo czyści dane demo
  await expect(
    page.getByText("Zapisuj miejsca przyciskiem", { exact: false }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
test("profil potrzeb, filtrowanie i zgłoszenie", async ({ page, isMobile }) => {
  await page.goto("/profile/setup");
  await page.getByRole("button", { name: "Dalej", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Toaleta dostępna", exact: true })
    .selectOption("true");
  await page.getByRole("button", { name: "Zapisz profil" }).click();
  await page.getByRole("link", { name: "Znajdź miejsce", exact: true }).click();
  await expect(
    page.getByText("Brakuje pewnych informacji").first(),
  ).toBeVisible();
  await page
    .getByRole("heading", { name: "Café Lisboa" })
    .getByRole("link")
    .click();
  await expect(
    page.getByText("Źródła podają różne informacje", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Zgłoś problem" }).click();
  await page
    .getByLabel("Opisz problem")
    .fill("Podjazd jest zamknięty z powodu remontu.");
  await page
    .getByRole("button", { name: "Zapisz przykładowe zgłoszenie" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Dziękujemy za pomoc!" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Moje zgłoszenia" }).click();
  await expect(
    page.getByText("Podjazd jest zamknięty z powodu remontu."),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
  if (isMobile)
    await expect(
      page.getByRole("navigation", { name: "Nawigacja mobilna" }),
    ).toBeVisible();
});
test("trasa, tekstowe kroki i symulacja nawigacji", async ({ page }) => {
  await page.goto("/route?to=pod-wawelem");
  await page.getByRole("button", { name: "Pokaż trasę" }).click();
  await expect(page.getByText("Trasa niepewna", { exact: true })).toBeVisible();
  await page
    .getByRole("link", { name: "Szczegóły trasy", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Planty", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Podgląd nawigacji", exact: true })
    .click();
  await page.getByRole("button", { name: "Następny krok" }).click();
  await expect(page.getByText("Podgląd kroku 2 z 3")).toBeVisible();
});
test("misja nie nalicza punktów przed weryfikacją", async ({ page }) => {
  await page.goto("/missions/toaleta");
  await page
    .getByRole("button", { name: "Rozpocznij przykładową misję" })
    .click();
  await page
    .getByLabel("Co udało Ci się sprawdzić?")
    .fill("Nie udało się potwierdzić szerokości wejścia.");
  await page
    .getByRole("button", { name: "Zapisz odpowiedź do weryfikacji" })
    .click();
  await expect(
    page.getByText("Oczekuje na weryfikację · 0 naliczonych punktów"),
  ).toBeVisible();
});
test("wszystkie ekrany mieszczą się w oknie i nie wysyłają API", async ({
  page,
  isMobile,
}) => {
  const api: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/")) api.push(r.url());
  });
  for (const path of [
    "/",
    "/search",
    "/map",
    "/place/pod-wawelem",
    "/route",
    "/profile/setup",
    "/profile",
    "/report",
    "/report/confirm",
    "/missions",
    "/about",
    "/login",
    "/nie-ma",
  ]) {
    await page.goto(path);
    await expect(page.locator("h1")).toBeVisible();
    if (path === "/")
      await page.screenshot({
        path: `/tmp/swoja-ui-${isMobile ? "mobile" : "desktop"}.png`,
        fullPage: true,
      });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      path,
    ).toBe(true);
  }
  expect(api).toEqual([]);
});
