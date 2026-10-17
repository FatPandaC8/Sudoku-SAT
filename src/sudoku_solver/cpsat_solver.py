"""OR-Tools CP-SAT baseline for Sudoku.

Each cell is an integer variable in ``1..N``; rows, columns, and subgrids
get ``AddAllDifferent`` constraints; givens are fixed with ``AddEquality``.

A ``FEASIBLE`` status is a proven solution, ``INFEASIBLE`` is a proven
no-solution, and anything else (``UNKNOWN`` / limit hit) is a timeout — a
timeout is never reported as unsatisfiable.
"""

from __future__ import annotations

import time

from .puzzle import EMPTY, Board, SolverResult, validate_solution

# OR-Tools status names -> our status vocabulary.
_STATUS_MAP = {
    "FEASIBLE": "solved",
    "OPTIMAL": "solved",
    "INFEASIBLE": "unsatisfiable",
}


def solve_cpsat(
    board: Board,
    time_limit: float | None = 10.0,
) -> SolverResult:
    """Solve ``board`` with CP-SAT.  ``time_limit`` is wall-clock seconds."""
    from ortools.sat.python import cp_model

    t0 = time.perf_counter()
    n = board.size
    k = board.k
    model = cp_model.CpModel()

    x = [[model.NewIntVar(1, n, f"x_{r}_{c}") for c in range(n)] for r in range(n)]

    for r in range(n):
        model.AddAllDifferent(x[r])
    for c in range(n):
        model.AddAllDifferent([x[r][c] for r in range(n)])
    for br in range(0, n, k):
        for bc in range(0, n, k):
            model.AddAllDifferent(
                [
                    x[r][c]
                    for r in range(br, br + k)
                    for c in range(bc, bc + k)
                ]
            )
    for r in range(n):
        for c in range(n):
            v = board.at(r, c)
            if v != EMPTY:
                model.Add(x[r][c] == v)

    solver = cp_model.CpSolver()
    if time_limit is not None:
        solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.log_search_progress = False

    try:
        status = solver.Solve(model)
    except Exception as exc:
        return SolverResult(
            status="error",
            runtime=time.perf_counter() - t0,
            error=f"CP-SAT execution failed: {exc}",
        )

    status_name = solver.StatusName(status)
    runtime = time.perf_counter() - t0
    stats = {
        "backend": "ortools-cpsat",
        "cpsat_status": status_name,
        "branches": solver.NumBranches(),
        "conflicts": solver.NumConflicts(),
        "wall_time": solver.WallTime(),
        "user_time": solver.UserTime(),
    }

    mapped = _STATUS_MAP.get(status_name)
    if mapped is None:
        # UNKNOWN, MODEL_INVALID, etc. — a limit hit is a timeout, never UNSAT.
        mapped = "timeout" if status_name in ("UNKNOWN", "MODEL_INVALID") else "error"

    if mapped != "solved":
        return SolverResult(status=mapped, runtime=runtime, stats=stats)

    cells = [[solver.Value(x[r][c]) for c in range(n)] for r in range(n)]
    result_board = Board(cells)
    problems = validate_solution(result_board, board)
    if problems:
        return SolverResult(
            status="error",
            runtime=runtime,
            stats=stats,
            error=f"CP-SAT returned an invalid solution: {problems}",
        )
    return SolverResult(status="solved", board=result_board, runtime=runtime, stats=stats)
