const FLOOR_COUNT = 18;
const floorLabels = document.querySelector("#floor-labels");
const floors = document.querySelector("#floors");
const shafts = document.querySelector("#shafts");
const assignmentOverlay = document.querySelector("#assignment-overlay");
const controls = {
  scenario: document.querySelector("#scenario"),
  policy: document.querySelector("#policy"),
  controlMode: document.querySelector("#control-mode"),
  speed: document.querySelector("#speed"),
  pause: document.querySelector("#pause"),
  reset: document.querySelector("#reset"),
};
const replayControls = {
  save: document.querySelector("#save-replay"),
  enter: document.querySelector("#enter-replay"),
  live: document.querySelector("#return-live"),
  slider: document.querySelector("#replay-slider"),
  status: document.querySelector("#replay-status"),
};

const carElements = new Map();
const heatmapElements = new Map();
let displayMode = "live";
let savedReplay = null;
let latestLiveSnapshot = null;
let experimentPayload = null;

function floorBottomPercent(floor) {
  return ((floor - 1) / (FLOOR_COUNT - 1)) * 100;
}

function buildBuilding() {
  for (let floor = 1; floor <= FLOOR_COUNT; floor += 1) {
    const label = document.createElement("div");
    label.className = `floor-label ${floor === FLOOR_COUNT ? "roof-access" : ""}`;
    label.textContent = floor === FLOOR_COUNT ? `${floor}F · ROOF` : `${floor}F`;
    label.style.bottom = `calc(${floorBottomPercent(floor)}% - 4px)`;
    floorLabels.appendChild(label);

    const line = document.createElement("div");
    line.className = `floor-line ${floor === 1 ? "lobby" : ""} ${floor === FLOOR_COUNT ? "roof-access" : ""}`;
    line.dataset.floor = String(floor);
    line.style.bottom = `${floorBottomPercent(floor)}%`;
    floors.appendChild(line);
  }

  ["L1", "L2", "L3", "H1", "H2", "H3"].forEach((id) => {
    const shaft = document.createElement("div");
    shaft.className = "shaft";
    shaft.dataset.id = id;
    const car = document.createElement("div");
    car.className = `car ${id.startsWith("L") ? "low" : "high"}`;
    car.dataset.carId = id;
    car.innerHTML = `<span>${id}</span><span>0/14</span>`;
    shaft.appendChild(car);
    shafts.appendChild(shaft);
    carElements.set(id, car);
  });

  const heatmap = document.querySelector("#floor-heatmap");
  for (let floor = 1; floor <= FLOOR_COUNT; floor += 1) {
    const cell = document.createElement("div");
    cell.className = "heat-cell";
    cell.dataset.floor = String(floor);
    cell.dataset.queue = "0";
    cell.innerHTML = `<span>${floor === FLOOR_COUNT ? `${floor}R` : `${floor}F`}</span><strong>0</strong>`;
    heatmap.appendChild(cell);
    heatmapElements.set(String(floor), cell);
  }
}

function fmtSeconds(value) {
  return `${Number(value || 0).toFixed(1)}s`;
}

function historyFromReplay(index) {
  if (!savedReplay) return [];
  return savedReplay.frames
    .slice(0, index + 1)
    .filter((frame) => Number(frame.sim_time) % 15 === 0)
    .map((frame) => ({
      sim_time: frame.sim_time,
      avg_wait: frame.metrics.avg_wait,
      p95_wait: frame.metrics.p95_wait,
    }));
}

