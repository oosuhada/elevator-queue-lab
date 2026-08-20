const FLOOR_COUNT = 18;
const floorLabels = document.querySelector("#floor-labels");
const floors = document.querySelector("#floors");
const shafts = document.querySelector("#shafts");
const controls = {
  scenario: document.querySelector("#scenario"),
  policy: document.querySelector("#policy"),
  speed: document.querySelector("#speed"),
  pause: document.querySelector("#pause"),
  reset: document.querySelector("#reset"),
};

const carElements = new Map();

function floorBottomPercent(floor) {
  return ((floor - 1) / (FLOOR_COUNT - 1)) * 100;
}

function buildBuilding() {
  for (let floor = 1; floor <= FLOOR_COUNT; floor += 1) {
    const label = document.createElement("div");
    label.className = "floor-label";
    label.textContent = `${floor}F`;
    label.style.bottom = `calc(${floorBottomPercent(floor)}% - 4px)`;
    floorLabels.appendChild(label);

    const line = document.createElement("div");
    line.className = `floor-line ${floor === 1 ? "lobby" : ""}`;
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
    car.innerHTML = `<span>${id}</span><span>0/14</span>`;
    shaft.appendChild(car);
    shafts.appendChild(shaft);
    carElements.set(id, car);
  });
}

function fmtSeconds(value) {
  return `${Number(value || 0).toFixed(1)}s`;
}

function render(snapshot) {
  document.querySelector("#clock").textContent = snapshot.clock;
  const minutes = Math.floor(snapshot.sim_time / 60);
  const seconds = snapshot.sim_time % 60;
  document.querySelector("#elapsed").textContent = `T+${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

  const live = document.querySelector("#live-state");
  live.classList.toggle("paused", !snapshot.running);
  live.lastChild.textContent = snapshot.running ? " LIVE SIMULATION" : " PAUSED";
  controls.pause.textContent = snapshot.running ? "Pause" : "Resume";

  const m = snapshot.metrics;
  document.querySelector("#avg-wait").textContent = fmtSeconds(m.avg_wait);
  document.querySelector("#p95-wait").textContent = fmtSeconds(m.p95_wait);
  document.querySelector("#queue").textContent = String(m.current_queue);
  document.querySelector("#avg-queue").textContent = `Lq avg ${Number(m.avg_queue).toFixed(2)}`;
  document.querySelector("#misses").textContent = String(m.missed_capacity);
  document.querySelector("#served").textContent = `${m.served} served`;
  document.querySelector("#lq-observed").textContent = Number(m.avg_queue).toFixed(2);
  document.querySelector("#lq-derived").textContent = Number(m.little_law_lq).toFixed(2);
  document.querySelector("#arrival-rate").textContent = `${Number(m.arrival_rate_per_min).toFixed(1)}/min`;

  snapshot.elevators.forEach((car) => {
    const el = carElements.get(car.id);
    if (!el) return;
    el.style.bottom = `calc(${floorBottomPercent(car.floor)}% - 14px)`;
    el.classList.toggle("full", car.load >= car.capacity);
    const arrow = car.direction > 0 ? "↑" : car.direction < 0 ? "↓" : "·";
    el.innerHTML = `<span>${car.id} ${arrow}</span><span>${car.load}/${car.capacity}</span>`;
    el.title = `${car.id}: floor ${car.floor}, stops ${car.stops.join(", ") || "none"}`;
  });

  document.querySelectorAll(".queue-badge").forEach((node) => node.remove());
  Object.entries(snapshot.queues).forEach(([floor, queue]) => {
    if (!queue.up && !queue.down) return;
    const badge = document.createElement("div");
    badge.className = "queue-badge";
    badge.style.bottom = `calc(${floorBottomPercent(Number(floor))}% - 7px)`;
    badge.innerHTML = `<b>↑ ${queue.up}</b><b class="down">↓ ${queue.down}</b>`;
    floors.appendChild(badge);
  });

  const calls = document.querySelector("#calls");
  if (!snapshot.calls.length) {
    calls.innerHTML = `<span class="muted">No active hall calls.</span>`;
  } else {
    calls.innerHTML = snapshot.calls
      .slice()
      .sort((a, b) => b.wait - a.wait)
      .slice(0, 12)
      .map((call) => `<span class="call"><b>${call.floor}F ${call.direction > 0 ? "↑" : "↓"} · ${call.bank}</b><span>→ ${call.assigned || "unassigned"}</span><span class="wait">${call.wait.toFixed(0)}s</span>${call.missed ? `<span>miss ${call.missed}</span>` : ""}</span>`)
      .join("");
  }
  drawChart(snapshot.history);
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
      speed: Number(controls.speed.value),
    }),
  });
  render(await response.json());
}

controls.scenario.addEventListener("change", () => sendControl("reset"));
controls.policy.addEventListener("change", () => sendControl("reset"));
controls.speed.addEventListener("change", () => sendControl("update"));
controls.reset.addEventListener("click", () => sendControl("reset"));
controls.pause.addEventListener("click", async () => {
  const action = controls.pause.textContent === "Pause" ? "pause" : "start";
  await sendControl(action);
});

async function refresh() {
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store" });
    if (response.ok) render(await response.json());
  } catch (error) {
    console.error(error);
  }
}

buildBuilding();
refresh();
setInterval(refresh, 300);

