"""Base definitions and result schema for Sudoku solver adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


# Standard solver status vocabulary according to benchmark plan
STATUS_SOLVED_VALID = "SOLVED_VALID"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_UNSAT_INVESTIGATE = "UNSAT_INVESTIGATE"
STATUS_INVALID_SOLUTION = "INVALID_SOLUTION"
STATUS_BUILD_FAIL = "BUILD_FAIL"
STATUS_SOLVER_ERROR = "SOLVER_ERROR"
STATUS_BLOCKED_LICENSE = "BLOCKED_LICENSE"
STATUS_RESOURCE_GUARD_LIVE = "RESOURCE_GUARD_LIVE"

VALID_STATUSES = {
    STATUS_SOLVED_VALID,
    STATUS_TIMEOUT,
    STATUS_UNSAT_INVESTIGATE,
    STATUS_INVALID_SOLUTION,
    STATUS_BUILD_FAIL,
    STATUS_SOLVER_ERROR,
    STATUS_BLOCKED_LICENSE,
    STATUS_RESOURCE_GUARD_LIVE,
}


@dataclass
class SolverResult:
    """Standard result structure returned by all solvers.

    Attributes:
        status: One of SOLVED_VALID, TIMEOUT, UNSAT_INVESTIGATE,
                INVALID_SOLUTION, BUILD_FAIL, SOLVER_ERROR, BLOCKED_LICENSE.
        solution: Flat row-major list of length N*N (or None if unsolved).
        t_build: Model construction time in seconds.
        t_solve: Pure solve time reported by or measured for the solver in seconds.
        t_total: Total end-to-end time (t_build + t_solve + extraction/validation).
        peak_rss_mb: Peak resident set size of process in MB (if measured).
        stats: Diagnostic statistics (variable counts, constraints, conflicts, etc.).
        error: Diagnostic error message if failed, blocked, or invalid.
    """

    status: str
    solution: list[int] | None = None
    t_build: float = 0.0
    t_solve: float = 0.0
    t_total: float = 0.0
    peak_rss_mb: float | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Unknown status {self.status!r}; choose from {sorted(VALID_STATUSES)}")

    @property
    def is_solved(self) -> bool:
        return self.status == STATUS_SOLVED_VALID and self.solution is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "solution": self.solution,
            "t_build": round(self.t_build, 6),
            "t_solve": round(self.t_solve, 6),
            "t_total": round(self.t_total, 6),
            "peak_rss_mb": self.peak_rss_mb,
            "stats": self.stats,
            "error": self.error,
        }
