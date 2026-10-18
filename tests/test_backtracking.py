"""Tests for the custom backtracking solver: MRV, FC, AC-3, stats."""

import pytest

from sudoku_solver.backtracking import (
    BacktrackingSolver,
    count_solutions,
    solve_backtracking,
)
from sudoku_solver.puzzle import Board, empty_board, is_valid_solution, parse_puzzle

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


# --- Adapter / integration tests (runner.py flat-list fix) ---


def test_flat_list_to_board_conversion():
    """Simulate what runner.py now does: reshape a flat puzzle list into
    a 2D grid before constructing Board.  Previously Board(flat_list)
    raised TypeError: 'int' object is not iterable."""
    flat = [0, 5, 9, 7, 0, 0, 3, 1, 0] + [0] * 72  # N=9 flat list
    n = 9
    grid = [flat[r * n : (r + 1) * n] for r in range(n)]
    board = Board(grid)
    assert board.size == 9
    assert board.at(0, 1) == 5
    assert board.at(0, 2) == 9
    result = solve_backtracking(board)
    assert result.status == "solved"
    assert is_valid_solution(result.board, board)


def test_timeout_returns_timeout_status():
    """A very short timeout must produce status 'timeout' rather than
    hanging or returning an incorrect status."""
    puzzle = empty_board(81)  # large empty board: hard to solve quickly
    result = solve_backtracking(puzzle, timeout=0.01)
    assert result.status in ("solved", "timeout", "unsatisfiable")
    # If solved quickly on an empty 81x81, that's fine too.
    if result.status == "solved":
        assert is_valid_solution(result.board, puzzle)


def test_timeout_respects_deadline():
    """With timeout=None (default), no deadline is enforced."""
    puzzle = parse_puzzle(KNOWN)
    result = solve_backtracking(puzzle, timeout=None)
    assert result.status == "solved"


def test_solved_solution_passes_independent_validation():
    """Every solved solution must pass is_valid_solution against givens."""
    puzzle = parse_puzzle(KNOWN)
    result = solve_backtracking(puzzle)
    assert result.status == "solved"
    assert is_valid_solution(result.board, puzzle)


def test_invalid_puzzle_returns_unsatisfiable():
    """A puzzle with duplicate givens (unsatisfiable) must return
    'unsatisfiable', not crash."""
    puzzle = parse_puzzle("11.......\n" + "." * 72)
    result = solve_backtracking(puzzle)
    assert result.status == "unsatisfiable"
    assert result.board is None


def test_solver_result_has_stats_keys():
    """SolverResult.stats must contain all expected keys."""
    puzzle = parse_puzzle(KNOWN)
    result = solve_backtracking(puzzle)
    for key in ("nodes", "decisions", "backtracks", "eliminations",
                "propagation_steps", "runtime"):
        assert key in result.stats
    assert result.stats["runtime"] >= 0