function render(snapshot, options = {}) {
  const replay = Boolean(options.replay);
  if (!replay) latestLiveSnapshot = snapshot;

  controls.scenario.value = snapshot.scenario;
  controls.policy.value = snapshot.policy;
  controls.controlMode.value = snapshot.simulation_config?.control_mode || "conventional";
  document.querySelector("#clock").textContent = snapshot.clock;
  const minutes = Math.floor(Number(snapshot.sim_time) / 60);
  const seconds = Number(snapshot.sim_time) % 60;
  document.querySelector("#elapsed").textContent = `T+${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

  const live = document.querySelector("#live-state");
  live.classList.toggle("paused", replay || !snapshot.running);
  live.classList.toggle("replay", replay);
  live.querySelector("span").textContent = replay ? "REPLAY MODE" : snapshot.running ? "LIVE SIMULATION" : "PAUSED";
  controls.pause.textContent = snapshot.running ? "Pause" : "Resume";

  const m = snapshot.metrics;
  document.querySelector("#avg-wait").textContent = fmtSeconds(m.avg_wait);
  document.querySelector("#p95-wait").textContent = fmtSeconds(m.p95_wait);
  document.querySelector("#queue").textContent = String(m.current_queue);
  document.querySelector("#queue").dataset.apiValue = String(m.current_queue);
  document.querySelector("#avg-queue").textContent = `Lq avg ${Number(m.avg_queue).toFixed(2)}`;
  document.querySelector("#misses").textContent = String(m.missed_capacity);
  document.querySelector("#reassignments").textContent = `${Number(m.reassignments || 0)} predictive reassignments`;
  document.querySelector("#served").textContent = `${m.served} served`;
  document.querySelector("#lq-observed").textContent = Number(m.avg_queue).toFixed(2);
  document.querySelector("#lq-derived").textContent = Number(m.little_law_lq).toFixed(2);
  document.querySelector("#arrival-rate").textContent = `${Number(m.arrival_rate_per_min).toFixed(1)}/min`;

  snapshot.elevators.forEach((car) => {
    const el = carElements.get(car.id);
    if (!el) return;
    el.style.bottom = `calc(${floorBottomPercent(car.floor)}% - 14px)`;
    el.classList.toggle("full", car.load >= car.capacity);
    el.classList.toggle("door-open", Boolean(car.door_open));
    const arrow = car.direction > 0 ? "↑" : car.direction < 0 ? "↓" : "·";
    el.innerHTML = `<span>${car.id} ${arrow}</span><span>${car.load}/${car.capacity}</span>`;
    el.dataset.floor = String(car.floor);
    el.dataset.load = String(car.load);
    el.dataset.capacity = String(car.capacity);
    el.dataset.phase = String(car.phase);
    el.title = `${car.id}: floor ${car.floor}, ${car.phase}, stops ${car.stops.join(", ") || "none"}`;
  });

  renderQueues(snapshot.queues || {});
  renderCalls(snapshot.calls || []);
  renderDecision(snapshot.decision_tail || []);
  renderEvents(snapshot.event_tail || []);
  requestAnimationFrame(() => drawAssignmentLinks(snapshot.calls || []));

  const chartHistory = replay ? historyFromReplay(Number(options.replayIndex || 0)) : snapshot.history || [];
  drawChart(chartHistory);
}

function renderQueues(queues) {
  document.querySelectorAll(".queue-badge").forEach((node) => node.remove());
  let total = 0;
  let maximum = 0;
  const counts = {};
  for (let floor = 1; floor <= FLOOR_COUNT; floor += 1) {
    const queue = queues[String(floor)] || { up: 0, down: 0 };
    const count = Number(queue.up || 0) + Number(queue.down || 0);
    counts[String(floor)] = count;
    total += count;
    maximum = Math.max(maximum, count);
    if (!count) continue;
    const badge = document.createElement("div");
    badge.className = "queue-badge";
    badge.dataset.floor = String(floor);
    badge.style.bottom = `calc(${floorBottomPercent(floor)}% - 7px)`;
    badge.innerHTML = `<b>↑ ${queue.up || 0}</b><b class="down">↓ ${queue.down || 0}</b>`;
    floors.appendChild(badge);
  }
  document.querySelector("#heatmap-total").textContent = `${total} waiting`;
  for (let floor = 1; floor <= FLOOR_COUNT; floor += 1) {
    const cell = heatmapElements.get(String(floor));
    const count = counts[String(floor)] || 0;
    const ratio = maximum ? count / maximum : 0;
    cell.dataset.queue = String(count);
    cell.style.setProperty("--heat", String(ratio));
    cell.querySelector("strong").textContent = String(count);
  }
}

function renderCalls(calls) {
  const target = document.querySelector("#calls");
  if (!calls.length) {
    target.innerHTML = `<span class="muted">No active hall calls.</span>`;
    return;
  }
  target.innerHTML = calls
    .slice()
    .sort((a, b) => b.wait - a.wait)
    .slice(0, 12)
    .map((call) => {
      const destination = call.destination ? ` → ${call.destination}F` : "";
      const score = call.assigned_score == null ? "" : ` · ${Number(call.assigned_score).toFixed(1)}`;
      return `<span class="call" data-floor="${call.floor}" data-assigned="${call.assigned || ""}"><b>${call.floor}F ${call.direction > 0 ? "↑" : "↓"}${destination}</b><span>${call.assigned || "unassigned"}${score}</span><span class="wait">${Number(call.wait).toFixed(0)}s</span>${call.missed ? `<span class="miss">miss ${call.missed}</span>` : ""}</span>`;
    })
    .join("");
}

function renderDecision(decisions) {
  const latest = decisions.at(-1);
  const reason = document.querySelector("#decision-reason");
  const candidates = document.querySelector("#decision-candidates");
  document.querySelector("#decision-policy").textContent = controls.policy.options[controls.policy.selectedIndex]?.text || controls.policy.value;
  if (!latest) {
    reason.textContent = "Waiting for the first dispatch decision…";
    document.querySelector("#decision-call").textContent = "No active decision";
    document.querySelector("#decision-queue").textContent = "queue 0";
    candidates.innerHTML = `<tr><td colspan="5" class="muted">No candidate scores yet.</td></tr>`;
    return;
  }
  reason.textContent = latest.reason || "Decision reason unavailable";
  const destination = latest.destination ? ` → ${latest.destination}F` : "";
  document.querySelector("#decision-call").textContent = `${latest.floor}F ${latest.direction > 0 ? "↑" : "↓"}${destination} · ${latest.bank}`;
  document.querySelector("#decision-queue").textContent = `queue ${latest.queue_size || 0}`;
  const rows = latest.candidates || latest.evaluations || [];
  if (!rows.length) {
    candidates.innerHTML = `<tr><td colspan="5" class="muted">No compatible candidates.</td></tr>`;
    return;
  }
  candidates.innerHTML = rows
    .slice()
    .sort((a, b) => Number(a.score) - Number(b.score))
    .map((item) => {
      const chosen = item.elevator_id === latest.chosen_elevator_id;
      return `<tr class="${chosen ? "chosen" : ""}"><td>${item.elevator_id}${chosen ? " ✓" : ""}</td><td>${Number(item.pickup_eta ?? item.eta ?? 0).toFixed(1)}s</td><td>${item.residual_capacity ?? "—"}</td><td>${Number(item.score ?? 0).toFixed(1)}</td><td>${item.feasible === false ? "no" : "yes"}</td></tr>`;
    })
    .join("");
}

function renderEvents(events) {
  const target = document.querySelector("#event-stream");
  const relevant = events
    .filter((event) => ["assign", "reassign", "assignment_invalidated", "full_pass"].includes(event.kind))
    .slice(-8)
    .reverse();
  if (!relevant.length) {
    target.innerHTML = `<span class="muted">No dispatch events yet.</span>`;
    return;
  }
  target.innerHTML = relevant.map((event) => {
    const label = {
      assign: "ASSIGN",
      reassign: "REASSIGN",
      assignment_invalidated: "INVALIDATE",
      full_pass: "FULL PASS",
    }[event.kind];
    const reason = event.details?.reason || event.details?.decision_reason || "";
    return `<article class="event event-${event.kind}"><time>T+${Number(event.sim_time).toFixed(1)}s</time><b>${label}</b><span>${event.floor || "—"}F · ${event.elevator_id || "—"}</span>${reason ? `<small>${escapeHtml(reason)}</small>` : ""}</article>`;
  }).join("");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function drawAssignmentLinks(calls) {
  const building = document.querySelector("#building");
  const rect = building.getBoundingClientRect();
  assignmentOverlay.setAttribute("viewBox", `0 0 ${rect.width} ${rect.height}`);
  assignmentOverlay.innerHTML = "";
  calls.filter((call) => call.assigned && carElements.has(call.assigned)).slice(0, 16).forEach((call) => {
    const carRect = carElements.get(call.assigned).getBoundingClientRect();
    const x1 = 105;
    const y1 = rect.height - (floorBottomPercent(Number(call.floor)) / 100) * rect.height;
    const x2 = carRect.left - rect.left + carRect.width / 2;
    const y2 = carRect.top - rect.top + carRect.height / 2;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", x1);
    line.setAttribute("y1", y1);
    line.setAttribute("x2", x2);
    line.setAttribute("y2", y2);
    line.setAttribute("class", call.bank === "low" ? "link-low" : "link-high");
    assignmentOverlay.appendChild(line);
    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", x1);
    dot.setAttribute("cy", y1);
    dot.setAttribute("r", 3);
    dot.setAttribute("class", call.bank === "low" ? "link-low" : "link-high");
    assignmentOverlay.appendChild(dot);
  });
}

function drawChart(history) {
  const canvas = document.querySelector("#wait-chart");
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(300, Math.round(rect.width * ratio));
  const height = Math.max(140, Math.round(rect.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, width, height);
  const pad = 22 * ratio;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  const values = history.flatMap((point) => [Number(point.avg_wait), Number(point.p95_wait)]);
  const max = Math.max(20, ...values) * 1.12;
  ctx.strokeStyle = "rgba(150,180,200,.12)";
  ctx.lineWidth = ratio;
  for (let i = 0; i <= 4; i += 1) {
    const y = pad + (plotH * i) / 4;
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(width - pad, y); ctx.stroke();
  }
  if (history.length < 2) return;
  const line = (field, color) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2 * ratio;
    ctx.beginPath();
    history.forEach((point, index) => {
      const x = pad + (index / (history.length - 1)) * plotW;
      const y = pad + plotH - (Number(point[field]) / max) * plotH;
      if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  };
  line("avg_wait", "#4dd7d1");
  line("p95_wait", "#f1b86a");
}

async function sendControl(action) {
  const response = await fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action,
      scenario: controls.scenario.value,
      policy: controls.policy.value,
      control_mode: controls.controlMode.value,
      speed: Number(controls.speed.value),
    }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "control request failed");
  if (displayMode === "live") render(payload);
  return payload;
}

function setSimulationControlsDisabled(disabled) {
  [controls.scenario, controls.policy, controls.controlMode, controls.speed, controls.pause, controls.reset]
    .forEach((element) => { element.disabled = disabled; });
}

async function saveReplay() {
  const response = await fetch("/api/replay", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "save" }),
  });
  savedReplay = await response.json();
  replayControls.enter.disabled = !savedReplay.frames?.length;
  replayControls.slider.max = String(Math.max(0, (savedReplay.frames?.length || 1) - 1));
  replayControls.slider.value = replayControls.slider.max;
  document.querySelector("#replay-count").textContent = String(savedReplay.frame_count || 0);
  document.querySelector("#replay-scenario").textContent = savedReplay.scenario || "—";
  document.querySelector("#replay-policy").textContent = savedReplay.policy || "—";
  replayControls.status.textContent = "saved run";
  updateReplayMeta(Number(replayControls.slider.value));
}

async function enterReplay() {
  if (!savedReplay?.frames?.length) return;
  if (latestLiveSnapshot?.running) await sendControl("pause");
  displayMode = "replay";
  setSimulationControlsDisabled(true);
  replayControls.live.disabled = false;
  replayControls.enter.disabled = true;
  replayControls.slider.disabled = false;
  replayControls.status.textContent = "replay mode";
  renderReplayFrame(Number(replayControls.slider.value));
}

function returnLive() {
  displayMode = "live";
  setSimulationControlsDisabled(false);
  replayControls.live.disabled = true;
  replayControls.enter.disabled = !savedReplay?.frames?.length;
  replayControls.slider.disabled = true;
  replayControls.status.textContent = savedReplay ? "saved run" : "live buffer";
  if (latestLiveSnapshot) render(latestLiveSnapshot);
}

function renderReplayFrame(index) {
  if (!savedReplay?.frames?.length) return;
  const bounded = Math.max(0, Math.min(index, savedReplay.frames.length - 1));
  replayControls.slider.value = String(bounded);
  const frame = {
    ...savedReplay.frames[bounded],
    running: false,
    speed: 0,
    history: historyFromReplay(bounded),
  };
  render(frame, { replay: true, replayIndex: bounded });
  updateReplayMeta(bounded);
}

function updateReplayMeta(index) {
  if (!savedReplay?.frames?.length) return;
  const frame = savedReplay.frames[index];
  document.querySelector("#replay-frame").textContent = `Frame ${index + 1} / ${savedReplay.frames.length}`;
  document.querySelector("#replay-clock").textContent = frame?.clock || "—";
}

function populateEvidence() {
  if (!experimentPayload?.baseline?.scenarios) return;
  const select = document.querySelector("#evidence-scenario");
  const preferred = ["morning", "lunch", "normal", "evening", "shock", "mixed_day"];
  select.innerHTML = preferred
    .filter((name) => experimentPayload.baseline.scenarios[name])
    .map((name) => `<option value="${name}">${name.replace("_", " ")}</option>`)
    .join("");
  select.value = "lunch";
  renderEvidenceScenario(select.value);
}

function renderEvidenceScenario(scenarioName) {
  const scenario = experimentPayload?.baseline?.scenarios?.[scenarioName];
  if (!scenario) return;
  const target = document.querySelector("#comparison-cards");
  const policyOrder = ["legacy_sticky", "nearest_car", "collective", "queue_aware", "capr"];
  target.innerHTML = policyOrder.map((name) => {
    const item = scenario.policies[name];
    const classification = item.guardrail_classification;
    const className = classification === "candidate_improvement" ? "good" : classification === "reference" ? "reference" : classification.includes("tradeoff") ? "tradeoff" : "neutral";
    return `<article class="comparison-card ${className}" data-policy="${name}"><div><span>${name.replaceAll("_", " ")}</span><b>${classification.replaceAll("_", " ")}</b></div><strong>${Number(item.avg_wait).toFixed(2)}s</strong><small>avg wait</small><dl><div><dt>P95</dt><dd>${Number(item.p95_wait).toFixed(2)}s</dd></div><div><dt>Energy proxy</dt><dd>${Number(item.energy_proxy).toFixed(0)}</dd></div></dl></article>`;
  }).join("");
  const capr = scenario.policies.capr;
  const collective = scenario.policies.collective;
  const delta = Number(capr.avg_wait) - Number(collective.avg_wait);
  const note = document.querySelector("#comparison-note");
  note.innerHTML = `<b>CAPR vs collective:</b> ${delta < 0 ? "lower" : "higher"} mean wait by ${Math.abs(delta).toFixed(2)}s. <span>${capr.guardrail_classification.replaceAll("_", " ")}.</span>`;
}

async function loadEvidence() {
  const response = await fetch("/api/experiment", { cache: "no-store" });
  if (!response.ok) return;
  experimentPayload = await response.json();
  populateEvidence();
}

async function refresh() {
  if (displayMode !== "live") return;
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store" });
    if (response.ok) render(await response.json());
  } catch (error) {
    console.error(error);
  }
}

controls.scenario.addEventListener("change", () => sendControl("reset"));
controls.policy.addEventListener("change", () => sendControl("reset"));
controls.controlMode.addEventListener("change", () => sendControl("reset"));
controls.speed.addEventListener("change", () => sendControl("update"));
controls.reset.addEventListener("click", () => sendControl("reset"));
controls.pause.addEventListener("click", async () => {
  const action = controls.pause.textContent === "Pause" ? "pause" : "start";
  await sendControl(action);
});
replayControls.save.addEventListener("click", saveReplay);
replayControls.enter.addEventListener("click", enterReplay);
replayControls.live.addEventListener("click", returnLive);
replayControls.slider.addEventListener("input", () => renderReplayFrame(Number(replayControls.slider.value)));
document.querySelector("#evidence-scenario").addEventListener("change", (event) => renderEvidenceScenario(event.target.value));
window.addEventListener("resize", () => {
  if (displayMode === "live" && latestLiveSnapshot) drawAssignmentLinks(latestLiveSnapshot.calls || []);
  else if (displayMode === "replay" && savedReplay) drawAssignmentLinks(savedReplay.frames[Number(replayControls.slider.value)]?.calls || []);
});

buildBuilding();
refresh();
loadEvidence();
setInterval(refresh, 300);
