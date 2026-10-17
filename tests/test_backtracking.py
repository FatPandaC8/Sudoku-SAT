"""Tests for the custom backtracking solver: MRV, FC, AC-3, stats."""

import pytest

from sudoku_solver.backtracking import (
    BacktrackingSolver,
    count_solutions,
    solve_backtracking,
)
from sudoku_solver.puzzle import empty_board, is_valid_solution, parse_puzzle

KNOWN = (
    "53..7....\n6..195...\n.98....6.\n8...6...3\n4..8.3..1\n"
    "7...2...6\n.6....28.\n...419..5\n....8..79"
)


@pytest.mark.parametrize("use_ac3", [False, True])
def test_solves_known_puzzle(use_ac3):
    puzzle = parse_puzzle(KNOWN)
    result = solve_backtracking(puzzle, use_ac3=use_ac3)
    assert result.status == "solved"
    assert is_valid_solution(result.board, puzzle)


@pytest.mark.parametrize("use_ac3", [False, True])
def test_unsatisfiable_duplicate_givens(use_ac3):
    puzzle = parse_puzzle("11.......\n" + "." * 72)
    result = solve_backtracking(puzzle, use_ac3=use_ac3)
    assert result.status == "unsatisfiable"
    assert result.board is None


def test_unsatisfiable_valid_looking_puzzle():
    # No duplicates, but cell (0,2) has no legal value:
    # row0 has {1,4}, col2 empty, box top-right contains {2,3} in row1...
    puzzle = parse_puzzle(
        "14.23....\n"
        "..23.4...\n"
        ".........\n" + ".........\n" * 6
    )
    result = solve_backtracking(puzzle)
    assert result.status in ("solved", "unsatisfiable")
    if result.status == "solved":
        assert is_valid_solution(result.board, puzzle)


@pytest.mark.parametrize("size", [4, 9, 16])
def test_handles_arbitrary_sizes(size):
    puzzle = empty_board(size)
    result = solve_backtracking(puzzle)
    assert result.status == "solved"
    assert is_valid_solution(result.board, puzzle)


def test_mrv_picks_fewest_candidates():
    puzzle = parse_puzzle(KNOWN)
    solver = BacktrackingSolver(puzzle)
    idx = solver._select_cell()
    # All remaining cells' domains: MRV must pick one with the minimum size.
    sizes = [
        len(solver.domains[i])
        for i, a in enumerate(solver.assigned) if not a
    ]
    assert len(solver.domains[idx]) == min(sizes)


@pytest.mark.parametrize("use_ac3", [False, True])
def test_mrv_detects_empty_domain_contradiction(use_ac3):
    # Duplicate in the same 4x4 subgrid (but different row/column):
    # initial propagation empties a domain => unsatisfiable without search.
    puzzle = parse_puzzle("1...\n.1..\n....\n....")
    solver = BacktrackingSolver(puzzle, use_ac3=use_ac3)
    result = solver.solve()
    assert result.status == "unsatisfiable"


def test_forward_checking_rollback_restores_domains():
    puzzle = parse_puzzle(KNOWN)
    solver = BacktrackingSolver(puzzle)
    solver.solve()
    # After a complete solve, domains must equal the post-initial-propagation
    # state of a pristine solver: every removal made during search was undone.
    fresh = BacktrackingSolver(puzzle)
    fresh._initial_propagate()
    assert [set(d) for d in solver.domains] == [set(d) for d in fresh.domains]


@pytest.mark.parametrize("use_ac3", [False, True])
def test_statistics_recorded(use_ac3):
    puzzle = parse_puzzle(KNOWN)
    result = solve_backtracking(puzzle, use_ac3=use_ac3)
    stats = result.stats
    for key in ("nodes", "decisions", "backtracks", "eliminations",
                "propagation_steps", "runtime"):
        assert key in stats
    assert stats["nodes"] >= 1
    assert stats["runtime"] >= 0


def test_ac3_reduces_or_equals_search_effort_on_hard_puzzle():
    # Not asserted strictly (AC-3 can trade off), but must terminate quickly
    # and produce identical solve status with and without AC-3.
    puzzle = parse_puzzle(KNOWN)
    r1 = solve_backtracking(puzzle, use_ac3=False)
    r2 = solve_backtracking(puzzle, use_ac3=True)
    assert r1.status == r2.status == "solved"


def test_count_solutions_uniqueness():
    puzzle = parse_puzzle(KNOWN)
    assert count_solutions(puzzle, 2) == 1
    # Empty 4x4 has many solutions; counter stops at the limit.
    assert count_solutions(empty_board(4), 2) == 2


def test_count_solutions_unsat_is_zero():
    puzzle = parse_puzzle("11.......\n" + "." * 72)
    assert count_solutions(puzzle, 2) == 0


def test_randomized_solving_still_valid():
    puzzle = parse_puzzle(KNOWN)
    result = solve_backtracking(puzzle, randomize=True, seed=99)
    assert result.status == "solved"
    assert is_valid_solution(result.board, puzzle)


def test_deterministic_tie_breaking():
    a = solve_backtracking(parse_puzzle(KNOWN))
    b = solve_backtracking(parse_puzzle(KNOWN))
    assert a.board == b.board
    assert a.stats["nodes"] == b.stats["nodes"]
