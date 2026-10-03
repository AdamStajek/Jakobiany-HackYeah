import { test, expect } from "@playwright/test";

test("zdjęcie miejsca ma autora, licencję, źródło i widok galerii", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/session", (route) =>
    route.fulfill({ status: 401, json: { error: { code: "UNAUTHORIZED" } } }),
  );
  await page.route("**/api/v1/places/**", (route) =>
    route.fulfill({
      json: {
        id: "node/1",
        name: "Muzeum ze zdjęciem",
        category: "Muzeum",
        address: "Kraków",
        location: { lat: 50.06, lon: 19.94 },
        distance_m: null,
        facts: [],
        barriers: [],
        attribution: [],
        updated_at: "2026-10-03T12:00:00Z",
        photos: [
          {
            url: "https://upload.wikimedia.org/test.jpg",
            original_url: "https://upload.wikimedia.org/test.jpg",
            source_url: "https://commons.wikimedia.org/wiki/File:Test.jpg",
            title: "Test.jpg",
            author: "Jan Fotograf",
            credit: "Praca własna",
            license: "CC BY-SA 4.0",
            license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
            description: "",
          },
        ],
      },
    }),
  );
  await page.route("https://upload.wikimedia.org/test.jpg", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="green"/></svg>',
    }),
  );
  await page.goto("/place/node%2F1");
  await expect(
    page.getByRole("heading", { name: "Muzeum ze zdjęciem", level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Muzeum ze zdjęciem — Test.jpg" }),
  ).toBeVisible();
  await expect(page.locator("figcaption")).toContainText("Jan Fotograf");
  await expect(
    page.getByRole("link", { name: "CC BY-SA 4.0" }),
  ).toHaveAttribute("href", "https://creativecommons.org/licenses/by-sa/4.0/");
  await page.getByRole("tab", { name: "Zdjęcia", exact: true }).click();
  await expect(page.locator('[role="tabpanel"] img')).toBeVisible();
  await expect(page.locator('[role="tabpanel"] figcaption')).toContainText(
    "Wikimedia Commons",
  );
});
