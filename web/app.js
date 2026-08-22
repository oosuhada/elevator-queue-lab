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
let theoryPayload = null;

const EVIDENCE_POLICIES = ["legacy_sticky", "nearest_car", "collective", "queue_aware", "capr"];
const POLICY_LABELS = {
  legacy_sticky: "Legacy sticky",
  nearest_car: "Nearest car",
  collective: "Collective",
  queue_aware: "Queue-aware",
  capr: "CAPR",
};
const GUARDRAIL_PRIORITY = {
  candidate_improvement: 0,
  reference: 1,
  mean_improves_with_guardrail_tradeoff: 2,
  no_mean_improvement: 3,
};

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

function evidenceLabel(classification) {
  return ({
    candidate_improvement: "clean candidate",
    reference: "collective reference",
    mean_improves_with_guardrail_tradeoff: "faster · tradeoff",
    no_mean_improvement: "no mean gain",
  })[classification] || classification.replaceAll("_", " ");
}

function evidenceClassName(classification) {
  if (classification === "candidate_improvement") return "good";
  if (classification === "reference") return "reference";
  if (classification.includes("tradeoff")) return "tradeoff";
  return "neutral";
}

function rankedPolicies(scenario) {
  const entries = EVIDENCE_POLICIES
    .filter((name) => scenario.policies[name])
    .map((name) => ({ name, ...scenario.policies[name] }));
  const speedOrder = [...entries].sort((a, b) =>
    Number(a.avg_wait) - Number(b.avg_wait)
      || Number(a.p95_wait) - Number(b.p95_wait)
      || Number(a.energy_proxy) - Number(b.energy_proxy));
  const speedRanks = new Map(speedOrder.map((item, index) => [item.name, index + 1]));
  return entries
    .sort((a, b) =>
      (GUARDRAIL_PRIORITY[a.guardrail_classification] ?? 99) - (GUARDRAIL_PRIORITY[b.guardrail_classification] ?? 99)
        || Number(a.avg_wait) - Number(b.avg_wait)
        || Number(a.p95_wait) - Number(b.p95_wait)
        || Number(a.energy_proxy) - Number(b.energy_proxy))
    .map((item, index) => ({ ...item, decisionRank: index + 1, speedRank: speedRanks.get(item.name) }));
}

function signedSeconds(value) {
  const numeric = Number(value || 0);
  if (Math.abs(numeric) < 0.005) return "±0.00s";
  return `${numeric > 0 ? "+" : "−"}${Math.abs(numeric).toFixed(2)}s`;
}

function renderPolicyLeaders(ranked) {
  const leader = ranked[0];
  const fastest = [...ranked].sort((a, b) => a.speedRank - b.speedRank)[0];
  const cleanCandidates = ranked.filter((item) => item.guardrail_classification === "candidate_improvement");
  const target = document.querySelector("#policy-leaders");
  target.innerHTML = `
    <article class="policy-leader primary">
      <span>Guardrail-aware #1</span>
      <strong>${POLICY_LABELS[leader.name]}</strong>
      <small>${evidenceLabel(leader.guardrail_classification)} · ${Number(leader.avg_wait).toFixed(2)}s AWT</small>
    </article>
    <article class="policy-leader">
      <span>Fastest mean wait</span>
      <strong>${POLICY_LABELS[fastest.name]}</strong>
      <small>#${fastest.speedRank} speed · ${Number(fastest.avg_wait).toFixed(2)}s${fastest.name === leader.name ? " · same leader" : ` · ${evidenceLabel(fastest.guardrail_classification)}`}</small>
    </article>
    <article class="policy-leader">
      <span>Clean candidates</span>
      <strong>${cleanCandidates.length}</strong>
      <small>${cleanCandidates.length ? cleanCandidates.map((item) => POLICY_LABELS[item.name]).join(" · ") : "Collective remains the guardrail-safe reference"}</small>
    </article>`;
}

