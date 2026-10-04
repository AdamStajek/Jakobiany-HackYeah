import { defineConfig } from "@playwright/test";
import accessibility from "./playwright.accessibility.config";

export default defineConfig({
  ...accessibility,
  testMatch: ["ux.spec.ts", "ai-search.spec.ts"],
  outputDir: "./ux-results",
  projects: [320, 390, 768, 940, 1024, 1440].map((width) => ({
    name: `${width}px`,
    use: { viewport: { width, height: 900 }, hasTouch: width <= 1024 },
  })),
});
