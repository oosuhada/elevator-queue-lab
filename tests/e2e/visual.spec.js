const fs = require("node:fs");
const path = require("node:path");
const { test, expect } = require("@playwright/test");


async function assertLayoutIntegrity(page) {
  const geometry = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
  }));
  expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.viewportWidth + 1);
  expect(geometry.bodyWidth).toBeLessThanOrEqual(geometry.viewportWidth + 1);
}

async function captureVisual(page, name, masks = []) {
  await assertLayoutIntegrity(page);
  if (process.env.CI) {
    const output = path.join("artifacts", "visual-ci");
    fs.mkdirSync(output, { recursive: true });
    await page.screenshot({ path: path.join(output, name), fullPage: true });
    return;
  }
  await expect(page).toHaveScreenshot(name, { fullPage: true, mask: masks });
}


test("stable workbench layouts retain their visual information hierarchy", async ({ page, request, baseURL }) => {
  await page.setViewportSize({ width: 1365, height: 900 });
  await request.post("/api/control", { data: { action: "reset_paused", scenario: "lunch", policy: "capr", speed: 1 } });
  for (let index = 0; index < 24; index += 1) {
    await request.post("/api/control", { data: { action: "step" } });
  }
  await page.goto(baseURL);
  await expect(page.getByRole("heading", { name: "Live Operations" })).toBeVisible();
  await expect(page.locator("#live-state span")).toHaveText("PAUSED");
  await expect(page.locator("#elapsed")).toHaveText("T+00:24");
  const masks = [page.locator(".status-bar"), page.locator("#clock"), page.locator("#elapsed")];
  await captureVisual(page, "live-operations-desktop.png", masks);

  await page.locator("#save-replay").click();
  await expect(page.locator("#replay-status")).toHaveText("saved run");
  await page.locator("#enter-replay").click();
  await expect(page.locator("#live-state span")).toHaveText("REPLAY MODE");
  await captureVisual(page, "replay.png", masks);
  await page.locator("#return-live").click();
  await expect(page.locator("#live-state span")).toHaveText("PAUSED");

  await page.getByRole("button", { name: "Experiments" }).click();
  await expect(page.getByRole("heading", { name: "Experiments" })).toBeVisible();
  await captureVisual(page, "experiments.png", [page.locator(".status-bar")]);

  await page.getByRole("button", { name: "Theory" }).click();
  await expect(page.getByRole("heading", { name: "Counterflow Criticality" })).toBeVisible();
  await captureVisual(page, "theory.png", [page.locator(".status-bar")]);

  await page.getByRole("button", { name: "Models" }).click();
  await expect(page.getByRole("heading", { name: "Models" })).toBeVisible();
  await captureVisual(page, "models.png", [page.locator(".status-bar")]);

  await page.getByRole("button", { name: "Explorer" }).click();
  await expect(page.getByRole("heading", { name: "Object Explorer" })).toBeVisible();
  await expect(page.getByTestId("decision-trace")).toBeVisible();
  await captureVisual(page, "explorer-decision-trace.png", [page.locator(".status-bar")]);

  await page.getByRole("button", { name: "Live Operations", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { name: "Live Operations" })).toBeVisible();
  await captureVisual(page, "live-operations-mobile.png", [page.locator(".status-bar"), page.locator("#clock"), page.locator("#elapsed")]);
});