function sampleStandardDeviation(values) {
  if (values.length < 2) return 0;
  const center = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance = values.reduce((sum, value) => sum + (value - center) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
}

function gaussianKernelDensity(values, x, bandwidth) {
  if (!values.length || bandwidth <= 0) return 0;
  const normalizer = values.length * bandwidth * Math.sqrt(2 * Math.PI);
  return values.reduce((sum, value) => {
    const z = (x - value) / bandwidth;
    return sum + Math.exp(-0.5 * z * z);
  }, 0) / normalizer;
}

function renderPolicyDensity(ranked) {
  const svg = document.querySelector("#policy-density-chart");
  const legend = document.querySelector("#policy-density-legend");
  const series = ranked
    .map((item) => ({ ...item, values: (item.avg_wait_seed_values || []).map(Number).filter(Number.isFinite) }))
    .filter((item) => item.values.length);
  if (!series.length) {
    svg.innerHTML = '<text x="380" y="140" text-anchor="middle" class="density-empty">Seed-level distribution evidence unavailable</text>';
    legend.innerHTML = "";
    return;
  }

  const allValues = series.flatMap((item) => item.values);
  const observedMin = Math.min(...allValues);
  const observedMax = Math.max(...allValues);
  const observedSpan = Math.max(1, observedMax - observedMin);
  const domainMin = Math.max(0, observedMin - observedSpan * 0.08);
  const domainMax = observedMax + observedSpan * 0.08;
  const width = 760;
  const height = 280;
  const left = 48;
  const right = 18;
  const top = 15;
  const bottom = 44;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const xScale = (value) => left + ((value - domainMin) / (domainMax - domainMin)) * plotWidth;

  const samples = 110;
  const curves = series.map((item) => {
    const spread = sampleStandardDeviation(item.values);
    const bandwidth = Math.max(observedSpan / 45, 1.06 * Math.max(spread, observedSpan / 30) * item.values.length ** -0.2);
    const points = Array.from({ length: samples + 1 }, (_, index) => {
      const x = domainMin + (index / samples) * (domainMax - domainMin);
      return [x, gaussianKernelDensity(item.values, x, bandwidth)];
    });
    return { ...item, points };
  });
  const maxDensity = Math.max(...curves.flatMap((curve) => curve.points.map(([, density]) => density)), 0.0001);
  const yScale = (density) => top + plotHeight - (density / maxDensity) * plotHeight * 0.92;
  const baselineY = top + plotHeight;
  const ticks = Array.from({ length: 6 }, (_, index) => domainMin + (index / 5) * (domainMax - domainMin));

  const grid = ticks.map((tick) => {
    const x = xScale(tick);
    return `<g class="density-grid"><line x1="${x.toFixed(2)}" y1="${top}" x2="${x.toFixed(2)}" y2="${baselineY}"/><text x="${x.toFixed(2)}" y="${height - 18}" text-anchor="middle">${tick.toFixed(1)}s</text></g>`;
  }).join("");

  const paths = curves.map((curve) => {
    const linePath = curve.points.map(([x, density], index) => `${index ? "L" : "M"}${xScale(x).toFixed(2)},${yScale(density).toFixed(2)}`).join(" ");
    const areaPath = `M${xScale(curve.points[0][0]).toFixed(2)},${baselineY} ${curve.points.map(([x, density]) => `L${xScale(x).toFixed(2)},${yScale(density).toFixed(2)}`).join(" ")} L${xScale(curve.points.at(-1)[0]).toFixed(2)},${baselineY} Z`;
    const meanX = xScale(Number(curve.avg_wait));
    const meanDensity = gaussianKernelDensity(curve.values, Number(curve.avg_wait), Math.max(observedSpan / 45, 1.06 * Math.max(sampleStandardDeviation(curve.values), observedSpan / 30) * curve.values.length ** -0.2));
    return `<g class="density-series density-${curve.name}" data-policy="${curve.name}"><path class="density-area" d="${areaPath}"/><path class="density-line" d="${linePath}"/><circle class="density-mean" cx="${meanX.toFixed(2)}" cy="${yScale(meanDensity).toFixed(2)}" r="3.4"/></g>`;
  }).join("");

  svg.innerHTML = `${grid}<line class="density-axis" x1="${left}" y1="${baselineY}" x2="${width - right}" y2="${baselineY}"/>${paths}<text class="density-axis-label" x="${width - right}" y="${height - 2}" text-anchor="end">per-seed average wait (seconds) → lower is better</text>`;
  legend.innerHTML = ranked.map((item) => `<span><i class="density-swatch density-${item.name}"></i><b>#${item.decisionRank}</b>${POLICY_LABELS[item.name]}</span>`).join("");
}

function renderPolicyRanking(ranked) {
  const target = document.querySelector("#policy-ranking-body");
  target.innerHTML = ranked.map((item) => {
    const ci = Number(item.avg_wait_ci95_halfwidth || 0);
    const evidenceClass = evidenceClassName(item.guardrail_classification);
    return `<tr class="rank-${evidenceClass}" data-policy="${item.name}">
      <td><strong class="decision-rank">#${item.decisionRank}</strong></td>
      <td><strong>${POLICY_LABELS[item.name]}</strong></td>
      <td><span class="evidence-pill ${evidenceClass}">${evidenceLabel(item.guardrail_classification)}</span></td>
      <td><b>${Number(item.avg_wait).toFixed(2)}s</b><small>±${ci.toFixed(2)}s</small></td>
      <td>${Number(item.p95_wait).toFixed(2)}s</td>
      <td>${Number(item.p99_wait || 0).toFixed(2)}s</td>
      <td>${Number(item.worst_floor_mean_wait || 0).toFixed(2)}s</td>
      <td>${Number(item.energy_proxy).toFixed(0)}</td>
      <td class="delta ${Number(item.avg_wait_delta_vs_collective || 0) < 0 ? "better" : Number(item.avg_wait_delta_vs_collective || 0) > 0 ? "worse" : ""}">${signedSeconds(item.avg_wait_delta_vs_collective)}</td>
      <td>#${item.speedRank}</td>
    </tr>`;
  }).join("");
}

function renderEvidenceScenario(scenarioName) {
  const scenario = experimentPayload?.baseline?.scenarios?.[scenarioName];
  if (!scenario) return;
  const ranked = rankedPolicies(scenario);
  renderPolicyLeaders(ranked);
  const target = document.querySelector("#comparison-cards");
  target.innerHTML = ranked.map((rankedItem) => {
    const name = rankedItem.name;
    const item = scenario.policies[name];
    const classification = item.guardrail_classification;
    const className = evidenceClassName(classification);
    return `<article class="comparison-card ${className}" data-policy="${name}"><div class="comparison-card-head"><div><span>${POLICY_LABELS[name]}</span><b>${evidenceLabel(classification)}</b></div><i>#${rankedItem.decisionRank}</i></div><strong>${Number(item.avg_wait).toFixed(2)}s</strong><small>avg wait · speed rank #${rankedItem.speedRank}</small><dl><div><dt>95% CI</dt><dd>±${Number(item.avg_wait_ci95_halfwidth || 0).toFixed(2)}s</dd></div><div><dt>P95</dt><dd>${Number(item.p95_wait).toFixed(2)}s</dd></div><div><dt>Energy proxy</dt><dd>${Number(item.energy_proxy).toFixed(0)}</dd></div></dl></article>`;
  }).join("");
  renderPolicyDensity(ranked);
  renderPolicyRanking(ranked);
  const capr = scenario.policies.capr;
  const collective = scenario.policies.collective;
  const delta = Number(capr.avg_wait) - Number(collective.avg_wait);
  const note = document.querySelector("#comparison-note");
  const leader = ranked[0];
  const fastest = [...ranked].sort((a, b) => a.speedRank - b.speedRank)[0];
  note.innerHTML = `<b>Scenario readout:</b> ${POLICY_LABELS[leader.name]} is the guardrail-aware leader; ${POLICY_LABELS[fastest.name]} is fastest by mean AWT. <span>CAPR is ${delta < 0 ? "lower" : "higher"} than collective by ${Math.abs(delta).toFixed(2)}s and is classified “${evidenceLabel(capr.guardrail_classification)}”. Ranking is scenario-specific, not a claim of global superiority.</span>`;
}

async function loadEvidence() {
  const response = await fetch("/api/experiment", { cache: "no-store" });
  if (!response.ok) return;
  experimentPayload = await response.json();
  populateEvidence();
}

function theoryPhaseLabel(bidirectionalLoad) {
  if (bidirectionalLoad < 4) return "static / churn";
  if (bidirectionalLoad < 12) return "transition";
  return "predictive value";
}

function renderTheory() {
  const discovery = theoryPayload?.discovery;
  const validation = theoryPayload?.validation;
  if (!discovery?.theory || !validation?.result) return;
  const theory = discovery.theory;
  const result = validation.result;
  const threshold = Number(theory.best_single_threshold?.threshold || 0);
  const linear = theory.linear_wait_delta_fit || {};
  const heldoutLinear = result.frozen_linear_effect_model || {};
  const gated = result.gated_policy_projection || {};

  const leaders = document.querySelector("#theory-leaders");
  leaders.innerHTML = `
    <article class="theory-leader primary">
      <span>Discovery relationship</span>
      <strong>r = ${Number(theory.pearson_bidirectional_load_rate_vs_capr_wait_delta).toFixed(2)}</strong>
      <small>higher B tracks lower CAPR − static average wait</small>
    </article>
    <article class="theory-leader">
      <span>High-effect trigger</span>
      <strong>B ≈ ${threshold.toFixed(2)}</strong>
      <small>${Number(theory.best_single_threshold.accuracy * 100).toFixed(1)}% discovery classification</small>
    </article>
    <article class="theory-leader">
      <span>Held-out falsification</span>
      <strong>${Number(result.accuracy * 100).toFixed(1)}%</strong>
      <small>${result.correct_cells}/${result.total_cells} unseen cells · recall ${Number(result.recall * 100).toFixed(0)}%</small>
    </article>
    <article class="theory-leader">
      <span>B-gated control projection</span>
      <strong>${Number((gated.wait_gain_retained_vs_always_on_capr || 0) * 100).toFixed(0)}% wait gain</strong>
      <small>${Number((gated.energy_overhead_reduction_vs_always_on_capr || 0) * 100).toFixed(0)}% less added energy · active ${gated.active_cells || 0}/${gated.total_cells || 0}</small>
    </article>`;

  renderTheoryScatter(discovery, validation);
  renderTheoryPhases(theory);
  renderCanonicalTheory(threshold);

  const rule = document.querySelector("#theory-rule");
  rule.innerHTML = `<span>Empirical effect law</span><strong>ΔAWT ≈ ${Number(linear.intercept_seconds).toFixed(3)} ${Number(linear.slope_seconds_per_bidirectional_pax_per_min) < 0 ? "−" : "+"} ${Math.abs(Number(linear.slope_seconds_per_bidirectional_pax_per_min)).toFixed(3)} · B</strong><small>CAPR minus CAPR-static · seconds · discovery R² ${Number(linear.r_squared).toFixed(2)}</small>`;

  const caveat = document.querySelector("#theory-caveat");
  caveat.innerHTML = `<b>What survived falsification:</b> B is useful as a continuous effect predictor (held-out r=${Number(heldoutLinear.correlation_observed_vs_predicted || 0).toFixed(2)}, MAE ${Number(heldoutLinear.mae_seconds || 0).toFixed(2)}s) and a high-recall screening variable, but B≈${threshold.toFixed(2)} is not a hard universal critical constant. The held-out grid produced ${result.confusion?.false_positive ?? 0} threshold false positives and ${result.confusion?.false_negative ?? 0} false negatives; ${result.all_threshold_positive_cells_have_negative_mean_delta ? "every threshold-positive held-out cell still moved mean AWT in the beneficial direction, but several confidence intervals crossed zero." : "some threshold-positive cells did not even improve the mean."} Treat this as a fuzzy phase transition to test on other buildings, capacities and traffic mixes.`;
}

function renderTheoryScatter(discovery, validation) {
  const svg = document.querySelector("#theory-scatter");
  const discoveryCells = discovery.cells || [];
  const validationCells = validation.cells || [];
  const allCells = [...discoveryCells, ...validationCells];
  if (!allCells.length) return;
  const points = allCells.map((cell) => ({
    x: Number(cell.demand.bidirectional_load_rate),
    y: Number(cell.capr_vs_static.metrics.avg_wait.delta_mean),
  }));
  const width = 820;
  const height = 340;
  const left = 58;
  const right = 22;
  const top = 18;
  const bottom = 48;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const xMax = Math.max(30, ...points.map((point) => point.x)) * 1.03;
  const observedMin = Math.min(...points.map((point) => point.y));
  const observedMax = Math.max(...points.map((point) => point.y));
  const yMin = Math.min(-7, observedMin - 0.5);
  const yMax = Math.max(4, observedMax + 0.5);
  const xScale = (x) => left + (x / xMax) * plotWidth;
  const yScale = (y) => top + ((yMax - y) / (yMax - yMin)) * plotHeight;
  const xTicks = [0, 4, 8, 12, 16, 20, 24, 28].filter((value) => value <= xMax);
  const yTicks = [-6, -4, -2, 0, 2, 4].filter((value) => value >= yMin && value <= yMax);
  const grid = [
    ...xTicks.map((tick) => `<g class="theory-gridline"><line x1="${xScale(tick)}" y1="${top}" x2="${xScale(tick)}" y2="${height - bottom}"/><text x="${xScale(tick)}" y="${height - 20}" text-anchor="middle">${tick}</text></g>`),
    ...yTicks.map((tick) => `<g class="theory-gridline"><line x1="${left}" y1="${yScale(tick)}" x2="${width - right}" y2="${yScale(tick)}"/><text x="${left - 9}" y="${yScale(tick) + 3}" text-anchor="end">${tick > 0 ? "+" : ""}${tick}s</text></g>`),
  ].join("");

  const threshold = Number(discovery.theory.best_single_threshold.threshold);
  const fit = discovery.theory.linear_wait_delta_fit;
  const fitY = (x) => Number(fit.intercept_seconds) + Number(fit.slope_seconds_per_bidirectional_pax_per_min) * x;
  const regression = `<line class="theory-fit" x1="${xScale(0)}" y1="${yScale(fitY(0))}" x2="${xScale(xMax)}" y2="${yScale(fitY(xMax))}"/>`;
  const zero = `<line class="theory-zero" x1="${left}" y1="${yScale(0)}" x2="${width - right}" y2="${yScale(0)}"/>`;
  const thresholdLine = `<g class="theory-threshold"><line x1="${xScale(threshold)}" y1="${top}" x2="${xScale(threshold)}" y2="${height - bottom}"/><text x="${xScale(threshold) + 6}" y="${top + 13}">high-effect trigger ≈ ${threshold.toFixed(2)}</text></g>`;

  const discoveryMarks = discoveryCells.map((cell) => {
    const x = xScale(Number(cell.demand.bidirectional_load_rate));
    const y = yScale(Number(cell.capr_vs_static.metrics.avg_wait.delta_mean));
    const supported = Boolean(cell.capr_vs_static.supported_wait_gain);
    const loss = Boolean(cell.capr_vs_static.supported_wait_loss);
    const state = supported ? "gain" : loss ? "loss" : "uncertain";
    return `<circle class="theory-point discovery ${state}" data-kind="discovery" cx="${x}" cy="${y}" r="4.1"><title>discovery · λ ${cell.demand.arrivals_per_minute}/min · p↑ ${cell.demand.lobby_up_probability} · B ${cell.demand.bidirectional_load_rate} · ΔAWT ${Number(cell.capr_vs_static.metrics.avg_wait.delta_mean).toFixed(2)}s</title></circle>`;
  }).join("");
  const validationMarks = validationCells.map((cell) => {
    const x = xScale(Number(cell.demand.bidirectional_load_rate));
    const y = yScale(Number(cell.capr_vs_static.metrics.avg_wait.delta_mean));
    const supported = Boolean(cell.capr_vs_static.supported_wait_gain);
    const size = 4.8;
    return `<rect class="theory-point validation ${supported ? "gain" : "uncertain"}" data-kind="validation" x="${x - size}" y="${y - size}" width="${size * 2}" height="${size * 2}" transform="rotate(45 ${x} ${y})"><title>held-out · λ ${cell.demand.arrivals_per_minute}/min · p↑ ${cell.demand.lobby_up_probability} · B ${cell.demand.bidirectional_load_rate} · ΔAWT ${Number(cell.capr_vs_static.metrics.avg_wait.delta_mean).toFixed(2)}s</title></rect>`;
  }).join("");
  svg.innerHTML = `${grid}${zero}${regression}${thresholdLine}${discoveryMarks}${validationMarks}<text class="theory-axis-label" x="${width - right}" y="${height - 3}" text-anchor="end">Bidirectional load B (passengers/min) →</text><text class="theory-axis-label" transform="translate(13 ${top}) rotate(-90)" text-anchor="end">Δ average wait · lower is better</text>`;
}

function renderTheoryPhases(theory) {
  const target = document.querySelector("#theory-phase-bins");
  target.innerHTML = (theory.phase_bins || []).map((bin) => {
    const upper = bin.upper == null ? "∞" : Number(bin.upper).toFixed(0);
    const delta = Number(bin.mean_avg_wait_delta_seconds);
    const clean = Number(bin.clean_gain_cells || 0);
    const state = Number(bin.lower) < 4 ? "static" : Number(bin.lower) < 12 ? "transition" : "predictive";
    return `<article class="phase-bin ${state}"><div><span>B ${Number(bin.lower).toFixed(0)}–${upper}</span><b>${state}</b></div><strong>${signedSeconds(delta)}</strong><small>mean ΔAWT · ${clean}/${bin.cells} clean-gain cells · E×${Number(bin.mean_energy_ratio).toFixed(2)}</small></article>`;
  }).join("");
}

function renderCanonicalTheory(threshold) {
  const scenarios = [
    { name: "Morning", lambda: 22, p: 0.97 },
    { name: "Lunch", lambda: 16, p: 0.45 },
    { name: "Normal", lambda: 5, p: 0.35 },
    { name: "Evening", lambda: 22, p: 0.03 },
  ];
  const target = document.querySelector("#canonical-theory-row");
  target.innerHTML = scenarios.map((scenario) => {
    const b = scenario.lambda * 4 * scenario.p * (1 - scenario.p);
    const phase = theoryPhaseLabel(b);
    const relation = b >= threshold ? "above trigger" : "below trigger";
    return `<article><span>${scenario.name}</span><strong>B ${b.toFixed(2)}</strong><small>${phase} · ${relation}</small></article>`;
  }).join("");
}

async function loadTheory() {
  try {
    const response = await fetch("/api/theory", { cache: "no-store" });
    if (!response.ok) return;
    theoryPayload = await response.json();
    renderTheory();
  } catch (error) {
    console.error(error);
  }
}

async function refresh() {
  if (displayMode !== "live") return;
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store" });
    const snapshot = response.ok ? await response.json() : null;
    // A refresh may have started in live mode just before the user enters replay.
    // Re-check the mode after the network await so a late live response cannot
    // overwrite the deterministic replay frame on a public/remote connection.
    if (snapshot && displayMode === "live") render(snapshot);
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
loadTheory();
setInterval(refresh, 300);
