const fs = require("node:fs");
const { test, expect } = require("@playwright/test");


test("M8 workbench preserves live/replay evidence and exposes analysis surfaces", async ({ page, request, baseURL }) => {
  fs.mkdirSync("artifacts", { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(baseURL);

  await expect(page.getByRole("heading", { name: "Live Operations" })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toHaveAttribute("aria-label", "Open Live Operations");
  await expect(page.locator("#building")).toBeVisible();
  await expect(page.locator(".floor-line")).toHaveCount(18);
  await expect(page.locator("[data-car-id]")).toHaveCount(6);

  await page.locator("#scenario").selectOption("shock");
  await expect.poll(async () => (await (await request.get("/api/snapshot")).json()).scenario).toBe("shock");
  await page.locator("#policy").selectOption("collective");
  await expect.poll(async () => (await (await request.get("/api/snapshot")).json()).policy).toBe("collective");
  await page.locator("#policy").selectOption("capr");
  await expect.poll(async () => (await (await request.get("/api/snapshot")).json()).policy).toBe("capr");
  await page.locator("#speed").selectOption("120");

  await expect.poll(async () => {
    const snapshot = await (await request.get("/api/snapshot")).json();
    return Number(snapshot.metrics.reassignments || 0);
  }, { timeout: 15000 }).toBeGreaterThan(0);

  const pauseResponse = await request.post("/api/control", { data: { action: "pause" } });
  const paused = await pauseResponse.json();
  await expect(page.locator("#clock")).toHaveText(paused.clock);
  await expect(page.locator("#queue")).toHaveText(String(paused.metrics.current_queue));
  await expect(page.locator("#avg-wait")).toHaveText(`${Number(paused.metrics.avg_wait).toFixed(1)}s`);
  await expect(page.locator("#p95-wait")).toHaveText(`${Number(paused.metrics.p95_wait).toFixed(1)}s`);
  await expect(page.locator("#served")).toHaveText(`${paused.metrics.served} served`);
  await expect(page.locator(".heat-cell")).toHaveCount(18);

  const latestDecision = paused.decision_tail.at(-1);
  expect(latestDecision).toBeTruthy();
  await expect(page.locator("#decision-reason")).toHaveText(latestDecision.reason);
  await expect(page.locator("#decision-candidates tr")).toHaveCount(latestDecision.candidates.length);
  await expect(page.locator(".candidate-instrument")).toHaveCount(latestDecision.candidates.length);
  await expect(page.locator(".score-decomposition").first()).toBeVisible();
  await expect(page.locator(".reassignment-gate")).toContainText("gate, not score term");
  for (const car of paused.elevators) {
    const locator = page.locator(`[data-car-id="${car.id}"]`);
    await expect(locator).toHaveAttribute("data-floor", String(car.floor));
    await expect(locator).toHaveAttribute("data-load", String(car.load));
    await expect(locator).toHaveAttribute("data-phase", String(car.phase));
  }

  await page.locator("#save-replay").click();
  await expect(page.locator("#replay-status")).toHaveText("saved run");
  const replay = await (await request.get("/api/replay")).json();
  expect(replay.source).toBe("saved_run");
  expect(replay.frame_count).toBeGreaterThan(2);
  await page.locator("#enter-replay").click();
  await expect(page.locator("#live-state span")).toHaveText("REPLAY MODE");
  await expect(page.locator("#clock")).toHaveText(replay.frames[0].clock);
  await expect(page.locator("#queue")).toHaveText(String(replay.frames[0].metrics.current_queue));
  await expect(page.locator(".timeline-marker")).not.toHaveCount(0);
  const finalReplayIndex = replay.frames.length - 1;
  await page.locator("#replay-slider").fill(String(finalReplayIndex));
  await expect(page.locator("#clock")).toHaveText(replay.frames[finalReplayIndex].clock);
  await expect(page.locator("#queue")).toHaveText(String(replay.frames[finalReplayIndex].metrics.current_queue));
  const replayDecision = replay.frames[finalReplayIndex].decision_tail.at(-1);
  if (replayDecision) {
    await expect(page.locator("#decision-reason")).toHaveText(replayDecision.reason);
  }
  await page.locator("#return-live").click();
  await expect(page.locator("#live-state span")).toHaveText("PAUSED");
  await expect(page.locator("#clock")).toHaveText(paused.clock);
  await page.screenshot({ path: "artifacts/m8-live-operations-desktop.png", fullPage: true });

  await page.getByRole("button", { name: "Experiments" }).click();
  await expect(page.getByRole("heading", { name: "Experiments" })).toBeVisible();
  await expect(page.locator("#comparison-cards .comparison-card")).toHaveCount(5);
  await expect(page.locator(".verdict-key")).toHaveCount(5);
  await expect(page.locator("#policy-density-chart .density-series")).toHaveCount(5);
  await expect(page.locator("#policy-ranking-body tr")).toHaveCount(5);
  const experiment = await (await request.get("/api/experiment")).json();
  const lunchCollective = experiment.baseline.scenarios.lunch.policies.collective;
  await expect(page.locator('#comparison-cards .comparison-card[data-policy="collective"] > strong')).toHaveText(`${Number(lunchCollective.avg_wait).toFixed(2)}s`);
  await page.screenshot({ path: "artifacts/m8-experiments.png", fullPage: true });

  await page.getByRole("button", { name: "Theory" }).click();
  await expect(page.locator("#theory-takeaway")).toContainText("Congestion alone is not the trigger.");
  await expect(page.locator("#theory-takeaway")).toContainText("traffic intensity and counterflow rise together");
  await expect(page.locator('#theory-scatter [data-kind="discovery"]')).toHaveCount(40);
  await expect(page.locator('#theory-scatter [data-kind="validation"]')).toHaveCount(18);
  const theory = await (await request.get("/api/theory")).json();
  expect(theory.validation.result.accuracy).toBe(0.722222);
  expect(theory.validation.result.recall).toBe(1);
  await page.screenshot({ path: "artifacts/m8-theory.png", fullPage: true });

  await page.getByRole("button", { name: "Models" }).click();
  await expect(page.getByText("Learned-controller superiority was not established.")).toBeVisible();
  await expect(page.getByText("negative / mixed result")).toBeVisible();

  await page.getByRole("button", { name: "Runs" }).click();
  await expect(page.getByText("SimulationRunArtifact").first()).toBeVisible();
  const runs = await (await request.get("/api/runs")).json();
  const runId = runs.runs[0].run_id;
  await expect(page.getByText(runId).first()).toBeVisible();

  await page.getByRole("button", { name: "Explorer" }).click();
  await expect(page.getByTestId("explorer-workbench")).toBeVisible();
  await page.locator(".object-type-list").getByRole("button", { name: /^DispatchDecision / }).click();
  await expect(page.locator(".object-list button").first()).toBeVisible();
  await page.locator(".object-list button").first().click();
  await expect(page.getByTestId("decision-trace")).toBeVisible();
  await expect(page.locator(".react-flow__node").first()).toBeVisible();
  await expect(page.locator(".graph-alternative")).toHaveAttribute("open", "");
  await expect(page.locator(".graph-alternative button").first()).toBeVisible();
  const graph = await (await request.get(`/api/runs/${runId}/graph`)).json();
  expect(graph.nodes.length).toBeGreaterThan(6);
  expect(graph.provenance.database).toBeNull();

  const askInput = page.getByLabel("Ask this run question");
  await askInput.fill("Compare this run with collective");
  await page.getByRole("button", { name: "Query evidence" }).click();
  await expect(page.locator(".ask-run-answer")).toContainText("committed 30-seed M3 evidence");
  await page.screenshot({ path: "artifacts/m8-explorer-decision-trace.png", fullPage: true });

  await page.getByRole("button", { name: "Live Operations", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("#building")).toBeVisible();
  await expect(page.locator("[data-car-id]")).toHaveCount(6);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: "artifacts/m8-live-operations-mobile.png", fullPage: true });
});
