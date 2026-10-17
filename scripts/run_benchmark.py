#!/usr/bin/env python3
"""Run the configured benchmark suite (resumable).

Usage:
    python scripts/run_benchmark.py --config configs/benchmark.toml
    python scripts/run_benchmark.py --config configs/quick.toml   # smoke run

Re-running after an interruption skips runs that already have a record.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sudoku_solver.benchmark import load_config, run_benchmark  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/benchmark.toml")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    summary = run_benchmark(config, quiet=args.quiet)
    print(json.dumps(summary, indent=2, default=str))
    # Non-zero exit when every run failed (partial failure still returns data).
    statuses = summary.get("status_counts", {})
    if statuses and not statuses.get("solved") and not statuses.get("unsatisfiable"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
