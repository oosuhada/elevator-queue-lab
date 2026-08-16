from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ("morning", "lunch", "normal", "evening", "shock", "mixed_day")
POLICIES = ("collective", "capr", "rl")
COLORS = {
    "collective": "#6ca9ff",
    "capr": "#4dd7d1",
    "rl": "#f1b86a",
}


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _summary_map(payload: dict[str, object]) -> dict[tuple[str, str], dict[str, object]]:
    return {
        (str(row["scenario"]), str(row["policy"])): row
        for row in payload["evaluation"]["summaries"]  # type: ignore[index]
    }


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _wait_chart(payload: dict[str, object]) -> str:
    rows = _summary_map(payload)
    width, height = 1120, 620
    left, right, top, bottom = 82, 28, 62, 118
    plot_w, plot_h = width - left - right, height - top - bottom
    max_wait = max(
        float(rows[(scenario, policy)]["metrics"]["avg_wait"]["mean"])
        + float(rows[(scenario, policy)]["metrics"]["avg_wait"]["ci95_halfwidth"])
        for scenario in SCENARIOS
        for policy in POLICIES
    )
    axis_max = max(10.0, (int(max_wait / 10.0) + 2) * 10.0)
    group_w = plot_w / len(SCENARIOS)
    bar_w = min(34.0, group_w / 4.8)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#07121a"/>',
        '<text x="82" y="34" fill="#e6f1f7" font-family="system-ui,sans-serif" font-size="22" font-weight="700">30-seed held-out mean waiting time</text>',
        '<text x="82" y="54" fill="#8299a8" font-family="system-ui,sans-serif" font-size="12">Fixed M5 checkpoint · common passenger traces · whiskers are 95% CI half-widths</text>',
    ]
    for tick in range(0, int(axis_max) + 1, 10):
        y = top + plot_h - (tick / axis_max) * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#17303e" stroke-width="1"/>')
        parts.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" fill="#8299a8" font-family="system-ui,sans-serif" font-size="11">{tick}s</text>')

    for scenario_index, scenario in enumerate(SCENARIOS):
        center = left + group_w * (scenario_index + 0.5)
        for policy_index, policy in enumerate(POLICIES):
            row = rows[(scenario, policy)]
            mean = float(row["metrics"]["avg_wait"]["mean"])
            ci = float(row["metrics"]["avg_wait"]["ci95_halfwidth"])
            x = center + (policy_index - 1) * (bar_w + 8) - bar_w / 2
            y = top + plot_h - (mean / axis_max) * plot_h
            h = (mean / axis_max) * plot_h
            error_top = top + plot_h - ((mean + ci) / axis_max) * plot_h
            error_bottom = top + plot_h - (max(0.0, mean - ci) / axis_max) * plot_h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="4" fill="{COLORS[policy]}" opacity="0.88"/>')
            parts.append(f'<line x1="{x + bar_w/2:.1f}" y1="{error_top:.1f}" x2="{x + bar_w/2:.1f}" y2="{error_bottom:.1f}" stroke="#dce8ee" stroke-width="1.5"/>')
            parts.append(f'<line x1="{x + bar_w/2 - 5:.1f}" y1="{error_top:.1f}" x2="{x + bar_w/2 + 5:.1f}" y2="{error_top:.1f}" stroke="#dce8ee" stroke-width="1.5"/>')
            parts.append(f'<text x="{x + bar_w/2:.1f}" y="{max(top + 12, y - 8):.1f}" text-anchor="middle" fill="#dce8ee" font-family="system-ui,sans-serif" font-size="10">{mean:.1f}</text>')
        label = scenario.replace("_", " ")
        parts.append(f'<text x="{center:.1f}" y="{top + plot_h + 24:.1f}" text-anchor="middle" fill="#b7c8d1" font-family="system-ui,sans-serif" font-size="12">{_esc(label)}</text>')

    legend_y = height - 46
    legend_x = left
    for policy in POLICIES:
        parts.append(f'<rect x="{legend_x}" y="{legend_y - 10}" width="14" height="14" rx="3" fill="{COLORS[policy]}"/>')
        parts.append(f'<text x="{legend_x + 21}" y="{legend_y + 1}" fill="#b7c8d1" font-family="system-ui,sans-serif" font-size="12">{policy}</text>')
        legend_x += 118
    parts.append(f'<text x="{width-right}" y="{legend_y + 1}" text-anchor="end" fill="#637b89" font-family="system-ui,sans-serif" font-size="10">Source: evidence/m6-heldout-30seed.json</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _tradeoff_chart(payload: dict[str, object]) -> str:
    rows = _summary_map(payload)
    points: list[tuple[str, str, float, float]] = []
    for scenario in SCENARIOS:
        base = rows[(scenario, "collective")]
        base_wait = float(base["metrics"]["avg_wait"]["mean"])
        base_energy = float(base["metrics"]["energy_proxy"]["mean"])
        for policy in ("capr", "rl"):
            row = rows[(scenario, policy)]
            wait = float(row["metrics"]["avg_wait"]["mean"])
            energy = float(row["metrics"]["energy_proxy"]["mean"])
            points.append((scenario, policy, (wait / base_wait - 1.0) * 100.0, (energy / base_energy - 1.0) * 100.0))

    width, height = 1120, 650
    left, right, top, bottom = 92, 35, 70, 100
    plot_w, plot_h = width - left - right, height - top - bottom
    xs = [point[2] for point in points] + [0.0]
    ys = [point[3] for point in points] + [0.0]
    x_min, x_max = min(-15.0, min(xs) - 8.0), max(15.0, max(xs) + 8.0)
    y_min, y_max = min(-15.0, min(ys) - 12.0), max(15.0, max(ys) + 12.0)

    def px(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_w

    def py(value: float) -> float:
        return top + plot_h - (value - y_min) / (y_max - y_min) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#07121a"/>',
        '<text x="92" y="35" fill="#e6f1f7" font-family="system-ui,sans-serif" font-size="22" font-weight="700">Wait–energy trade-off vs collective</text>',
        '<text x="92" y="56" fill="#8299a8" font-family="system-ui,sans-serif" font-size="12">Lower-left is the desired quadrant; percentages use 30 held-out seed means</text>',
        f'<rect x="{left}" y="{top}" width="{px(0)-left:.1f}" height="{py(0)-top:.1f}" fill="#173c34" opacity="0.25"/>',
        f'<line x1="{px(0):.1f}" y1="{top}" x2="{px(0):.1f}" y2="{top+plot_h}" stroke="#607986" stroke-width="1.2"/>',
        f'<line x1="{left}" y1="{py(0):.1f}" x2="{left+plot_w}" y2="{py(0):.1f}" stroke="#607986" stroke-width="1.2"/>',
    ]
    for value in range(-75, 101, 25):
        if x_min <= value <= x_max:
            parts.append(f'<text x="{px(value):.1f}" y="{top+plot_h+24}" text-anchor="middle" fill="#8299a8" font-family="system-ui,sans-serif" font-size="10">{value:+d}%</text>')
    for value in range(-50, 201, 25):
        if y_min <= value <= y_max:
            parts.append(f'<text x="{left-12}" y="{py(value)+4:.1f}" text-anchor="end" fill="#8299a8" font-family="system-ui,sans-serif" font-size="10">{value:+d}%</text>')
    parts.append(f'<text x="{left+plot_w/2:.1f}" y="{height-48}" text-anchor="middle" fill="#a9bdc8" font-family="system-ui,sans-serif" font-size="12">Mean-wait change vs collective →</text>')
    parts.append(f'<text transform="translate(22 {top+plot_h/2:.1f}) rotate(-90)" text-anchor="middle" fill="#a9bdc8" font-family="system-ui,sans-serif" font-size="12">Energy-proxy change vs collective →</text>')
    abbreviations = {"morning":"AM", "lunch":"LU", "normal":"NO", "evening":"PM", "shock":"SH", "mixed_day":"MX"}
    for scenario, policy, wait_delta, energy_delta in points:
        x, y = px(wait_delta), py(energy_delta)
        if policy == "capr":
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{COLORS[policy]}" stroke="#e6f1f7" stroke-width="1"/>')
        else:
            parts.append(f'<rect x="{x-7:.1f}" y="{y-7:.1f}" width="14" height="14" rx="2" fill="{COLORS[policy]}" stroke="#e6f1f7" stroke-width="1"/>')
        dx = 12 if x < left + plot_w - 80 else -12
        anchor = "start" if dx > 0 else "end"
        parts.append(f'<text x="{x+dx:.1f}" y="{y-8:.1f}" text-anchor="{anchor}" fill="#dce8ee" font-family="system-ui,sans-serif" font-size="10">{abbreviations[scenario]} {policy.upper()}</text>')
    parts.append(f'<text x="{width-right}" y="{height-20}" text-anchor="end" fill="#637b89" font-family="system-ui,sans-serif" font-size="10">AM morning · LU lunch · NO normal · PM evening · SH shock · MX mixed day</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _evidence_markdown(m3: dict[str, object], m5: dict[str, object], m6: dict[str, object]) -> str:
    m6_rows = _summary_map(m6)
    lines = [
        "# M6 evidence summary",
        "",
        "This file is generated from committed experiment artifacts. Do not edit the numeric tables by hand.",
        "",
        "## 30-seed held-out release evaluation",
        "",
        "The M5 checkpoint is fixed before this evaluation. Passenger seeds 21–50 are disjoint from training seeds 1–6; `mixed_day` was absent from training.",
        "",
        "| scenario | collective AWT | CAPR AWT | RL AWT | CAPR guardrail | RL guardrail |",
        "|---|---:|---:|---:|---|---|",
    ]
    for scenario in SCENARIOS:
        c = m6_rows[(scenario, "collective")]
        capr = m6_rows[(scenario, "capr")]
        rl = m6_rows[(scenario, "rl")]
        lines.append(
            f"| {scenario} | {float(c['metrics']['avg_wait']['mean']):.2f}s | "
            f"{float(capr['metrics']['avg_wait']['mean']):.2f}s | "
            f"{float(rl['metrics']['avg_wait']['mean']):.2f}s | "
            f"{capr['guardrail_classification']} | {rl['guardrail_classification']} |"
        )
    lines += [
        "",
        "## M3 30-seed CAPR evidence",
        "",
        "| scenario | collective AWT | CAPR AWT | collective energy | CAPR energy | CAPR classification |",
        "|---|---:|---:|---:|---:|---|",
    ]
    m3_scenarios = m3["scenarios"]
    for scenario in SCENARIOS:
        c = m3_scenarios[scenario]["policies"]["collective"]
        capr = m3_scenarios[scenario]["policies"]["capr"]
        lines.append(
            f"| {scenario} | {float(c['avg_wait']):.2f}s | {float(capr['avg_wait']):.2f}s | "
            f"{float(c['energy_proxy']):.0f} | {float(capr['energy_proxy']):.0f} | {capr['guardrail_classification']} |"
        )
    lines += [
        "",
        "## M5 single-feature ablation headline",
        "",
        "All five single-feature ablations preserve the same general verdict: no global learned-controller superiority; `mixed_day` remains the only guardrail-clean RL candidate.",
        "",
        "| ablated feature | mixed_day RL AWT | mixed_day RL energy |",
        "|---|---:|---:|",
    ]
    for feature in ("eta", "load", "capacity", "age", "prepositioning"):
        headline = m5["ablations"][feature]["headline"]
        row = next(item for item in headline if item["scenario"] == "mixed_day" and item["policy"] == "rl")
        lines.append(f"| {feature} | {float(row['avg_wait']):.2f}s | {float(row['energy_proxy']):.0f} |")
    lines += [
        "",
        "Generated by `python scripts/generate_m6_assets.py`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic M6 portfolio evidence assets.")
    parser.add_argument("--m3", type=Path, default=ROOT / "evidence" / "m3-regression-baseline.json")
    parser.add_argument("--m5", type=Path, default=ROOT / "evidence" / "m5-heldout-evaluation.json")
    parser.add_argument("--m6", type=Path, default=ROOT / "evidence" / "m6-heldout-30seed.json")
    args = parser.parse_args()
    m3, m5, m6 = _load(args.m3), _load(args.m5), _load(args.m6)
    assets = ROOT / "docs" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "m6-heldout-wait.svg").write_text(_wait_chart(m6), encoding="utf-8")
    (assets / "m6-wait-energy-tradeoff.svg").write_text(_tradeoff_chart(m6), encoding="utf-8")
    (ROOT / "docs" / "M6_EVIDENCE_SUMMARY.md").write_text(
        _evidence_markdown(m3, m5, m6), encoding="utf-8"
    )
    print("generated docs/assets/m6-heldout-wait.svg")
    print("generated docs/assets/m6-wait-energy-tradeoff.svg")
    print("generated docs/M6_EVIDENCE_SUMMARY.md")


if __name__ == "__main__":
    main()
