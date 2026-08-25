const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "tests/e2e",
  timeout: 45000,
  workers: 1,
  snapshotPathTemplate: "{testDir}/__screenshots__/{arg}{ext}",
  expect: {
    toHaveScreenshot: {
      animations: "disabled",
      maxDiffPixelRatio: 0.08,
    },
  },
  use: {
    baseURL: process.env.BASE_URL || "http://127.0.0.1:4173/",
    browserName: "chromium",
    trace: "retain-on-failure",
  },
  webServer: process.env.BASE_URL ? undefined : {
    command: "python3 -m app.server --port 4173",
    url: "http://127.0.0.1:4173/api/health",
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
