import { test, expect } from "@playwright/test";
import { places, assess } from "../../src/data/mock";
import { emptyConstraints } from "../../src/data/types";

test("map tab stays responsive: zoom, markers, details and navigation", async ({ page, isMobile }) => {
  test.setTimeout(20000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/v1/places/search", (route) => route.fulfill({
    json: { items: places.map((place) => ({ ...place, assessment: assess(place, emptyConstraints) })), next_cursor: null, warnings: [], attribution: [] },
  }));
  await page.route("**/api/v1/places/pod-wawelem", (route) => route.fulfill({ json: places[0] }));
  await page.goto("/");
  const navigation = page.getByRole("navigation", { name: isMobile ? "Nawigacja mobilna" : "Nawigacja główna", exact: true });
  await navigation.getByRole("link", { name: "Mapa", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Mapa Krakowa" })).toBeVisible();
  const map = page.getByRole("region", { name: "Mapa wyników" });
  const marker = map.getByRole("button", { name: "Pokaż na mapie: Kawiarnia Pod Wawelem", exact: true });
  await expect(marker).toBeVisible();
  if (!isMobile) {
    await page.getByRole("button", { name: "Switch to English", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Kraków map" })).toBeVisible();
    await page.getByRole("button", { name: "Przełącz na polski", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Mapa Krakowa" })).toBeVisible();
  }
  const drawing = map.locator(".map-canvas");
  const original = await drawing.getAttribute("data-zoom");
  await map.getByRole("button", { name: "Powiększ mapę" }).click();
  await expect(drawing).not.toHaveAttribute("data-zoom", original!);
  await map.getByRole("button", { name: "Pomniejsz mapę" }).click();
  await expect(drawing).toHaveAttribute("data-zoom", original!);
  await marker.click();
  await expect(map.locator(".map-popup")).toContainText("Kawiarnia Pod Wawelem");
  await map.getByRole("button", { name: "Zamknij szczegóły znacznika" }).click();
  await expect(map.locator(".map-popup")).toHaveCount(0);
  await marker.click();
  await map.getByRole("link", { name: "Zobacz szczegóły" }).click();
  await expect(page.getByRole("heading", { name: "Kawiarnia Pod Wawelem", level: 1 })).toBeVisible();
  await navigation.getByRole("link", { name: "Mapa", exact: true }).click();
  await expect(marker).toBeVisible();
  await page.getByRole("link", { name: "Zobacz listę miejsc" }).click();
  await expect(page.getByRole("heading", { name: "Znajdź swoje miejsce" })).toBeVisible();
  expect(errors).toEqual([]);
});
