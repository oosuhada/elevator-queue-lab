import type { ExperimentPayload, HistoryPoint, PolicyEvidence, Snapshot } from "../../contracts/api";
import { parseChartSpec, type ChartSpec } from "../../contracts/chartSpec";
import { WorkbenchState } from "../common/WorkbenchState";


interface ChartRendererProps {
  spec: ChartSpec | unknown;
  data: unknown;
}

interface Point {
  x: number;
  y: number;
  label?: string;
  detail?: string;
}

const POLICY_ORDER = ["legacy_sticky", "nearest_car", "collective", "queue_aware", "capr"];

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function normalize(value: number, min: number, max: number): number {
  if (max === min) return 0.5;
  return (value - min) / (max - min);
}

function polyline(points: Point[], width = 620, height = 220): string {
  if (!points.length) return "";
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  return points
    .map((point) => {
      const x = 28 + normalize(point.x, xMin, xMax) * (width - 56);
      const y = 18 + (1 - normalize(point.y, yMin, yMax)) * (height - 44);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function ChartFrame({ title, source, children }: { title: string; source: string; children: React.ReactNode }) {
  return (
    <article className="chart-frame">
      <header>
        <strong>{title}</strong>
        <span>{source}</span>
      </header>
      <div className="chart-canvas">{children}</div>
    </article>
  );
}

function TimeSeriesRenderer({ spec, data }: { spec: Extract<ChartSpec, { type: "timeSeries" }>; data: unknown }) {
  const history = Array.isArray(data) ? (data as HistoryPoint[]) : [];
  const width = 620;
  const height = 220;
  if (history.length < 2) {
    return <WorkbenchState kind="empty" title="Not enough time-series samples" />;
  }
  const series = spec.y.map((field) => ({
    field,
    points: history.map((item) => ({ x: Number(item[spec.x as keyof HistoryPoint]), y: Number(item[field as keyof HistoryPoint]) })),
  }));
  return (
    <ChartFrame title={spec.title} source={spec.source}>
      <svg id="wait-chart" className="semantic-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={spec.title}>
        {[0, 1, 2, 3, 4].map((row) => (
          <line key={row} x1="28" x2={width - 28} y1={22 + row * 42} y2={22 + row * 42} className="chart-grid" />
        ))}
        {series.map((entry, index) => (
          <polyline key={entry.field} className={`chart-line chart-line-${index}`} points={polyline(entry.points, width, height)} />
        ))}
      </svg>
      <div className="chart-legend">
        {series.map((entry, index) => <span key={entry.field} className={`legend-key legend-key-${index}`}>{entry.field}</span>)}
      </div>
    </ChartFrame>
  );
}

function evidenceScenario(data: unknown, scenario: string) {
  const payload = data as ExperimentPayload | undefined;
  return payload?.baseline?.scenarios?.[scenario]?.policies ?? {};
}

function evidenceValue(evidence: PolicyEvidence | undefined, metric: string): number {
  const record = evidence as unknown as Record<string, unknown> | undefined;
  return Number(record?.[metric] ?? 0);
}

function PolicyComparisonRenderer({ spec, data }: { spec: Extract<ChartSpec, { type: "policyComparison" }>; data: unknown }) {
  const policies = evidenceScenario(data, spec.scenario);
  const values = POLICY_ORDER.filter((policy) => policies[policy]).map((policy) => ({
    policy,
    value: evidenceValue(policies[policy], spec.metric),
  }));
  const max = Math.max(1, ...values.map((item) => item.value));
  return (
    <ChartFrame title={spec.title} source={spec.source}>
      <div className="bar-chart" aria-label={spec.title}>
        {values.map((item) => (
          <div className="bar-row" key={item.policy} data-policy={item.policy}>
            <span>{item.policy}</span>
            <div className="bar-track"><span style={{ width: `${clamp((item.value / max) * 100, 2, 100)}%` }} /></div>
            <strong>{item.value.toFixed(2)}</strong>
          </div>
        ))}
      </div>
    </ChartFrame>
  );
}

function DistributionRenderer({ spec, data }: { spec: Extract<ChartSpec, { type: "distribution" }>; data: unknown }) {
  const policies = evidenceScenario(data, spec.scenario);
  const allValues = POLICY_ORDER.flatMap((policy) => policies[policy]?.avg_wait_seed_values ?? []);
  const min = Math.min(...allValues, 0);
  const max = Math.max(...allValues, 1);
  return (
    <ChartFrame title={spec.title} source={spec.source}>
      <svg id="policy-density-chart" className="semantic-chart distribution-chart" viewBox="0 0 620 250" role="img" aria-label={spec.title}>
        {POLICY_ORDER.map((policy, row) => {
          const values = policies[policy]?.avg_wait_seed_values ?? [];
          return (
            <g key={policy} className="density-series" data-policy={policy}>
              <text x="8" y={35 + row * 42}>{policy}</text>
              <line x1="118" x2="600" y1={31 + row * 42} y2={31 + row * 42} className="chart-grid" />
              {values.map((value, index) => (
                <circle
                  key={`${policy}-${index}`}
                  cx={118 + normalize(Number(value), min, max) * 482}
                  cy={31 + row * 42 + ((index % 3) - 1) * 4}
                  r="3"
                  className={`distribution-dot distribution-dot-${row}`}
                />
              ))}
            </g>
          );
        })}
      </svg>
    </ChartFrame>
  );
}

function TradeoffRenderer({ spec, data }: { spec: Extract<ChartSpec, { type: "tradeoff" }>; data: unknown }) {
  const policies = evidenceScenario(data, spec.scenario);
  const points = POLICY_ORDER.filter((policy) => policies[policy]).map((policy) => ({
    policy,
    x: evidenceValue(policies[policy], spec.x),
    y: evidenceValue(policies[policy], spec.y),
  }));
  const xMin = Math.min(...points.map((point) => point.x));
  const xMax = Math.max(...points.map((point) => point.x));
  const yMin = Math.min(...points.map((point) => point.y));
  const yMax = Math.max(...points.map((point) => point.y));
  return (
    <ChartFrame title={spec.title} source={spec.source}>
      <svg className="semantic-chart" viewBox="0 0 620 260" role="img" aria-label={spec.title}>
        <line x1="54" x2="598" y1="226" y2="226" className="chart-axis" />
        <line x1="54" x2="54" y1="18" y2="226" className="chart-axis" />
        {points.map((point, index) => (
          <g key={point.policy} data-policy={point.policy}>
            <circle
              cx={64 + normalize(point.x, xMin, xMax) * 520}
              cy={216 - normalize(point.y, yMin, yMax) * 184}
              r="8"
              className={`tradeoff-point tradeoff-point-${index}`}
            />
            <text x={72 + normalize(point.x, xMin, xMax) * 520} y={210 - normalize(point.y, yMin, yMax) * 184}>{point.policy}</text>
          </g>
        ))}
        <text x="280" y="250">{spec.x}</text>
        <text transform="translate(14 160) rotate(-90)">{spec.y}</text>
      </svg>
    </ChartFrame>
  );
}

function FloorHeatmapRenderer({ spec, data }: { spec: Extract<ChartSpec, { type: "floorHeatmap" }>; data: unknown }) {
  const snapshot = data as Snapshot | undefined;
  const counts = Array.from({ length: 18 }, (_, index) => {
    const floor = index + 1;
    const queue = snapshot?.queues?.[String(floor)] ?? { up: 0, down: 0 };
    return { floor, count: Number(queue.up) + Number(queue.down) };
  });
  const max = Math.max(1, ...counts.map((item) => item.count));
  return (
    <ChartFrame title={spec.title} source={spec.source}>
      <div id="floor-heatmap" className="floor-heatmap">
        {counts.map((item) => (
          <div
            key={item.floor}
            className="heat-cell"
            data-floor={item.floor}
            data-queue={item.count}
            style={{ "--heat": item.count / max } as React.CSSProperties}
          >
            <span>{item.floor}F</span>
            <strong>{item.count}</strong>
          </div>
        ))}
      </div>
    </ChartFrame>
  );
}

function ConfidenceIntervalRenderer({ spec, data }: { spec: Extract<ChartSpec, { type: "confidenceInterval" }>; data: unknown }) {
  const policies = evidenceScenario(data, spec.scenario);
  return (
    <ChartFrame title={spec.title} source={spec.source}>
      <div className="ci-chart">
        {POLICY_ORDER.filter((policy) => policies[policy]).map((policy) => {
          const item = policies[policy];
          const mean = evidenceValue(item, spec.metric);
          const halfwidth = Number(item.avg_wait_ci95_halfwidth ?? 0);
          return (
            <div key={policy} className="ci-row">
              <span>{policy}</span>
              <strong>{mean.toFixed(2)} ± {halfwidth.toFixed(2)}s</strong>
            </div>
          );
        })}
      </div>
    </ChartFrame>
  );
}

function ExperimentMatrixRenderer({ spec, data }: { spec: Extract<ChartSpec, { type: "experimentMatrix" }>; data: unknown }) {
  const payload = data as ExperimentPayload | undefined;
  const scenarios = Object.entries(payload?.baseline?.scenarios ?? {});
  const values = scenarios.flatMap(([, scenario]) => POLICY_ORDER.map((policy) => evidenceValue(scenario.policies[policy], spec.metric)));
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  return (
    <ChartFrame title={spec.title} source={spec.source}>
      <div className="experiment-matrix" role="table" aria-label={spec.title}>
        <div className="matrix-row matrix-head" role="row">
          <span role="columnheader">scenario</span>
          {POLICY_ORDER.map((policy) => <span role="columnheader" key={policy}>{policy}</span>)}
        </div>
        {scenarios.map(([scenarioName, scenario]) => (
          <div className="matrix-row" role="row" key={scenarioName}>
            <strong role="rowheader">{scenarioName}</strong>
            {POLICY_ORDER.map((policy) => {
              const value = evidenceValue(scenario.policies[policy], spec.metric);
              return <span role="cell" key={policy} style={{ "--heat": normalize(value, min, max) } as React.CSSProperties}>{value.toFixed(1)}</span>;
            })}
          </div>
        ))}
      </div>
    </ChartFrame>
  );
}

function MetricCardRenderer({ spec, data }: { spec: Extract<ChartSpec, { type: "metricCard" }>; data: unknown }) {
  const record = data as Record<string, unknown>;
  return (
    <ChartFrame title={spec.title} source={spec.source}>
      <div className="single-metric-card">
        <strong>{String(record?.[spec.metric] ?? "—")}{spec.unit ?? ""}</strong>
        <span>{spec.metric}</span>
      </div>
    </ChartFrame>
  );
}

const REGISTERED_RENDERERS = {
  timeSeries: TimeSeriesRenderer,
  policyComparison: PolicyComparisonRenderer,
  distribution: DistributionRenderer,
  tradeoff: TradeoffRenderer,
  floorHeatmap: FloorHeatmapRenderer,
  metricCard: MetricCardRenderer,
  confidenceInterval: ConfidenceIntervalRenderer,
  experimentMatrix: ExperimentMatrixRenderer,
} as const;

export function ChartRenderer({ spec: rawSpec, data }: ChartRendererProps) {
  const parsed = parseChartSpec(rawSpec);
  const Renderer = REGISTERED_RENDERERS[parsed.type] as React.ComponentType<{ spec: any; data: unknown }>;
  return <Renderer spec={parsed} data={data} />;
}
