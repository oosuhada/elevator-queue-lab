const fs = require("node:fs");
const path = require("node:path");
const { test, expect } = require("@playwright/test");


test.skip(!process.env.SHOWCASE, "showcase capture runs only through npm run capture:showcase");

test("capture portfolio showcase from the real workbench", async ({ page, request, baseURL }) => {
  const output = path.join("docs", "assets", "showcase");
  fs.mkdirSync(output, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(baseURL);
  await expect(page.getByRole("heading", { name: "Live Operations" })).toBeVisible();
  await request.post("/api/control", { data: { action: "reset", scenario: "shock", policy: "capr", speed: 120 } });
  await expect.poll(async () => Number((await (await request.get("/api/snapshot")).json()).metrics.reassignments || 0), { timeout: 15000 }).toBeGreaterThan(0);
  await request.post("/api/control", { data: { action: "pause" } });
  await expect(page.locator("#live-state span")).toHaveText("PAUSED");
  await page.screenshot({ path: path.join(output, "m8-live-operations.png"), fullPage: true });

  await page.locator("#save-replay").click();
  await page.locator("#enter-replay").click();
  await expect(page.locator("#live-state span")).toHaveText("REPLAY MODE");
  await page.screenshot({ path: path.join(output, "m8-replay.png"), fullPage: true });
  await page.locator("#return-live").click();

  for (const [name, file] of [
    ["Experiments", "m8-experiments.png"],
    ["Theory", "m8-theory.png"],
    ["Models", "m8-models.png"],
    ["Explorer", "m8-explorer.png"],
  ]) {
    await page.getByRole("button", { name }).click();
    if (name === "Explorer") {
      await page.getByRole("button", { name: /DispatchDecision/ }).click();
      await expect(page.getByTestId("decision-trace")).toBeVisible();
    }
    await page.screenshot({ path: path.join(output, file), fullPage: true });
  }
});
