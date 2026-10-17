#!/usr/bin/env python3
"""Generate all figures from saved benchmark results (no solver runs).

Usage:
    python scripts/plot_results.py --results data/results
    python scripts/plot_results.py --results data/results --size 9 --difficulty hard
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sudoku_solver.benchmark import generate_all_plots  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="data/results")
    parser.add_argument("--out", default=None,
                        help="figure output dir (default: <results>/figures)")
    parser.add_argument("--size", type=int, default=None)
    parser.add_argument("--difficulty", default=None)
    parser.add_argument("--solver", default=None,
                        help="backtracking | cpsat | sat")
    parser.add_argument("--encoding", default=None)
    parser.add_argument("--backend", default=None)
    args = parser.parse_args()

    filters = {
        k: v for k, v in {
            "size": args.size, "difficulty": args.difficulty,
            "solver": args.solver, "encoding": args.encoding,
            "backend": args.backend,
        }.items() if v is not None
    }
    written = generate_all_plots(args.results, args.out, **filters)
    for path in written:
        print(f"wrote {path}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
