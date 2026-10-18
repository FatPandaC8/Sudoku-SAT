"""Gurobi MIP solver adapter for Sudoku with license limitation detection."""

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


def solve_gurobi(
    puzzle: Sequence[int],
    N: int,
    timeout: float | None = None,
    threads: int = 1,
) -> SolverResult:
    """Solve puzzle using Gurobi MIP (binary one-hot formulation)."""
    t_start = time.perf_counter()

    try:
        import gurobipy as gp
        from gurobipy import GRB
    except ImportError as e:
        return SolverResult(
            status=STATUS_SOLVER_ERROR,
            t_build=0.0,
            t_solve=0.0,
            t_total=time.perf_counter() - t_start,
            error=f"gurobipy not installed or import failed: {e}",
            stats={"solver": "gurobi-mip"},
        )

    # Step 1: Model Build
    try:
        t0 = time.perf_counter()
        box = math.isqrt(N)

        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 0)
        env.start()

        m = gp.Model("sudoku_gurobi", env=env)
        m.setParam("Threads", int(threads))
        if timeout is not None and timeout > 0:
            m.setParam("TimeLimit", float(timeout))

        x = m.addVars(N, N, range(1, N + 1), vtype=GRB.BINARY, name="x")

        # 1. Exactly one per cell
        for r in range(N):
            for c in range(N):
                m.addConstr(gp.quicksum(x[r, c, v] for v in range(1, N + 1)) == 1)

        # 2. Exactly one per row
        for r in range(N):
            for v in range(1, N + 1):
                m.addConstr(gp.quicksum(x[r, c, v] for c in range(N)) == 1)

        # 3. Exactly one per column
        for c in range(N):
            for v in range(1, N + 1):
                m.addConstr(gp.quicksum(x[r, c, v] for r in range(N)) == 1)

        # 4. Exactly one per box
        for br in range(box):
            for bc in range(box):
                for v in range(1, N + 1):
                    m.addConstr(
                        gp.quicksum(
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
                m.addConstr(x[r, c, val] == 1)
                n_clues += 1

        t_build = time.perf_counter() - t0

    except gp.GurobiError as e:
        err_msg = str(e)
        if "size-limited license" in err_msg or "Model too large" in err_msg:
            return SolverResult(
                status=STATUS_BLOCKED_LICENSE,
                t_build=time.perf_counter() - t_start,
                t_solve=0.0,
                t_total=time.perf_counter() - t_start,
                error=f"Gurobi size-limited license exceeded: {err_msg}",
                stats={"solver": "gurobi-mip", "reason": "RESTRICTED_LICENSE_LIMIT"},
            )
        return SolverResult(
            status=STATUS_BUILD_FAIL,
            t_build=time.perf_counter() - t_start,
            t_solve=0.0,
            t_total=time.perf_counter() - t_start,
            error=f"Gurobi model build failed: {err_msg}",
            stats={"solver": "gurobi-mip"},
        )
    except Exception as e:
        return SolverResult(
            status=STATUS_BUILD_FAIL,
            t_build=time.perf_counter() - t_start,
            t_solve=0.0,
            t_total=time.perf_counter() - t_start,
            error=f"Gurobi build error: {e}",
            stats={"solver": "gurobi-mip"},
        )

    # Step 2: Optimize
    t_solve_start = time.perf_counter()
    try:
        m.optimize()
        t_solve = time.perf_counter() - t_solve_start
    except gp.GurobiError as e:
        err_msg = str(e)
        if "size-limited license" in err_msg or "Model too large" in err_msg:
            return SolverResult(
                status=STATUS_BLOCKED_LICENSE,
                t_build=t_build,
                t_solve=0.0,
                t_total=time.perf_counter() - t_start,
                error=f"Gurobi size-limited license exceeded during optimize: {err_msg}",
                stats={"solver": "gurobi-mip", "reason": "RESTRICTED_LICENSE_LIMIT"},
            )
        return SolverResult(
            status=STATUS_SOLVER_ERROR,
            t_build=t_build,
            t_solve=time.perf_counter() - t_solve_start,
            t_total=time.perf_counter() - t_start,
            error=f"Gurobi optimize error: {err_msg}",
            stats={"solver": "gurobi-mip"},
        )

    stats: dict[str, Any] = {
        "solver": "gurobi-mip",
        "gurobi_status": m.status,
        "runtime_gurobi": getattr(m, "Runtime", t_solve),
        "node_count": getattr(m, "NodeCount", 0),
        "iter_count": getattr(m, "IterCount", 0),
        "threads": threads,
        "clues": n_clues,
    }

    if m.status == GRB.OPTIMAL:
        candidate = [0] * (N * N)
        for r in range(N):
            for c in range(N):
                for v in range(1, N + 1):
                    if x[r, c, v].X > 0.5:
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
                error=f"Gurobi solution invalid: {val_res.reason} ({val_res.message})",
            )

        return SolverResult(
            status=STATUS_SOLVED_VALID,
            solution=candidate,
            t_build=t_build,
            t_solve=t_solve,
            t_total=t_total,
            stats=stats,
        )

    elif m.status == GRB.INFEASIBLE:
        return SolverResult(
            status=STATUS_UNSAT_INVESTIGATE,
            t_build=t_build,
            t_solve=t_solve,
            t_total=time.perf_counter() - t_start,
            stats=stats,
            error="Gurobi reported INFEASIBLE on a puzzle derived from a valid solution",
        )

    elif m.status == GRB.TIME_LIMIT:
        return SolverResult(
            status=STATUS_TIMEOUT,
            t_build=t_build,
            t_solve=t_solve,
            t_total=time.perf_counter() - t_start,
            stats=stats,
            error="Gurobi reached time limit",
        )

    return SolverResult(
        status=STATUS_SOLVER_ERROR,
        t_build=t_build,
        t_solve=t_solve,
        t_total=time.perf_counter() - t_start,
        stats=stats,
        error=f"Gurobi returned unexpected status code: {m.status}",
    )
