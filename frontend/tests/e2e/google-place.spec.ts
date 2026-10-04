import { test, expect } from "@playwright/test";

for (const fail of [false, true]) {
  test(`Google card loads below the address by default, ${fail ? "handles failure" : "uses selected ID"}`, async ({
    page,
  }) => {
    await page.route("**/api/v1/auth/session", (route) =>
      route.fulfill({ status: 401, json: { error: { code: "UNAUTHORIZED" } } }),
    );
    await page.route("**/api/v1/places/**", (route) =>
      route.fulfill({
        json: {
          id: "node/1",
          name: "Muzeum testowe",
          category: "Muzeum",
          address: "Kraków",
          location: { lat: 50.06, lon: 19.94 },
          distance_m: null,
          facts: [],
          barriers: [],
          attribution: [],
          updated_at: "2026-10-04T12:00:00Z",
        },
      }),
    );
    await page.addInitScript(() => {
      Object.assign(window, {
        google: {
          maps: {
            importLibrary: async () => {
              document.documentElement.dataset.googleLoaded = "yes";
            },
          },
        },
      });
    });
    await page.goto("/place/node%2F1");
    await expect(page.locator("html")).toHaveAttribute(
      "data-google-loaded",
      "yes",
    );
    await expect(
      page.locator(".place-address + .google-place-card"),
    ).toBeVisible();
    await expect(
      page.getByText("Sprawdź konkretne cechy miejsca.", { exact: false }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Pokaż informacje Google Maps" }),
    ).toHaveCount(0);
    const search = page.locator("gmp-place-search");
    await expect(search).toHaveCount(1);
    await expect(page.locator("gmp-place-details")).toHaveCount(0);
    expect(
      await page
        .locator("gmp-place-text-search-request")
        .evaluate(
          (el) => (el as HTMLElement & { textQuery: string }).textQuery,
        ),
    ).toContain("Muzeum testowe");
    await search.evaluate((el, failed) => {
      el.dispatchEvent(
        failed
          ? new Event("gmp-error")
          : Object.assign(new Event("gmp-select"), {
              place: { id: "chosen-google-id" },
            }),
      );
    }, fail);
    if (fail) {
      await expect(
        page
          .getByRole("region", { name: "Informacje Google Maps" })
          .getByRole("status"),
      ).toContainText("chwilowo niedostępne");
    } else {
      await expect(
        page.locator("gmp-place-details-place-request"),
      ).toHaveAttribute("place", "chosen-google-id");
      await expect(search).toHaveCount(0);
      await expect(page.locator("gmp-place-all-content")).toHaveCount(1);
      await page
        .locator("gmp-place-details")
        .evaluate((el) => el.dispatchEvent(new Event("gmp-load")));
      await expect(page.getByText("Ładowanie karty Google Maps…")).toHaveCount(
        0,
      );
    }
    await expect(
      page.getByRole("heading", { name: "Muzeum testowe", exact: true }),
    ).toBeVisible();
    await page.getByRole("tab", { name: "Informacje", exact: true }).click();
    await expect(
      page.locator(".place-address + .google-place-card"),
    ).toBeVisible();
    await expect(page.locator("gmp-place-details")).toHaveCount(fail ? 0 : 1);
  });
}
