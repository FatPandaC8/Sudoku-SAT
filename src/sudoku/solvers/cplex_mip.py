"""CPLEX MIP solver adapter for Sudoku with Community Edition limit detection."""

from __future__ import annotations

import math
import time
from typing import Any, Sequence

from ..validator import is_valid_solution_for_puzzle
from .base import (
    STATUS_BLOCKED_LICENSE,
    STATUS_BUILD_FAIL,
    STATUS_INVALID_SOLUTION,
    STATUS_SOLVED_VALID,
    STATUS_SOLVER_ERROR,
    STATUS_TIMEOUT,
    STATUS_UNSAT_INVESTIGATE,
    SolverResult,
)


def solve_cplex_mip(
    puzzle: Sequence[int],
    N: int,
    timeout: float | None = None,
    threads: int = 1,
) -> SolverResult:
    """Solve puzzle using CPLEX MIP (binary one-hot formulation via docplex.mp)."""
    t_start = time.perf_counter()

    try:
        import docplex.mp.model as cpx_mp
        import cplex
    except ImportError as e:
        return SolverResult(
            status=STATUS_SOLVER_ERROR,
            t_build=0.0,
            t_solve=0.0,
            t_total=time.perf_counter() - t_start,
            error=f"cplex or docplex not installed or import failed: {e}",
            stats={"solver": "cplex-mip"},
        )

    # Step 1: Model Build
    try:
        t0 = time.perf_counter()
        box = math.isqrt(N)

        mp = cpx_mp.Model(name="sudoku_cplex_mip")
        mp.context.cplex_parameters.threads = int(threads)
        if timeout is not None and timeout > 0:
            mp.set_time_limit(float(timeout))

        x = mp.binary_var_cube(N, N, range(1, N + 1), name="x")

        # 1. Exactly one per cell
        for r in range(N):
            for c in range(N):
                mp.add_constraint(mp.sum(x[r, c, v] for v in range(1, N + 1)) == 1)

        # 2. Exactly one per row
        for r in range(N):
            for v in range(1, N + 1):
                mp.add_constraint(mp.sum(x[r, c, v] for c in range(N)) == 1)

        # 3. Exactly one per column
        for c in range(N):
            for v in range(1, N + 1):
                mp.add_constraint(mp.sum(x[r, c, v] for r in range(N)) == 1)

        # 4. Exactly one per box
        for br in range(box):
            for bc in range(box):
                for v in range(1, N + 1):
                    mp.add_constraint(
                        mp.sum(
                            x[br * box + r, bc * box + c, v]
                            for r in range(box)
                            for c in range(box)
                        ) == 1
                    )

        # 5. Clues
        n_clues = 0
        for i, val in enumerate(puzzle):
            if val != 0:
                r = i // N
                c = i % N
                mp.add_constraint(x[r, c, val] == 1)
                n_clues += 1

        t_build = time.perf_counter() - t0

    except Exception as e:
        err_msg = str(e)
        if "size limits" in err_msg or "1000 vars" in err_msg or "CPLEX code=1016" in err_msg:
            return SolverResult(
                status=STATUS_BLOCKED_LICENSE,
                t_build=time.perf_counter() - t_start,
                t_solve=0.0,
                t_total=time.perf_counter() - t_start,
                error=f"CPLEX Community Edition limit exceeded: {err_msg}",
                stats={"solver": "cplex-mip", "reason": "COMMUNITY_EDITION_LIMIT"},
            )
        return SolverResult(
            status=STATUS_BUILD_FAIL,
            t_build=time.perf_counter() - t_start,
            t_solve=0.0,
            t_total=time.perf_counter() - t_start,
            error=f"CPLEX MIP build failed: {err_msg}",
            stats={"solver": "cplex-mip"},
        )

    # Step 2: Solve
    t_solve_start = time.perf_counter()
    try:
        sol = mp.solve(log_output=False)
        t_solve = time.perf_counter() - t_solve_start
    except Exception as e:
        err_msg = str(e)
        if "size limits" in err_msg or "1000 vars" in err_msg or "CPLEX code=1016" in err_msg:
            return SolverResult(
                status=STATUS_BLOCKED_LICENSE,
                t_build=t_build,
                t_solve=0.0,
                t_total=time.perf_counter() - t_start,
                error=f"CPLEX Community Edition limit exceeded: {err_msg}",
                stats={"solver": "cplex-mip", "reason": "COMMUNITY_EDITION_LIMIT"},
            )
        return SolverResult(
            status=STATUS_SOLVER_ERROR,
            t_build=t_build,
            t_solve=time.perf_counter() - t_solve_start,
            t_total=time.perf_counter() - t_start,
            error=f"CPLEX MIP solve error: {err_msg}",
            stats={"solver": "cplex-mip"},
        )

    solve_details = getattr(mp, "solve_details", None)
    solve_status = solve_details.status if solve_details else "unknown"
    stats: dict[str, Any] = {
        "solver": "cplex-mip",
        "cplex_status": solve_status,
        "threads": threads,
        "clues": n_clues,
    }

    if sol is not None:
        candidate = [0] * (N * N)
        for r in range(N):
            for c in range(N):
                for v in range(1, N + 1):
                    if sol.get_value(x[r, c, v]) > 0.5:
                        candidate[r * N + c] = v
                        break

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
                error=f"CPLEX MIP solution invalid: {val_res.reason} ({val_res.message})",
            )

        return SolverResult(
            status=STATUS_SOLVED_VALID,
            solution=candidate,
            t_build=t_build,
            t_solve=t_solve,
            t_total=t_total,
            stats=stats,
        )

    # If no solution was returned, check solve status
    if "infeasible" in solve_status.lower():
        return SolverResult(
            status=STATUS_UNSAT_INVESTIGATE,
            t_build=t_build,
            t_solve=t_solve,
            t_total=time.perf_counter() - t_start,
            stats=stats,
            error="CPLEX MIP reported infeasible on a puzzle derived from a valid solution",
        )
    elif "time limit" in solve_status.lower() or (timeout and t_solve >= timeout * 0.95):
        return SolverResult(
            status=STATUS_TIMEOUT,
            t_build=t_build,
            t_solve=t_solve,
            t_total=time.perf_counter() - t_start,
            stats=stats,
            error=f"CPLEX MIP timed out with status: {solve_status}",
        )

    return SolverResult(
        status=STATUS_SOLVER_ERROR,
        t_build=t_build,
        t_solve=t_solve,
        t_total=time.perf_counter() - t_start,
        stats=stats,
        error=f"CPLEX MIP returned no solution, status: {solve_status}",
    )
