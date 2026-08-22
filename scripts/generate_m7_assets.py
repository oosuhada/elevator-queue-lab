from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _scale(value: float, lower: float, upper: float, start: float, end: float) -> float:
    if upper == lower:
        return (start + end) / 2.0
    return start + (value - lower) / (upper - lower) * (end - start)


def generate_svg(discovery: dict[str, object], validation: dict[str, object]) -> str:
    width, height = 1100, 650
    left, right, top, bottom = 92, 42, 70, 86
    plot_w = width - left - right
    plot_h = height - top - bottom
    discovery_cells = discovery["cells"]
    validation_cells = validation["cells"]
    all_cells = [*discovery_cells, *validation_cells]
    xs = [float(cell["demand"]["bidirectional_load_rate"]) for cell in all_cells]
    ys = [float(cell["capr_vs_static"]["metrics"]["avg_wait"]["delta_mean"]) for cell in all_cells]
    x_min, x_max = 0.0, max(30.0, max(xs) * 1.03)
    y_min, y_max = min(-7.0, min(ys) - 0.5), max(4.0, max(ys) + 0.5)
    x = lambda value: _scale(value, x_min, x_max, left, left + plot_w)
    y = lambda value: _scale(value, y_min, y_max, top + plot_h, top)
    theory = discovery["theory"]
    threshold = float(theory["best_single_threshold"]["threshold"])
    fit = theory["linear_wait_delta_fit"]
    intercept = float(fit["intercept_seconds"])
    slope = float(fit["slope_seconds_per_bidirectional_pax_per_min"])

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 650">',
        '<rect width="1100" height="650" rx="20" fill="#08141e"/>',
        '<text x="92" y="38" fill="#eaf1f7" font-family="system-ui,sans-serif" font-size="22" font-weight="700">Counterflow Criticality Hypothesis</text>',
        '<text x="92" y="59" fill="#718a9b" font-family="system-ui,sans-serif" font-size="12">CAPR continuous reassignment minus CAPR-static · 30 common seeds per cell · lower ΔAWT is better</text>',
    ]
    for tick in (0, 4, 8, 12, 16, 20, 24, 28):
        px = x(float(tick))
        lines.append(f'<line x1="{px:.2f}" y1="{top}" x2="{px:.2f}" y2="{top + plot_h}" stroke="#294252" stroke-opacity=".35"/>')
        lines.append(f'<text x="{px:.2f}" y="{height - 55}" text-anchor="middle" fill="#718a9b" font-family="system-ui,sans-serif" font-size="11">{tick}</text>')
    for tick in (-6, -4, -2, 0, 2, 4):
        if not y_min <= tick <= y_max:
            continue
        py = y(float(tick))
        lines.append(f'<line x1="{left}" y1="{py:.2f}" x2="{left + plot_w}" y2="{py:.2f}" stroke="#294252" stroke-opacity=".35"/>')
        lines.append(f'<text x="{left - 12}" y="{py + 4:.2f}" text-anchor="end" fill="#718a9b" font-family="system-ui,sans-serif" font-size="11">{tick:+d}s</text>')
    lines.append(f'<line x1="{left}" y1="{y(0):.2f}" x2="{left + plot_w}" y2="{y(0):.2f}" stroke="#dce8ee" stroke-opacity=".6" stroke-dasharray="6 5"/>')
    lines.append(f'<line x1="{x(threshold):.2f}" y1="{top}" x2="{x(threshold):.2f}" y2="{top + plot_h}" stroke="#f1b86a" stroke-opacity=".8" stroke-dasharray="4 5"/>')
    lines.append(f'<text x="{x(threshold) + 8:.2f}" y="{top + 18}" fill="#f1b86a" font-family="system-ui,sans-serif" font-size="11">high-effect trigger B≈{threshold:.2f}</text>')
    fit_y0 = intercept
    fit_y1 = intercept + slope * x_max
    lines.append(f'<line x1="{x(0):.2f}" y1="{y(fit_y0):.2f}" x2="{x(x_max):.2f}" y2="{y(fit_y1):.2f}" stroke="#4dd7d1" stroke-width="2.5" stroke-dasharray="9 6"/>')

    for cell in discovery_cells:
        cx = x(float(cell["demand"]["bidirectional_load_rate"]))
        cy = y(float(cell["capr_vs_static"]["metrics"]["avg_wait"]["delta_mean"]))
        gain = bool(cell["capr_vs_static"]["supported_wait_gain"])
        loss = bool(cell["capr_vs_static"]["supported_wait_loss"])
        fill = "#79dfb0" if gain else "#ff8a8a" if loss else "#6ca9ff"
        title = html.escape(
            f"Discovery λ={cell['demand']['arrivals_per_minute']}, p_up={cell['demand']['lobby_up_probability']}, B={cell['demand']['bidirectional_load_rate']}, ΔAWT={cell['capr_vs_static']['metrics']['avg_wait']['delta_mean']}"
        )
        lines.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="5" fill="{fill}" fill-opacity=".8" stroke="#071019" stroke-width="1.4"><title>{title}</title></circle>')

    for cell in validation_cells:
        cx = x(float(cell["demand"]["bidirectional_load_rate"]))
        cy = y(float(cell["capr_vs_static"]["metrics"]["avg_wait"]["delta_mean"]))
        gain = bool(cell["capr_vs_static"]["supported_wait_gain"])
        fill = "#79dfb0" if gain else "#9db4c2"
        lines.append(f'<rect x="{cx - 5:.2f}" y="{cy - 5:.2f}" width="10" height="10" fill="{fill}" fill-opacity=".25" stroke="{fill}" stroke-width="1.6" transform="rotate(45 {cx:.2f} {cy:.2f})"/>')

    lines.extend(
        [
            f'<text x="{left + plot_w}" y="{height - 20}" text-anchor="end" fill="#8299a8" font-family="system-ui,sans-serif" font-size="12">Bidirectional load B = λ · 4p↑(1−p↑) [passengers/min] →</text>',
            f'<text x="23" y="{top}" transform="rotate(-90 23 {top})" text-anchor="end" fill="#8299a8" font-family="system-ui,sans-serif" font-size="12">Δ average wait [s] · CAPR − static</text>',
            '<circle cx="92" cy="622" r="5" fill="#6ca9ff"/><text x="105" y="626" fill="#8299a8" font-family="system-ui,sans-serif" font-size="11">discovery</text>',
            '<rect x="180" y="617" width="10" height="10" transform="rotate(45 185 622)" fill="#9db4c2" fill-opacity=".25" stroke="#9db4c2"/><text x="199" y="626" fill="#8299a8" font-family="system-ui,sans-serif" font-size="11">held-out validation</text>',
            '<circle cx="330" cy="622" r="5" fill="#79dfb0"/><text x="343" y="626" fill="#8299a8" font-family="system-ui,sans-serif" font-size="11">95% CI-supported gain</text>',
            '</svg>',
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the M7 counterflow criticality evidence figure")
    parser.add_argument("--discovery", type=Path, default=ROOT / "evidence" / "m7-bidirectional-load-sweep.json")
    parser.add_argument("--validation", type=Path, default=ROOT / "evidence" / "m7-threshold-validation.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "assets" / "m7-counterflow-criticality.svg")
    args = parser.parse_args()
    discovery = json.loads(args.discovery.read_text(encoding="utf-8"))
    validation = json.loads(args.validation.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generate_svg(discovery, validation), encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
