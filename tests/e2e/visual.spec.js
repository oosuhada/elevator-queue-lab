const { test, expect } = require("@playwright/test");


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
  await expect(page).toHaveScreenshot("live-operations-desktop.png", { fullPage: true, mask: masks });

  await page.locator("#save-replay").click();
  await expect(page.locator("#replay-status")).toHaveText("saved run");
  await page.locator("#enter-replay").click();
  await expect(page.locator("#live-state span")).toHaveText("REPLAY MODE");
  await expect(page).toHaveScreenshot("replay.png", { fullPage: true, mask: masks });
  await page.locator("#return-live").click();
  await expect(page.locator("#live-state span")).toHaveText("PAUSED");

  await page.getByRole("button", { name: "Experiments" }).click();
  await expect(page).toHaveScreenshot("experiments.png", { fullPage: true, mask: [page.locator(".status-bar")] });

  await page.getByRole("button", { name: "Theory" }).click();
  await expect(page).toHaveScreenshot("theory.png", { fullPage: true, mask: [page.locator(".status-bar")] });

  await page.getByRole("button", { name: "Models" }).click();
  await expect(page).toHaveScreenshot("models.png", { fullPage: true, mask: [page.locator(".status-bar")] });

  await page.getByRole("button", { name: "Explorer" }).click();
  await expect(page.getByTestId("decision-trace")).toBeVisible();
  await expect(page).toHaveScreenshot("explorer-decision-trace.png", { fullPage: true, mask: [page.locator(".status-bar")] });

  await page.getByRole("button", { name: "Live Operations", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page).toHaveScreenshot("live-operations-mobile.png", { fullPage: true, mask: [page.locator(".status-bar"), page.locator("#clock"), page.locator("#elapsed")] });
});
