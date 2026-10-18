"""Tests for Phase 2: SAT AMO encodings, solver adapters, and status handling."""

from __future__ import annotations

import math
from itertools import product
from pathlib import Path
import pytest
from pysat.solvers import Solver

from sudoku.solvers.base import (
    STATUS_BLOCKED_LICENSE,
    STATUS_INVALID_SOLUTION,
    STATUS_SOLVED_VALID,
    STATUS_TIMEOUT,
    STATUS_UNSAT_INVESTIGATE,
)
from sudoku.solvers.cplex_cp import solve_cplex_cp
from sudoku.solvers.cplex_mip import solve_cplex_mip
from sudoku.solvers.cpsat import solve_cpsat
from sudoku.solvers.gurobi import solve_gurobi
from sudoku.solvers.sat import (
    AMO_ENCODINGS,
    AuxAllocator,
    build_sudoku_cnf,
    estimate_encoding_clauses,
    solve_sat,
    var_id,
)
from sudoku.validator import is_valid_solution_for_puzzle


PRIMARY_MAX = 50


def check_amo_satisfiable(assignment: tuple[bool, ...], clauses: list[list[int]]) -> bool:
    assumptions = [(i + 1) if val else -(i + 1) for i, val in enumerate(assignment)]
    with Solver(name="minisat22", bootstrap_with=clauses) as s:
        return s.solve(assumptions=assumptions)


class TestAMOEncodingsExhaustive:
    @pytest.mark.parametrize("encoding", ["pairwise", "sequential", "binary", "commander", "product"])
    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8])
    def test_amo_exhaustive_truth_table(self, encoding: str, n: int):
        lits = list(range(1, n + 1))
        aux = AuxAllocator(PRIMARY_MAX)
        clauses = AMO_ENCODINGS[encoding](lits, aux)

        # Check aux variables never collide with primary
        all_lits = {abs(l) for cl in clauses for l in cl}
        aux_lits = all_lits - set(lits)
        assert all(v > PRIMARY_MAX for v in aux_lits), f"{encoding}: aux variable collision"

        # Check all 2^n assignments
        for assignment in product([False, True], repeat=n):
            n_true = sum(assignment)
            is_sat = check_amo_satisfiable(assignment, clauses)
            if n_true <= 1:
                assert is_sat, f"{encoding} failed to allow <=1 true for n={n}, assignment={assignment}"
            else:
                assert not is_sat, f"{encoding} failed to forbid >=2 true for n={n}, assignment={assignment}"

    def test_unknown_encoding_raises(self):
        with pytest.raises(ValueError):
            build_sudoku_cnf([0] * 16, 4, encoding="invalid_enc")

    def test_commander_group_size_validation(self):
        lits = [1, 2, 3, 4]
        aux = AuxAllocator(10)
        with pytest.raises(ValueError):
            AMO_ENCODINGS["commander"](lits, aux, opts={"commander_group_size": 1})


@pytest.fixture(scope="module")
def sample_9x9_puzzle():
    from sudoku.dataset import load_puzzles
    puzzles = load_puzzles("data/manifest.csv", sizes=9, ratios=0.5, index_range=(0, 1))
    return puzzles[0]


class TestSATSolverFullModel:

    @pytest.mark.parametrize("encoding", ["pairwise", "sequential", "binary", "commander", "product"])
    @pytest.mark.parametrize("backend", ["cadical153", "glucose4", "minisat22"])
    def test_sat_solve_all_encodings_and_backends(self, sample_9x9_puzzle, encoding: str, backend: str):
        res = solve_sat(
            puzzle=sample_9x9_puzzle["puzzle"],
            N=sample_9x9_puzzle["N"],
            encoding=encoding,
            backend=backend,
        )
        assert res.status == STATUS_SOLVED_VALID
        assert res.solution is not None
        assert is_valid_solution_for_puzzle(sample_9x9_puzzle["puzzle"], res.solution, 9).ok

    def test_contradictory_clues_reported_unsat(self, sample_9x9_puzzle):
        # Corrupt puzzle by placing two identical digits in row 0
        bad_puzzle = list(sample_9x9_puzzle["puzzle"])
        bad_puzzle[0] = 5
        bad_puzzle[1] = 5
        res = solve_sat(bad_puzzle, 9, encoding="sequential", backend="minisat22")
        assert res.status == STATUS_UNSAT_INVESTIGATE

    def test_pairwise_memory_safety_guard(self):
        from sudoku.bench.runner import BenchmarkConfig, execute_run_subprocess

        puzzle_rec = {
            "id": "guard_test",
            "N": 81,
            "requested_ratio": 0.3,
            "puzzle": [0] * (81 * 81),
        }
        res = execute_run_subprocess(
            puzzle_rec,
            BenchmarkConfig(solver="sat", encoding="pairwise", backend="cadical153"),
            memory_bytes_per_clause=1000.0,
        )
        assert res["status"] == "BUILD_FAIL"
        assert res["stats"]["reason"] == "RESOURCE_GUARD"
        assert res["stats"]["estimated_memory_bytes"] > res["stats"]["guard_threshold_bytes"]
        assert res["stats"]["available_ram_bytes"] == res["available_ram_bytes_at_start"]


class TestNonSATSolverAdapters:
    def test_cpsat_solver_on_n9(self, sample_9x9_puzzle):
        res = solve_cpsat(sample_9x9_puzzle["puzzle"], 9, timeout=10)
        assert res.status == STATUS_SOLVED_VALID
        assert res.solution is not None
        assert is_valid_solution_for_puzzle(sample_9x9_puzzle["puzzle"], res.solution, 9).ok

    def test_gurobi_solver_on_n9(self, sample_9x9_puzzle):
        res = solve_gurobi(sample_9x9_puzzle["puzzle"], 9, timeout=10)
        assert res.status == STATUS_SOLVED_VALID
        assert res.solution is not None
        assert is_valid_solution_for_puzzle(sample_9x9_puzzle["puzzle"], res.solution, 9).ok

    def test_cplex_mip_solver_on_n9(self, sample_9x9_puzzle):
        res = solve_cplex_mip(sample_9x9_puzzle["puzzle"], 9, timeout=10)
        assert res.status == STATUS_SOLVED_VALID
        assert res.solution is not None
        assert is_valid_solution_for_puzzle(sample_9x9_puzzle["puzzle"], res.solution, 9).ok

    def test_cplex_cp_solver_on_n9(self, sample_9x9_puzzle):
        res = solve_cplex_cp(sample_9x9_puzzle["puzzle"], 9, timeout=10)
        assert res.status == STATUS_SOLVED_VALID
        assert res.solution is not None
        assert is_valid_solution_for_puzzle(sample_9x9_puzzle["puzzle"], res.solution, 9).ok

    def test_commercial_license_limits_reported_cleanly(self):
        # N=36 exceeds Gurobi, CPLEX MIP, and CPLEX CP community limits
        puz_36 = [0] * (36 * 36)
        res_gurobi = solve_gurobi(puz_36, 36, timeout=5)
        assert res_gurobi.status == STATUS_BLOCKED_LICENSE

        res_cplex_mip = solve_cplex_mip(puz_36, 36, timeout=5)
        assert res_cplex_mip.status == STATUS_BLOCKED_LICENSE

        res_cplex_cp = solve_cplex_cp(puz_36, 36, timeout=5)
        assert res_cplex_cp.status == STATUS_BLOCKED_LICENSE
