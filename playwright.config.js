const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "tests/e2e",
  timeout: 30000,
  workers: 1,
  use: {
    baseURL: process.env.BASE_URL || "http://127.0.0.1:4173/",
    browserName: "chromium",
  },
});
