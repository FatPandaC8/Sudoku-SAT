"""Tests for Phase 1 Sudoku validator."""

from __future__ import annotations

import math
import pytest

from sudoku.generator import generate_complete_grid
from sudoku.validator import (
    ValidationResult,
    is_valid_complete_grid,
    is_valid_puzzle,
    is_valid_solution_for_puzzle,
)


# Known-valid minimal grid for N=4 (box 2)
GRID_N4 = [
    1, 2, 3, 4,
    3, 4, 1, 2,
    2, 1, 4, 3,
    4, 3, 2, 1,
]

# Known-valid classic grid for N=9 (box 3)
GRID_N9 = [
    5, 3, 4, 6, 7, 8, 9, 1, 2,
    6, 7, 2, 1, 9, 5, 3, 4, 8,
    1, 9, 8, 3, 4, 2, 5, 6, 7,
    8, 5, 9, 7, 6, 1, 4, 2, 3,
    4, 2, 6, 8, 5, 3, 7, 9, 1,
    7, 1, 3, 9, 2, 4, 8, 5, 6,
    9, 6, 1, 5, 3, 7, 2, 8, 4,
    2, 8, 7, 4, 1, 9, 6, 3, 5,
    3, 4, 5, 2, 8, 6, 1, 7, 9,
]

