import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "account.spec.ts",
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:5337",
    trace: "retain-on-failure",
    actionTimeout: 10000,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
  webServer: [
    {
      command:
        "PYTHONPATH=../src ../.venv/bin/python ../tests/account_server.py",
      url: "http://127.0.0.1:8137/openapi.json",
      reuseExistingServer: false,
    },
    {
      command:
        "npm run dev -- --port 5337 --host 127.0.0.1 --config vite.account.config.ts",
      url: "http://127.0.0.1:5337",
      reuseExistingServer: false,
    },
  ],
});
