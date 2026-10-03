import { expect, it, vi } from "vitest";

it("switches map labels from Polish to English and back", async () => {
  vi.stubGlobal("localStorage", { getItem: () => "pl", setItem: vi.fn() });
  vi.stubGlobal("document", { documentElement: { lang: "pl" } });
  try {
    const { setLanguage, translate } = await import("../src/i18n");
    const labels = [
      ["Powiększ mapę", "Zoom in"],
      ["Pomniejsz mapę", "Zoom out"],
      ["Twoja lokalizacja", "Your location"],
      ["Pokaż na mapie:", "Show on map:"],
      ["Najbliższy adres:", "Nearest address:"],
      ["Przywróć widok mapy", "Reset map view"],
    ];
    setLanguage("en");
    for (const [pl, en] of labels) expect(translate(pl)).toBe(en);
    setLanguage("pl");
    for (const [pl, en] of labels) expect(translate(en)).toBe(pl);
  } finally {
    vi.unstubAllGlobals();
  }
});