# Known-valid base grid for N=16 (box 4)
def make_base_grid(N: int) -> list[int]:
    box = math.isqrt(N)
    return [(box * (r % box) + r // box + c) % N + 1 for r in range(N) for c in range(N)]


GRID_N16 = make_base_grid(16)


class TestValidatorAcceptance:
    def test_accepts_known_valid_grids(self):
        res4 = is_valid_complete_grid(GRID_N4, 4)
        assert res4.ok is True
        assert res4.reason == "OK"

        res9 = is_valid_complete_grid(GRID_N9, 9)
        assert res9.ok is True
        assert res9.reason == "OK"

        res16 = is_valid_complete_grid(GRID_N16, 16)
        assert res16.ok is True
        assert res16.reason == "OK"

    def test_accepts_generated_grids_n36_n81(self):
        import random
        rng = random.Random(12345)
        grid36 = generate_complete_grid(36, rng)
        res36 = is_valid_complete_grid(grid36, 36)
        assert res36.ok is True

        grid81 = generate_complete_grid(81, rng)
        res81 = is_valid_complete_grid(grid81, 81)
        assert res81.ok is True


class TestValidatorRejections:
    def test_rejects_row_duplicate(self):
        bad = list(GRID_N9)
        bad[1] = bad[0]  # row 0 has duplicate
        res = is_valid_complete_grid(bad, 9)
        assert res.ok is False
        assert res.reason == "ROW_DUP"

    def test_rejects_col_duplicate(self):
        bad = list(GRID_N9)
        bad[9] = bad[0]  # col 0 (row 1) equals col 0 (row 0)
        res = is_valid_complete_grid(bad, 9)
        assert res.ok is False
        assert res.reason in ("ROW_DUP", "COL_DUP")

        # Create duplicate strictly in column without row dup
        # Swap two distinct cells in row 1
        bad_col = list(GRID_N9)
        # Swap bad_col[9] (col 0, row 1) and bad_col[10] (col 1, row 1)
        bad_col[9], bad_col[10] = bad_col[10], bad_col[9]
        res_col = is_valid_complete_grid(bad_col, 9)
        assert res_col.ok is False
        assert res_col.reason in ("COL_DUP", "BOX_DUP")

    def test_rejects_box_duplicate(self):
        # Swap cells within row 0 and row 1 such that row counts are preserved but box has dups
        # Or construct explicit box duplicate on N=4
        bad = [
            1, 2, 3, 4,
            2, 1, 4, 3,  # box (0,0) has {1,2, 2,1} -> duplicate! but rows have {1,2,3,4}
            3, 4, 1, 2,
            4, 3, 2, 1,
        ]
        res = is_valid_complete_grid(bad, 4)
        assert res.ok is False
        assert res.reason == "BOX_DUP"

    def test_rejects_out_of_range(self):
        bad = list(GRID_N9)
        bad[0] = 10  # > 9
        res = is_valid_complete_grid(bad, 9)
        assert res.ok is False
        assert res.reason == "OUT_OF_RANGE"

        bad_neg = list(GRID_N9)
        bad_neg[0] = -1
        res_neg = is_valid_complete_grid(bad_neg, 9)
        assert res_neg.ok is False
        assert res_neg.reason == "OUT_OF_RANGE"

    def test_rejects_zero_in_complete_grid(self):
        bad = list(GRID_N9)
        bad[0] = 0
        res = is_valid_complete_grid(bad, 9)
        assert res.ok is False
        assert res.reason == "ZERO_IN_COMPLETE"

    def test_rejects_wrong_length(self):
        res_short = is_valid_complete_grid(GRID_N9[:-1], 9)
        assert res_short.ok is False
        assert res_short.reason == "BAD_LENGTH"

        res_long = is_valid_complete_grid(GRID_N9 + [1], 9)
        assert res_long.ok is False
        assert res_long.reason == "BAD_LENGTH"

    def test_rejects_non_int_and_bool_types(self):
        # Test bool (since bool inherits from int in Python, must be explicitly rejected)
        bad_bool = list(GRID_N9)
        bad_bool[0] = True
        res_bool = is_valid_complete_grid(bad_bool, 9)
        assert res_bool.ok is False
        assert res_bool.reason == "BAD_TYPE"

        # Test float
        bad_float = list(GRID_N9)
        bad_float[0] = 5.0
        res_float = is_valid_complete_grid(bad_float, 9)
        assert res_float.ok is False
        assert res_float.reason == "BAD_TYPE"

        # Test None and str
        bad_none = list(GRID_N9)
        bad_none[0] = None
        res_none = is_valid_complete_grid(bad_none, 9)
        assert res_none.ok is False
        assert res_none.reason == "BAD_TYPE"

        bad_str = list(GRID_N9)
        bad_str[0] = "5"
        res_str = is_valid_complete_grid(bad_str, 9)
        assert res_str.ok is False
        assert res_str.reason == "BAD_TYPE"

        # Non-sequence grid
        res_obj = is_valid_complete_grid("not a list", 9)
        assert res_obj.ok is False
        assert res_obj.reason == "BAD_TYPE"

    def test_rejects_non_square_n(self):
        res = is_valid_complete_grid([1] * 35, 35)
        assert res.ok is False
        assert res.reason == "NON_SQUARE_N"

        res_zero = is_valid_complete_grid([], 0)
        assert res_zero.ok is False
        assert res_zero.reason == "INVALID_N"


class TestPuzzleAndSolutionValidation:
    def test_is_valid_puzzle_success(self):
        solution = list(GRID_N4)
        puzzle = list(solution)
        puzzle[0] = 0
        puzzle[5] = 0
        res = is_valid_puzzle(puzzle, solution, 4)
        assert res.ok is True
        assert res.n_empty == 2

    def test_is_valid_puzzle_clue_mismatch(self):
        solution = list(GRID_N4)
        puzzle = list(solution)
        puzzle[0] = 3  # solution has 1
        res = is_valid_puzzle(puzzle, solution, 4)
        assert res.ok is False
        assert res.reason == "CLUE_MISMATCH"

    def test_is_valid_solution_for_puzzle_accepts_alternative_solution(self):
        # N=4 puzzle with clues that admit multiple solutions
        # Clues:
        # 1 . . .
        # . . . .
        # . . . .
        # . . . .
        puzzle = [
            1, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 0,
        ]
        # Candidate 1: standard GRID_N4 (has 1 at (0,0))
        cand1 = list(GRID_N4)
        assert cand1[0] == 1
        res1 = is_valid_solution_for_puzzle(puzzle, cand1, 4)
        assert res1.ok is True

        # Candidate 2: swap digits 2 and 3 in GRID_N4
        # Digit 1 remains at (0,0), digits 2 and 3 swap everywhere
        # This is a valid Sudoku grid and matches the clue puzzle[0] == 1,
        # but differs from cand1!
        swap_map = {1: 1, 2: 3, 3: 2, 4: 4}
        cand2 = [swap_map[v] for v in GRID_N4]
        assert cand2 != cand1
        assert cand2[0] == 1
        assert is_valid_complete_grid(cand2, 4).ok is True

        res2 = is_valid_solution_for_puzzle(puzzle, cand2, 4)
        assert res2.ok is True
        assert res2.reason == "OK"

    def test_is_valid_solution_for_puzzle_rejects_clue_violation(self):
        puzzle = [
            2, 0, 0, 0,  # demands 2 at cell 0
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 0,
        ]
        # GRID_N4 has 1 at cell 0, so it violates clue
        res = is_valid_solution_for_puzzle(puzzle, GRID_N4, 4)
        assert res.ok is False
        assert res.reason == "CLUE_MISMATCH"
