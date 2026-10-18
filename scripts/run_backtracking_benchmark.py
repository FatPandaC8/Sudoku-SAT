"""Benchmark the classical backtracking solver on the fixed 120-puzzle dataset.

Runs each puzzle through the backtracking solver (MRV + forward checking)
with a 10-second per-instance timeout, validates every returned solution
independently, and records results to a CSV file.

Does NOT modify or rerun any existing SAT/CP-SAT results.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

# Ensure src/ is on the path so sudoku_solver and sudoku packages are importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sudoku_solver.backtracking import solve_backtracking
from sudoku_solver.puzzle import Board, EMPTY, is_valid_solution
from sudoku.validator import is_valid_solution_for_puzzle
from sudoku.dataset import load_puzzles

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_CSV = REPO_ROOT / "data" / "results" / "backtracking_results.csv"
TIMEOUT_S = 10.0


def run_backtracking_benchmark() -> list[dict]:
    """Run backtracking on all 120 puzzles and return result records."""
    puzzles = load_puzzles(str(REPO_ROOT / "data" / "manifest.csv"))
    results: list[dict] = []

    for i, puzzle_rec in enumerate(puzzles, 1):
        puzzle_id = puzzle_rec["id"]
        N = puzzle_rec["N"]
        ratio = puzzle_rec["requested_ratio"]
        flat_puzzle = puzzle_rec["puzzle"]

        # Build Board from flat list (reshape N x N).
        grid = [flat_puzzle[r * N : (r + 1) * N] for r in range(N)]
        board = Board(grid)

        t0 = time.perf_counter()
        result = solve_backtracking(board, timeout=TIMEOUT_S)
        elapsed = time.perf_counter() - t0

        # Validate solution independently.
        validation_ok = False
        validation_reason = ""
        if result.status == "solved" and result.board is not None:
            candidate = [v for row in result.board.cells for v in row]
            vr = is_valid_solution_for_puzzle(flat_puzzle, candidate, N)
            validation_ok = vr.ok
            validation_reason = vr.reason if not vr.ok else ""

        # Map internal status to benchmark status vocabulary.
        if result.status == "solved":
            status = "SOLVED_VALID" if validation_ok else "INVALID_SOLUTION"
        elif result.status == "timeout":
            status = "TIMEOUT"
        elif result.status == "unsatisfiable":
            status = "UNSAT_INVESTIGATE"
        else:
            status = "SOLVER_ERROR"

        results.append({
            "puzzle_id": puzzle_id,
            "N": N,
            "requested_ratio": ratio,
            "status": status,
            "runtime_s": round(elapsed, 6),
            "t_solve_s": round(result.stats.get("runtime", elapsed), 6),
            "validation_ok": validation_ok,
            "validation_reason": validation_reason,
            "nodes": result.stats.get("nodes", 0),
            "decisions": result.stats.get("decisions", 0),
            "backtracks": result.stats.get("backtracks", 0),
            "eliminations": result.stats.get("eliminations", 0),
            "propagation_steps": result.stats.get("propagation_steps", 0),
            "error": result.error or "",
        })

        print(
            f"[{i:3d}/120] {puzzle_id}: {status} "
            f"({elapsed:.3f}s, nodes={result.stats.get('nodes', 0)})",
            flush=True,
        )

    return results


def save_results(results: list[dict], path: Path) -> None:
    """Write results to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "puzzle_id", "N", "requested_ratio", "status",
        "runtime_s", "t_solve_s", "validation_ok", "validation_reason",
        "nodes", "decisions", "backtracks", "eliminations",
        "propagation_steps", "error",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)


def print_summary(results: list[dict]) -> None:
    """Print a summary of results."""
    total = len(results)
    solved = sum(1 for r in results if r["status"] == "SOLVED_VALID")
    invalid = sum(1 for r in results if r["status"] == "INVALID_SOLUTION")
    timed_out = sum(1 for r in results if r["status"] == "TIMEOUT")
    unsat = sum(1 for r in results if r["status"] == "UNSAT_INVESTIGATE")
    errors = sum(1 for r in results if r["status"] == "SOLVER_ERROR")

    print(f"\n{'=' * 60}")
    print(f"Backtracking Benchmark Summary")
    print(f"{'=' * 60}")
    print(f"Total puzzles:  {total}")
    print(f"Solved valid:   {solved} ({solved / total * 100:.2f}%)")
    print(f"Invalid:        {invalid}")
    print(f"Timeouts:       {timed_out}")
    print(f"Unsat:          {unsat}")
    print(f"Errors:         {errors}")
    print(f"{'=' * 60}")

    # By size
    for n in sorted({r["N"] for r in results}):
        sub = [r for r in results if r["N"] == n]
        s = sum(1 for r in sub if r["status"] == "SOLVED_VALID")
        t = sum(1 for r in sub if r["status"] == "TIMEOUT")
        print(f"  N={n}: {len(sub)} puzzles, {s} solved ({s / len(sub) * 100:.2f}%), {t} timeouts")

    # By ratio
    for ratio in sorted({r["requested_ratio"] for r in results}):
        sub = [r for r in results if r["requested_ratio"] == ratio]
        s = sum(1 for r in sub if r["status"] == "SOLVED_VALID")
        t = sum(1 for r in sub if r["status"] == "TIMEOUT")
        print(f"  r={ratio}: {len(sub)} puzzles, {s} solved ({s / len(sub) * 100:.2f}%), {t} timeouts")


def main() -> None:
    results = run_backtracking_benchmark()
    save_results(results, OUTPUT_CSV)
    print_summary(results)
    print(f"\nResults saved to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
