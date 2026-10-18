"""CPLEX CP (CP Optimizer) solver adapter for Sudoku with Community Edition limit detection."""

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


def solve_cplex_cp(
    puzzle: Sequence[int],
    N: int,
    timeout: float | None = None,
    workers: int = 1,
) -> SolverResult:
    """Solve puzzle using CPLEX CP (CP Optimizer all_diff integer model)."""
    t_start = time.perf_counter()

    try:
        import docplex.cp.model as cpx_cp
    except ImportError as e:
        return SolverResult(
            status=STATUS_SOLVER_ERROR,
            t_build=0.0,
            t_solve=0.0,
            t_total=time.perf_counter() - t_start,
            error=f"docplex.cp not installed or import failed: {e}",
            stats={"solver": "cplex-cp"},
        )

    # Step 1: Model Build
    try:
        t0 = time.perf_counter()
        box = math.isqrt(N)

        cp_m = cpx_cp.CpoModel(name="sudoku_cplex_cp")
        vars_cp = [
            cp_m.integer_var(1, N, name=f"x_{r}_{c}")
            for r in range(N)
            for c in range(N)
        ]

        # Row all-different
        for r in range(N):
            cp_m.add(cpx_cp.all_diff([vars_cp[r * N + c] for c in range(N)]))

        # Column all-different
        for c in range(N):
            cp_m.add(cpx_cp.all_diff([vars_cp[r * N + c] for r in range(N)]))

        # Box all-different
        for br in range(box):
            for bc in range(box):
                cp_m.add(
                    cpx_cp.all_diff(
                        [
                            vars_cp[(br * box + r) * N + bc * box + c]
                            for r in range(box)
                            for c in range(box)
                        ]
                    )
                )

        # Clues
        n_clues = 0
        for i, val in enumerate(puzzle):
            if val != 0:
                cp_m.add(vars_cp[i] == val)
                n_clues += 1

        t_build = time.perf_counter() - t0

    except Exception as e:
        err_msg = str(e)
        if "size limit" in err_msg.lower() or "2^1000" in err_msg:
            return SolverResult(
                status=STATUS_BLOCKED_LICENSE,
                t_build=time.perf_counter() - t_start,
                t_solve=0.0,
                t_total=time.perf_counter() - t_start,
                error=f"CP Optimizer Community Edition limit exceeded: {err_msg}",
                stats={"solver": "cplex-cp", "reason": "COMMUNITY_EDITION_LIMIT"},
            )
        return SolverResult(
            status=STATUS_BUILD_FAIL,
            t_build=time.perf_counter() - t_start,
            t_solve=0.0,
            t_total=time.perf_counter() - t_start,
            error=f"CPLEX CP model build failed: {err_msg}",
            stats={"solver": "cplex-cp"},
        )

    # Step 2: Solve
    t_solve_start = time.perf_counter()
    solve_kwargs: dict[str, Any] = {
        "LogVerbosity": "Quiet",
        "Workers": int(workers),
    }
    if timeout is not None and timeout > 0:
        solve_kwargs["TimeLimit"] = float(timeout)

    try:
        msol = cp_m.solve(**solve_kwargs)
        t_solve = time.perf_counter() - t_solve_start
    except Exception as e:
        err_msg = str(e)
        if "size limit" in err_msg.lower() or "2^1000" in err_msg:
            return SolverResult(
                status=STATUS_BLOCKED_LICENSE,
                t_build=t_build,
                t_solve=0.0,
                t_total=time.perf_counter() - t_start,
                error=f"CP Optimizer Community Edition limit exceeded: {err_msg}",
                stats={"solver": "cplex-cp", "reason": "COMMUNITY_EDITION_LIMIT"},
            )
        return SolverResult(
            status=STATUS_SOLVER_ERROR,
            t_build=t_build,
            t_solve=time.perf_counter() - t_solve_start,
            t_total=time.perf_counter() - t_start,
            error=f"CP Optimizer solve error: {err_msg}",
            stats={"solver": "cplex-cp"},
        )

    solve_status = msol.get_solve_status()
    stats: dict[str, Any] = {
        "solver": "cplex-cp",
        "cplex_status": solve_status,
        "workers": workers,
        "clues": n_clues,
    }

    if solve_status in ("Feasible", "Optimal"):
        candidate = [int(msol[vars_cp[i]]) for i in range(N * N)]
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
                error=f"CPLEX CP solution failed validation: {val_res.reason} ({val_res.message})",
            )

        return SolverResult(
            status=STATUS_SOLVED_VALID,
            solution=candidate,
            t_build=t_build,
            t_solve=t_solve,
            t_total=t_total,
            stats=stats,
        )

    elif solve_status == "Infeasible":
        return SolverResult(
            status=STATUS_UNSAT_INVESTIGATE,
            t_build=t_build,
            t_solve=t_solve,
            t_total=time.perf_counter() - t_start,
            stats=stats,
            error="CPLEX CP reported Infeasible on a puzzle derived from a valid solution",
        )

    elif solve_status in ("Unknown", "JobFailed") or (timeout and t_solve >= timeout * 0.95):
        return SolverResult(
            status=STATUS_TIMEOUT,
            t_build=t_build,
            t_solve=t_solve,
            t_total=time.perf_counter() - t_start,
            stats=stats,
            error=f"CPLEX CP timed out or stopped with status: {solve_status}",
        )

    return SolverResult(
        status=STATUS_SOLVER_ERROR,
        t_build=t_build,
        t_solve=t_solve,
        t_total=time.perf_counter() - t_start,
        stats=stats,
        error=f"CPLEX CP returned status: {solve_status}",
    )
