const fs = require("node:fs");
const { test, expect } = require("@playwright/test");

function waitText(value) {
  return Number(value || 0).toFixed(1) + "s";
}

test("live UI and deterministic replay match API state", async ({ page, request, baseURL }) => {
  fs.mkdirSync("artifacts", { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto(baseURL);
  await expect(page.locator("#comparison-cards .comparison-card")).toHaveCount(5);
  await expect(page.locator("#policy-leaders .policy-leader")).toHaveCount(3);
  await expect(page.locator("#policy-density-chart .density-series")).toHaveCount(5);
  await expect(page.locator("#policy-ranking-body tr")).toHaveCount(5);
  await expect(page.locator("#policy-ranking-body tr").first()).toHaveAttribute("data-policy", "capr");
  await expect(page.locator("#comparison-cards .comparison-card").first()).toHaveAttribute("data-policy", "capr");
  await expect(page.locator("#policy-leaders .policy-leader.primary strong")).toHaveText("CAPR");
  await expect(page.locator("#theory-takeaway")).toBeVisible();
  await expect(page.locator("#theory-takeaway .theory-takeaway-copy > strong"))
    .toHaveText("Congestion alone is not the trigger.");
  await expect(page.locator("#theory-takeaway")).toContainText("heavy traffic and enough counterflow rise together");
  await expect(page.locator("#theory-takeaway")).toContainText("Morning");
  await expect(page.locator("#theory-takeaway")).toContainText("B 2.56");
  await expect(page.locator("#theory-takeaway")).toContainText("Lunch");
  await expect(page.locator("#theory-takeaway")).toContainText("B 15.84");
  await expect(page.locator("#theory-leaders .theory-leader")).toHaveCount(4);
  await expect(page.locator('#theory-scatter [data-kind="discovery"]')).toHaveCount(40);
  await expect(page.locator('#theory-scatter [data-kind="validation"]')).toHaveCount(18);
  await expect(page.locator("#theory-rule strong")).toContainText("0.158");
  await expect(page.locator("#theory-caveat")).toContainText("fuzzy phase transition");

  await page.locator("#evidence-scenario").selectOption("mixed_day");
  await expect(page.locator("#policy-ranking-body tr").first()).toHaveAttribute("data-policy", "collective");
  await expect(page.locator("#policy-leaders .policy-leader.primary strong")).toHaveText("Collective");
  await expect(page.locator("#policy-leaders .policy-leader").nth(1).locator("strong")).toHaveText("CAPR");
  await page.locator("#evidence-scenario").selectOption("lunch");

  await request.post("/api/control", {
    data: {
      action: "reset",
      scenario: "shock",
      policy: "capr",
      control_mode: "conventional",
      speed: 120,
    },
  });
  await expect.poll(async () => {
    const response = await request.get("/api/snapshot");
    const body = await response.json();
    return Number(body.metrics.reassignments || 0);
  }, { timeout: 8000 }).toBeGreaterThan(0);
  const pauseResponse = await request.post("/api/control", {
    data: {
      action: "pause",
      scenario: "shock",
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
  await expect(page.locator("#wait-chart")).toBeVisible();
  await expect(page.locator("#queue-trend-chart")).toBeVisible();
  const latestQueueHistory = snapshot.history.at(-1);
  expect(latestQueueHistory).toBeTruthy();
  await expect(page.locator("#queue-trend-value"))
    .toHaveText(Number(latestQueueHistory.avg_queue).toFixed(2));

  const expectedCalls = Math.min(12, snapshot.calls.length);
  await expect(page.locator("#calls .call")).toHaveCount(expectedCalls);
  const expectedLinks = snapshot.calls.filter((call) => call.assigned).slice(0, 16).length;
  await expect(page.locator("#assignment-overlay line")).toHaveCount(expectedLinks);

  const latestDecision = snapshot.decision_tail.at(-1);
  expect(latestDecision).toBeTruthy();
  const candidateRows = latestDecision.candidates || latestDecision.evaluations || [];
  await expect(page.locator("#decision-candidates tr")).toHaveCount(candidateRows.length);
  await expect(page.locator("#decision-reason")).not.toHaveText("Waiting for the first dispatch decision…");

  expect(snapshot.metrics.reassignments).toBeGreaterThan(0);
  const relevantEventKinds = new Set(["assign", "reassign", "assignment_invalidated", "full_pass"]);
  const relevantEvents = snapshot.event_tail
    .filter((event) => relevantEventKinds.has(event.kind))
    .slice(-8);
  expect(relevantEvents.length).toBeGreaterThan(0);
  await expect(page.locator("#event-stream .event")).toHaveCount(relevantEvents.length);
  if (relevantEvents.some((event) => event.kind === "reassign")) {
    await expect(page.locator("#event-stream .event-reassign").first()).toBeVisible();
  }

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

  const evidenceResponse = await request.get("/api/experiment");
  const evidence = await evidenceResponse.json();
  const lunchCollective = evidence.baseline.scenarios.lunch.policies.collective;
  await expect(page.locator('#comparison-cards .comparison-card[data-policy="collective"] > strong'))
    .toHaveText(`${Number(lunchCollective.avg_wait).toFixed(2)}s`);
  const theoryResponse = await request.get("/api/theory");
  const theory = await theoryResponse.json();
  expect(theory.discovery.cells).toHaveLength(40);
  expect(theory.validation.cells).toHaveLength(18);
  expect(theory.validation.result.recall).toBe(1);

  await page.screenshot({ path: "artifacts/m4-dashboard-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("#building")).toBeVisible();
  await expect(page.locator("#comparison-cards")).toBeVisible();
  await expect(page.locator("#policy-density-chart")).toBeVisible();
  await expect(page.locator("#policy-ranking-body tr")).toHaveCount(5);
  await expect(page.locator("#theory-scatter")).toBeVisible();
  await expect(page.locator("#canonical-theory-row article")).toHaveCount(4);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: "artifacts/m4-dashboard-mobile.png", fullPage: true });
});
