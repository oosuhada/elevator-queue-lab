from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
REQUIRED = (
    "AGENTS.md",
    "README.md",
    "docs/PRODUCT_CHARTER.md",
    "docs/MODELING_PROTOCOL.md",
    "docs/ROADMAP.md",
    "docs/M3_FINDINGS.md",
    "docs/M5_MODEL_CARD.md",
    "docs/M6_RESEARCH_REPORT.md",
    "docs/M6_EVIDENCE_SUMMARY.md",
    "docs/assets/m6-dashboard.png",
    "docs/assets/m6-heldout-wait.svg",
    "docs/assets/m6-wait-energy-tradeoff.svg",
    "deploy/README.md",
    "deploy/install_macos.sh",
    "deploy/Caddyfile.example",
    "deploy/nginx-location.conf.example",
    "evidence/m3-regression-baseline.json",
    "evidence/m5-heldout-evaluation.json",
    "evidence/m6-heldout-30seed.json",
    "models/m5-ddqn-baseline.json",
)
FORBIDDEN_TRACKED_PREFIXES = (
    ".tmp-",
    "node_modules/",
    "artifacts/",
    "test-results/",
    "__pycache__/",
)


def _git_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def _local_markdown_links(path: Path) -> list[Path]:
    text = path.read_text(encoding="utf-8")
    links: list[Path] = []
    for raw in LOCAL_LINK_RE.findall(text):
        target = raw.strip().split()[0].strip("<>")
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.split("#", 1)[0]
        links.append((path.parent / target).resolve())
    return links


def _png_dimensions(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()[:24]
    if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", raw[16:24])


def audit(*, live_url: str | None = None) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required release file: {relative}")

    tracked = _git_files()
    for relative in tracked:
        if relative.startswith(FORBIDDEN_TRACKED_PREFIXES) or "/__pycache__/" in relative:
            errors.append(f"forbidden generated file is tracked: {relative}")

    for markdown in (ROOT / "README.md", ROOT / "docs" / "M6_RESEARCH_REPORT.md"):
        if not markdown.is_file():
            continue
        for target in _local_markdown_links(markdown):
            if not target.exists():
                errors.append(f"broken local link in {markdown.relative_to(ROOT)}: {target}")

    model_path = ROOT / "models" / "m5-ddqn-baseline.json"
    m6_path = ROOT / "evidence" / "m6-heldout-30seed.json"
    if model_path.is_file() and m6_path.is_file():
        m6 = json.loads(m6_path.read_text(encoding="utf-8"))
        actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if m6.get("fixed_model_sha256") != actual_hash:
            errors.append("M6 evidence model SHA-256 does not match checked-in M5 artifact")
        contract = m6.get("held_out_contract", {})
        held_out = {int(seed) for seed in contract.get("passenger_seeds", [])}
        training = {int(seed) for seed in m6.get("training_passenger_seeds", [])}
        if int(contract.get("seed_count", 0)) < 30 or len(held_out) < 30:
            errors.append("M6 release evidence has fewer than 30 held-out seeds")
        if training & held_out:
            errors.append("M6 release evidence overlaps training and held-out passenger seeds")
        if not contract.get("mixed_day_was_unseen_in_training"):
            errors.append("M6 release evidence does not record mixed_day as unseen training traffic")

    screenshot = ROOT / "docs" / "assets" / "m6-dashboard.png"
    if screenshot.is_file():
        try:
            width, height = _png_dimensions(screenshot)
            if width < 1200 or height < 700:
                errors.append(f"README screenshot is too small for portfolio QA: {width}x{height}")
        except ValueError as exc:
            errors.append(str(exc))

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    lowered = readme.lower()
    if "formal standards compliance" not in lowered and "formal iso" not in lowered:
        errors.append("README must explicitly disclaim formal standards compliance")
    if "negative/mixed" not in lowered:
        errors.append("README must preserve the learned-controller negative/mixed result")

    deploy_readme = ROOT / "deploy" / "README.md"
    if deploy_readme.is_file():
        deployment_text = deploy_readme.read_text(encoding="utf-8")
        if "https://elevator.oosu.dev/" not in deployment_text:
            errors.append("deployment contract must target https://elevator.oosu.dev/")
        if "ontology.oosu.dev/elevator_queue_lab" in deployment_text:
            errors.append("deployment contract must not mount the demo under ontology.oosu.dev")

    if live_url:
        parsed = urllib.parse.urlparse(live_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "elevator.oosu.dev"
            or parsed.path not in {"", "/"}
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            errors.append(
                "public release URL must be exactly the dedicated host https://elevator.oosu.dev/"
            )
            return errors
        try:
            request = urllib.request.Request(live_url, headers={"User-Agent": "elevator-queue-lab-release-audit"})
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status != 200:
                    errors.append(f"live demo returned HTTP {response.status}: {live_url}")
        except Exception as exc:  # network errors are release blockers only when URL is required.
            errors.append(f"live demo check failed: {live_url}: {exc}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the repository before the M6 portfolio release.")
    parser.add_argument("--live-url", help="optional public demo URL; when supplied HTTP 200 is required")
    args = parser.parse_args()
    errors = audit(live_url=args.live_url)
    if errors:
        print("M6 release audit FAILED")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("M6 release audit passed")
    print(f"tracked_files={len(_git_files())}")
    print("held_out_seed_count=30")


if __name__ == "__main__":
    main()
