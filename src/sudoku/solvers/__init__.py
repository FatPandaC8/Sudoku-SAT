"""Sudoku solver adapters and benchmark solver interfaces."""

from .base import (
    STATUS_BLOCKED_LICENSE,
    STATUS_BUILD_FAIL,
    STATUS_INVALID_SOLUTION,
    STATUS_SOLVED_VALID,
    STATUS_SOLVER_ERROR,
    STATUS_TIMEOUT,
    STATUS_UNSAT_INVESTIGATE,
    VALID_STATUSES,
    SolverResult,
)
from .cplex_cp import solve_cplex_cp
from .cplex_mip import solve_cplex_mip
from .cpsat import solve_cpsat
from .gurobi import solve_gurobi
from .sat import (
    AMO_ENCODINGS,
    AuxAllocator,
    amo_binary,
    amo_commander,
    amo_pairwise,
    amo_product,
    amo_sequential,
    build_sudoku_cnf,
    estimate_encoding_clauses,
    solve_sat,
    var_id,
)

__all__ = [
    "SolverResult",
    "STATUS_SOLVED_VALID",
    "STATUS_TIMEOUT",
    "STATUS_UNSAT_INVESTIGATE",
    "STATUS_INVALID_SOLUTION",
    "STATUS_BUILD_FAIL",
    "STATUS_SOLVER_ERROR",
    "STATUS_BLOCKED_LICENSE",
    "VALID_STATUSES",
    "solve_sat",
    "solve_cpsat",
    "solve_gurobi",
    "solve_cplex_mip",
    "solve_cplex_cp",
    "build_sudoku_cnf",
    "estimate_encoding_clauses",
    "var_id",
    "AuxAllocator",
    "AMO_ENCODINGS",
    "amo_pairwise",
    "amo_sequential",
    "amo_binary",
    "amo_commander",
    "amo_product",
]
