import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "accessibility.spec.ts",
  outputDir: "./a11y-results",
  workers: 1,
  timeout: 180000,
  use: {
    baseURL: "http://127.0.0.1:5337",
    actionTimeout: 10000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "tablet", use: { viewport: { width: 768, height: 1024 } } },
    {
      name: "mobile",
      use: { viewport: { width: 390, height: 844 }, hasTouch: true },
    },
    { name: "reflow", use: { viewport: { width: 320, height: 900 } } },
  ],
  webServer: [
    {
      command:
        "PYTHONPATH=../src ../.venv/bin/python ../tests/account_server.py",
      url: "http://127.0.0.1:8137/openapi.json",
      reuseExistingServer: !process.env.CI,
    },
    {
      command:
        "npm run dev -- --port 5337 --host 127.0.0.1 --config vite.account.config.ts",
      url: "http://127.0.0.1:5337",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
