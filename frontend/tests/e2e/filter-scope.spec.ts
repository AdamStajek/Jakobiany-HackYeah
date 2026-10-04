import { test, expect } from "@playwright/test";
import { emptyConstraints } from "../../src/data/types";

test("filtry są niezależne, a profil stosuje się tylko po kliknięciu", async ({
  page,
}) => {
  const searches: Record<string, unknown>[] = [];
  const profile = {
    id: "profile-1",
    name: "Mój profil potrzeb",
    description: "Bez schodów",
    constraints: {
      ...emptyConstraints,
      max_steps: 0,
      require_step_free_access: true,
    },
  };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/session")) {
      return route.fulfill({
        json: {
          user: { id: "user-1", display_name: "Test", roles: [] },
          csrf_token: "test",
        },
      });
    }
    if (path.endsWith("/profiles")) {
      if (route.request().method() === "POST") {
        return route.fulfill({
          json: { ...profile, ...route.request().postDataJSON() },
        });
      }
      return route.fulfill({ json: { items: [profile], next_cursor: null } });
    }
    if (path.endsWith("/profiles/profile-1")) {
      return route.fulfill({
        json: { ...profile, ...route.request().postDataJSON() },
      });
    }
    if (path.endsWith("/bookmarks")) return route.fulfill({ json: [] });
    if (path.endsWith("/places/search"))
      searches.push(route.request().postDataJSON());
    return route.fulfill({
      json: {
        items: [],
        next_cursor: null,
        total_count: 0,
        points: 0,
        warnings: [],
        attribution: [],
      },
    });
  });
  await page.goto("/route");
  const routeFilter = page.getByLabel("Unikaj schodów");
  await expect(
    page.getByRole("button", { name: "Ustaw preferencje z profilu" }),
  ).toBeEnabled();
  await expect(routeFilter).not.toBeChecked();
  await routeFilter.check();
  await page.locator('a[href="/search"]:visible').first().click();
  await expect
    .poll(() => searches.at(-1))
    .toMatchObject({ constraints: emptyConstraints });
  if (
    await page.getByRole("button", { name: "Filtry", exact: true }).isVisible()
  ) {
    await page.getByRole("button", { name: "Filtry", exact: true }).click();
  }
  await page.getByLabel("Toaleta dostępna", { exact: true }).check();
  await page.locator('a[href="/route"]:visible').first().click();
  await expect(routeFilter).toBeChecked();
  await routeFilter.uncheck();
  await page
    .getByRole("button", { name: "Ustaw preferencje z profilu" })
    .click();
  await expect(routeFilter).toBeChecked();
  await page.locator('a[href="/search"]:visible').first().click();
  await expect
    .poll(() => searches.at(-1))
    .toMatchObject({
      constraints: {
        require_step_free_access: null,
        require_accessible_toilet: true,
      },
    });
  await page
    .getByRole("button", { name: "Ustaw preferencje z profilu" })
    .click();
  await expect
    .poll(() => searches.at(-1))
    .toMatchObject({ constraints: profile.constraints });
  await page.goto("/profile/setup");
  await page.getByRole("button", { name: "Wybierz potrzeby ręcznie" }).click();
  await expect(page.getByLabel("Maksymalna liczba stopni")).toHaveValue("0");
  await page.getByLabel("Maksymalna liczba stopni").fill("3");
  await page
    .getByRole("button", { name: "Zapisz profil", exact: true })
    .click();
  await page.getByRole("link", { name: "Znajdź miejsce", exact: true }).click();
  await expect
    .poll(() => searches.at(-1))
    .toMatchObject({ constraints: emptyConstraints });
  await page
    .getByRole("button", { name: "Ustaw preferencje z profilu" })
    .click();
  await expect
    .poll(() => searches.at(-1))
    .toMatchObject({ constraints: { max_steps: 3 } });
});
