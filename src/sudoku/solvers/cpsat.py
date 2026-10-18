"""OR-Tools CP-SAT solver adapter for Sudoku."""

from __future__ import annotations

import math
import time
from typing import Any, Sequence

from ortools.sat.python import cp_model

from ..validator import is_valid_solution_for_puzzle
from .base import (
    STATUS_BUILD_FAIL,
    STATUS_INVALID_SOLUTION,
    STATUS_SOLVED_VALID,
    STATUS_SOLVER_ERROR,
    STATUS_TIMEOUT,
    STATUS_UNSAT_INVESTIGATE,
    SolverResult,
)


def solve_cpsat(
    puzzle: Sequence[int],
    N: int,
    timeout: float | None = None,
    num_workers: int = 1,
) -> SolverResult:
    """Solve puzzle using OR-Tools CP-SAT with AddAllDifferent integer variables."""
    t_start = time.perf_counter()

    # Step 1: Model Build
    try:
        t0 = time.perf_counter()
        box = math.isqrt(N)
        model = cp_model.CpModel()

        # Decision variables: x[r][c] in 1..N
        x = [
            [model.NewIntVar(1, N, f"x_{r}_{c}") for c in range(N)]
            for r in range(N)
        ]

        # Row all-different
        for r in range(N):
            model.AddAllDifferent(x[r])

        # Column all-different
        for c in range(N):
            model.AddAllDifferent([x[r][c] for r in range(N)])

        # Box all-different
        for br in range(box):
            for bc in range(box):
                model.AddAllDifferent(
                    [
                        x[br * box + r][bc * box + c]
                        for r in range(box)
                        for c in range(box)
                    ]
                )

        # Clues
        n_clues = 0
        for i, val in enumerate(puzzle):
            if val != 0:
                r = i // N
                c = i % N
                model.Add(x[r][c] == val)
                n_clues += 1

        t_build = time.perf_counter() - t0
    except Exception as e:
        return SolverResult(
            status=STATUS_BUILD_FAIL,
            t_build=0.0,
            t_solve=0.0,
            t_total=time.perf_counter() - t_start,
            error=f"CP-SAT model build failed: {e}",
            stats={"solver": "ortools-cpsat"},
        )

    # Step 2: Solve
    solver = cp_model.CpSolver()
    if timeout is not None and timeout > 0:
        solver.parameters.max_time_in_seconds = float(timeout)
    solver.parameters.num_workers = int(num_workers)
    solver.parameters.log_search_progress = False

    t_solve_start = time.perf_counter()
    try:
        status_code = solver.Solve(model)
        t_solve = time.perf_counter() - t_solve_start
    except Exception as e:
        return SolverResult(
            status=STATUS_SOLVER_ERROR,
            t_build=t_build,
            t_solve=time.perf_counter() - t_solve_start,
            t_total=time.perf_counter() - t_start,
            error=f"CP-SAT solver invocation failed: {e}",
            stats={"solver": "ortools-cpsat"},
        )

    status_name = solver.StatusName(status_code)
    stats: dict[str, Any] = {
        "solver": "ortools-cpsat",
        "cpsat_status": status_name,
        "branches": solver.NumBranches(),
        "conflicts": solver.NumConflicts(),
        "wall_time": solver.WallTime(),
        "user_time": solver.UserTime(),
        "num_workers": num_workers,
        "clues": n_clues,
    }

    if status_name in ("FEASIBLE", "OPTIMAL"):
        candidate = [solver.Value(x[r][c]) for r in range(N) for c in range(N)]
        val_res = is_valid_solution_for_puzzle(puzzle, candidate, N)
        t_total = time.perf_counter() - t_start

        if not val_res.ok:
            return SolverResult(
                status=STATUS_INVALID_SOLUTION,
                solution=candidate,
                t_build=t_build,
                t_solve=t_solve,
                t_total=t_total,
                stats=stats,
                error=f"CP-SAT solution failed validation: {val_res.reason} ({val_res.message})",
            )

        return SolverResult(
            status=STATUS_SOLVED_VALID,
            solution=candidate,
            t_build=t_build,
            t_solve=t_solve,
            t_total=t_total,
            stats=stats,
        )

    elif status_name == "INFEASIBLE":
        return SolverResult(
            status=STATUS_UNSAT_INVESTIGATE,
            t_build=t_build,
            t_solve=t_solve,
            t_total=time.perf_counter() - t_start,
            stats=stats,
            error="CP-SAT reported INFEASIBLE on a puzzle derived from a valid solution",
        )

    elif status_name in ("UNKNOWN", "MODEL_INVALID"):
        return SolverResult(
            status=STATUS_TIMEOUT,
            t_build=t_build,
            t_solve=t_solve,
            t_total=time.perf_counter() - t_start,
            stats=stats,
            error=f"CP-SAT finished with status {status_name} (likely timeout)",
        )

    return SolverResult(
        status=STATUS_SOLVER_ERROR,
        t_build=t_build,
        t_solve=t_solve,
        t_total=time.perf_counter() - t_start,
        stats=stats,
        error=f"CP-SAT returned unexpected status: {status_name}",
    )
