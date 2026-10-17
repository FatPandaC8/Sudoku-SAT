#!/usr/bin/env python3
"""Solve one puzzle with any solver configuration.

Usage:
    python scripts/solve.py data/puzzles/9x9/9x9_easy_000_seed42.json \\
        --solver sat --encoding pairwise --backend glucose4
    python scripts/solve.py --text "53..7...." --size 9 --solver backtracking
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sudoku_solver.benchmark import SolverConfig, run_solver  # noqa: E402
from sudoku_solver.generator import load_puzzle  # noqa: E402
from sudoku_solver.puzzle import format_puzzle, parse_puzzle, validate_solution  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzle", nargs="?", help="puzzle JSON file")
    parser.add_argument("--text", help="inline puzzle text (rows of symbols)")
    parser.add_argument("--solver", default="backtracking",
                        choices=["backtracking", "cpsat", "sat"])
    parser.add_argument("--encoding", default="pairwise")
    parser.add_argument("--backend", default="minisat22")
    parser.add_argument("--ac3", action="store_true")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    givens = None
    puzzle_id = "inline"
    if args.puzzle:
        puzzle, _solution, record = load_puzzle(args.puzzle)
        puzzle_id = record.get("puzzle_id", Path(args.puzzle).stem)
    elif args.text:
        puzzle = parse_puzzle(args.text)
    else:
        parser.error("provide a puzzle file or --text")

    config = SolverConfig(
        solver=args.solver,
        encoding=args.encoding if args.solver == "sat" else None,
        backend=args.backend if args.solver == "sat" else None,
        use_ac3=args.ac3,
    )
    result = run_solver(puzzle, config)

    if args.json:
        print(json.dumps({
            "puzzle_id": puzzle_id,
            "status": result.status,
            "runtime": result.runtime,
            "validated": bool(result.board) and not validate_solution(result.board, puzzle),
            "error": result.error,
            "stats": result.stats,
            "board": format_puzzle(result.board) if result.board else None,
        }, indent=2, default=str))
        return 0 if result.solved else 1

    print(f"puzzle : {puzzle_id}")
    print(f"config : {config.label}")
    print(f"status : {result.status}  ({result.runtime:.4f}s)")
    if result.error:
        print(f"error  : {result.error}")
    if result.board:
        problems = validate_solution(result.board, puzzle)
        print(f"valid  : {not problems}")
        print(format_puzzle(result.board))
    if result.stats:
        interesting = {
            k: v for k, v in result.stats.items()
            if k in ("total_vars", "clauses", "conflicts", "propagations",
                     "nodes", "decisions", "backtracks", "branches",
                     "build_time", "solve_time")
        }
        if interesting:
            print(f"stats  : {interesting}")
    return 0 if result.solved else 1


if __name__ == "__main__":
    raise SystemExit(main())
