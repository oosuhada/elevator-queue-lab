const heatmapArea = document.querySelector(".heatmap-area");
const trend = document.createElement("div");
trend.className = "queue-trend";
trend.innerHTML = `
  <div class="queue-trend-title"><span>QUEUE TIME SERIES · Lq</span><strong id="queue-trend-value">0.00</strong></div>
  <canvas id="queue-trend-chart" width="320" height="88" aria-label="Average queue over simulation time"></canvas>
`;
heatmapArea.appendChild(trend);

const style = document.createElement("style");
style.textContent = `
  .queue-trend { margin-top: 9px; padding-top: 8px; border-top: 1px solid rgba(157,186,207,.1); }
  .queue-trend-title { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:4px; color:#6e8899; font-size:7px; font-weight:800; letter-spacing:.08em; }
  .queue-trend-title strong { color:#8ecfd2; font-size:9px; font-variant-numeric:tabular-nums; }
  #queue-trend-chart { display:block; width:100%; height:50px; border-radius:5px; background:rgba(5,14,21,.5); }
`;
document.head.appendChild(style);

let replayCache = null;

function drawQueueTrend(points) {
  const canvas = document.querySelector("#queue-trend-chart");
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(160, Math.round(rect.width * ratio));
  const height = Math.max(50, Math.round(rect.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, width, height);
  const values = points.map((point) => Number(point.avg_queue || 0));
  const current = values.at(-1) || 0;
  document.querySelector("#queue-trend-value").textContent = current.toFixed(2);
  if (values.length < 2) return;

  const pad = 7 * ratio;
  const plotWidth = width - pad * 2;
  const plotHeight = height - pad * 2;
  const maximum = Math.max(1, ...values) * 1.12;
  ctx.strokeStyle = "rgba(150,180,200,.10)";
  ctx.lineWidth = ratio;
  for (let index = 0; index <= 2; index += 1) {
    const y = pad + (plotHeight * index) / 2;
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(width - pad, y); ctx.stroke();
  }
  ctx.strokeStyle = "#6ca9ff";
  ctx.lineWidth = 1.6 * ratio;
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = pad + (index / (values.length - 1)) * plotWidth;
    const y = pad + plotHeight - (value / maximum) * plotHeight;
    if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

async function refreshLiveTrend() {
  if (document.querySelector("#live-state span")?.textContent === "REPLAY MODE") return;
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store" });
    if (!response.ok) return;
    const snapshot = await response.json();
    drawQueueTrend(snapshot.history || []);
  } catch (error) {
    console.error(error);
  }
}

async function drawReplayTrend() {
  try {
    if (!replayCache) {
      const response = await fetch("/api/replay", { cache: "no-store" });
      if (!response.ok) return;
      replayCache = await response.json();
    }
    const slider = document.querySelector("#replay-slider");
    const index = Number(slider.value || 0);
    const points = (replayCache.frames || [])
      .slice(0, index + 1)
      .filter((frame) => Number(frame.sim_time) % 15 === 0)
      .map((frame) => ({ avg_queue: frame.metrics.avg_queue }));
    drawQueueTrend(points);
  } catch (error) {
    console.error(error);
  }
}

document.querySelector("#save-replay")?.addEventListener("click", () => { replayCache = null; });
document.querySelector("#enter-replay")?.addEventListener("click", () => setTimeout(drawReplayTrend, 0));
document.querySelector("#replay-slider")?.addEventListener("input", drawReplayTrend);
document.querySelector("#return-live")?.addEventListener("click", () => setTimeout(refreshLiveTrend, 0));
window.addEventListener("resize", () => {
  if (document.querySelector("#live-state span")?.textContent === "REPLAY MODE") drawReplayTrend();
  else refreshLiveTrend();
});

refreshLiveTrend();
setInterval(refreshLiveTrend, 1000);
