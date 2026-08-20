from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.trace import generate_trace


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a canonical passenger OD trace")
    parser.add_argument("--scenario", required=True, choices=("morning", "lunch", "normal", "evening"))
    parser.add_argument("--seconds", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    trace = generate_trace(args.scenario, args.seconds, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(trace.to_json() + "\n", encoding="utf-8", newline="\n")
    print(f"events={len(trace.events)} sha256={trace.digest} output={args.output}")


if __name__ == "__main__":
    main()

