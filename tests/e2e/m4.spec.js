const fs = require("node:fs");
const { test, expect } = require("@playwright/test");

function waitText(value) {
  return Number(value || 0).toFixed(1) + "s";
}

test("live UI and deterministic replay match API state", async ({ page, request }) => {
  fs.mkdirSync("artifacts", { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto("/");
  await expect(page.locator("#comparison-cards .comparison-card")).toHaveCount(5);

  await request.post("/api/control", {
    data: {
      action: "reset",
      scenario: "evening",
      policy: "capr",
      control_mode: "conventional",
      speed: 120,
    },
  });
  await page.waitForTimeout(900);
  const pauseResponse = await request.post("/api/control", {
    data: {
      action: "pause",
      scenario: "evening",
      policy: "capr",
      control_mode: "conventional",
      speed: 120,
    },
  });
  const snapshot = await pauseResponse.json();

  await expect(page.locator("#clock")).toHaveText(snapshot.clock);
  await expect(page.locator("#queue")).toHaveText(String(snapshot.metrics.current_queue));
  await expect(page.locator("#avg-wait")).toHaveText(waitText(snapshot.metrics.avg_wait));
  await expect(page.locator("#p95-wait")).toHaveText(waitText(snapshot.metrics.p95_wait));
  await expect(page.locator("#served")).toHaveText(`${snapshot.metrics.served} served`);

  for (const car of snapshot.elevators) {
    const locator = page.locator(`[data-car-id="${car.id}"]`);
    await expect(locator).toHaveAttribute("data-floor", String(car.floor));
    await expect(locator).toHaveAttribute("data-load", String(car.load));
    await expect(locator).toHaveAttribute("data-phase", String(car.phase));
  }

  for (let floor = 1; floor <= 18; floor += 1) {
    const queue = snapshot.queues[String(floor)] || { up: 0, down: 0 };
    const expectedQueue = Number(queue.up || 0) + Number(queue.down || 0);
    await expect(page.locator(`.heat-cell[data-floor="${floor}"]`)).toHaveAttribute(
      "data-queue",
      String(expectedQueue),
    );
  }

  await page.locator("#save-replay").click();
  await expect(page.locator("#replay-status")).toHaveText("saved run");
  const replayResponse = await request.get("/api/replay");
  const replay = await replayResponse.json();
  expect(replay.source).toBe("saved_run");
  expect(replay.frame_count).toBeGreaterThan(2);

  await page.locator("#enter-replay").click();
  await expect(page.locator("#live-state span")).toHaveText("REPLAY MODE");
  await page.locator("#replay-slider").evaluate((element) => {
    element.value = "0";
    element.dispatchEvent(new Event("input", { bubbles: true }));
  });
  const firstFrame = replay.frames[0];
  await expect(page.locator("#clock")).toHaveText(firstFrame.clock);
  await expect(page.locator("#queue")).toHaveText(String(firstFrame.metrics.current_queue));
  await expect(page.locator("#avg-wait")).toHaveText(waitText(firstFrame.metrics.avg_wait));
  await expect(page.locator("#replay-frame")).toHaveText(`Frame 1 / ${replay.frames.length}`);

  await page.locator("#return-live").click();
  await expect(page.locator("#clock")).toHaveText(snapshot.clock);
  await expect(page.locator("#live-state span")).toHaveText("PAUSED");

  await page.screenshot({ path: "artifacts/m4-dashboard-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("#building")).toBeVisible();
  await expect(page.locator("#comparison-cards")).toBeVisible();
  await page.screenshot({ path: "artifacts/m4-dashboard-mobile.png", fullPage: true });
});
