"""Sudoku grid and puzzle validator.

Provides fast, robust O(N^2) validation functions for flat row-major
Sudoku grids of size N = k^2 (k = isqrt(N)).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class ValidationResult:
    """Structured validation outcome.

    Attributes:
        ok: True if validation succeeded, False otherwise.
        reason: Short machine-readable code (e.g., 'OK', 'BAD_TYPE', 'BAD_LENGTH',
            'INVALID_N', 'NON_SQUARE_N', 'OUT_OF_RANGE', 'ZERO_IN_COMPLETE',
            'ROW_DUP', 'COL_DUP', 'BOX_DUP', 'CLUE_MISMATCH').
        message: Human-readable diagnostic message.
        n_empty: Number of empty cells counted (for puzzle validation).
    """

    ok: bool
    reason: str = "OK"
    message: str = ""
    n_empty: int = 0

    def __bool__(self) -> bool:
        return self.ok


def is_valid_complete_grid(grid: Any, N: int) -> ValidationResult:
    """Validate that `grid` is a complete, legal Sudoku grid of size `N`.

    Checks:
    - N is a positive integer and a perfect square (box = isqrt(N)).
    - grid is a list or tuple of length N*N.
    - Every element is strictly of type int (bools and floats rejected).
    - Every element is in the range 1..N (no zeros or out-of-range values).
    - Every row, column, and box contains each digit 1..N exactly once.

    Returns:
        ValidationResult indicating success or failure reason.
    """
    if type(N) is not int or N <= 0:
        return ValidationResult(
            ok=False, reason="INVALID_N", message=f"N must be a positive integer, got {N!r}"
        )

    box = math.isqrt(N)
    if box * box != N:
        return ValidationResult(
            ok=False,
            reason="NON_SQUARE_N",
            message=f"N={N} is not a perfect square (isqrt({N})={box})",
        )

    if not isinstance(grid, (list, tuple)):
        return ValidationResult(
            ok=False,
            reason="BAD_TYPE",
            message=f"grid must be a list or tuple, got {type(grid).__name__}",
        )

    expected_len = N * N
    if len(grid) != expected_len:
        return ValidationResult(
            ok=False,
            reason="BAD_LENGTH",
            message=f"grid length must be N^2={expected_len}, got {len(grid)}",
        )

    # Validate element types and ranges
    for i, x in enumerate(grid):
        if type(x) is not int:
            return ValidationResult(
                ok=False,
                reason="BAD_TYPE",
                message=f"cell {i} has invalid type {type(x).__name__}",
            )
        if x == 0:
            return ValidationResult(
                ok=False,
                reason="ZERO_IN_COMPLETE",
                message=f"complete grid contains empty cell (0) at index {i}",
            )
        if x < 1 or x > N:
            return ValidationResult(
                ok=False,
                reason="OUT_OF_RANGE",
                message=f"cell {i} value {x} out of range 1..{N}",
            )

    # Check rows: each must contain all digits 1..N
    for r in range(N):
        start = r * N
        row = grid[start : start + N]
        if len(set(row)) != N:
            return ValidationResult(
                ok=False,
                reason="ROW_DUP",
                message=f"duplicate value in row {r}",
            )

    # Check columns: each must contain all digits 1..N
    for c in range(N):
        seen: set[int] = set()
        for r in range(N):
            v = grid[r * N + c]
            if v in seen:
                return ValidationResult(
                    ok=False,
                    reason="COL_DUP",
                    message=f"duplicate value {v} in column {c}",
                )
            seen.add(v)

    # Check boxes: each box must contain all digits 1..N
    for br in range(box):
        for bc in range(box):
            seen_box: set[int] = set()
            for r in range(box):
                row_offset = (br * box + r) * N + bc * box
                for c in range(box):
                    v = grid[row_offset + c]
                    if v in seen_box:
                        return ValidationResult(
                            ok=False,
                            reason="BOX_DUP",
                            message=f"duplicate value {v} in box ({br}, {bc})",
                        )
                    seen_box.add(v)

    return ValidationResult(ok=True, reason="OK", message="Valid complete grid")


def is_valid_puzzle(puzzle: Any, solution: Any, N: int) -> ValidationResult:
    """Validate that `puzzle` is consistent with `solution` for size `N`.

    Checks:
    - `solution` is a valid complete grid of size `N`.
    - `puzzle` is a sequence of integers of length N*N.
    - Values of `puzzle` are in range 0..N.
    - Every non-zero cell of `puzzle` equals the corresponding cell in `solution`.
    - Zeros are the only difference.
    - Records the count of empty cells in `n_empty`.

    Returns:
        ValidationResult with `n_empty` on success or failure reason.
    """
    sol_res = is_valid_complete_grid(solution, N)
    if not sol_res.ok:
        return sol_res

    if not isinstance(puzzle, (list, tuple)):
        return ValidationResult(
            ok=False,
            reason="BAD_TYPE",
            message=f"puzzle must be a list or tuple, got {type(puzzle).__name__}",
        )

    expected_len = N * N
    if len(puzzle) != expected_len:
        return ValidationResult(
            ok=False,
            reason="BAD_LENGTH",
            message=f"puzzle length must be N^2={expected_len}, got {len(puzzle)}",
        )

    n_empty = 0
    for i, x in enumerate(puzzle):
        if type(x) is not int:
            return ValidationResult(
                ok=False,
                reason="BAD_TYPE",
                message=f"puzzle cell {i} has invalid type {type(x).__name__}",
            )
        if x < 0 or x > N:
            return ValidationResult(
                ok=False,
                reason="OUT_OF_RANGE",
                message=f"puzzle cell {i} value {x} out of range 0..{N}",
            )
        if x == 0:
            n_empty += 1
        else:
            sol_val = solution[i]
            if x != sol_val:
                r = i // N
                c = i % N
                return ValidationResult(
                    ok=False,
                    reason="CLUE_MISMATCH",
                    message=f"puzzle clue at ({r},{c}) has value {x}, but solution has {sol_val}",
                )

    return ValidationResult(
        ok=True,
        reason="OK",
        message="Puzzle is valid and consistent with reference solution",
        n_empty=n_empty,
    )


def is_valid_solution_for_puzzle(
    puzzle: Any, candidate: Any, N: int
) -> ValidationResult:
    """Validate that `candidate` is a valid complete grid AND matches every clue of `puzzle`.

    Note: This does NOT require `candidate` to equal any reference solution,
    as multiple valid solutions may exist for a puzzle.

    Returns:
        ValidationResult indicating success or failure reason.
    """
    cand_res = is_valid_complete_grid(candidate, N)
    if not cand_res.ok:
        return cand_res

    if not isinstance(puzzle, (list, tuple)):
        return ValidationResult(
            ok=False,
            reason="BAD_TYPE",
            message=f"puzzle must be a list or tuple, got {type(puzzle).__name__}",
        )

    expected_len = N * N
    if len(puzzle) != expected_len:
        return ValidationResult(
            ok=False,
            reason="BAD_LENGTH",
            message=f"puzzle length must be N^2={expected_len}, got {len(puzzle)}",
        )

    for i, p_val in enumerate(puzzle):
        if type(p_val) is not int:
            return ValidationResult(
                ok=False,
                reason="BAD_TYPE",
                message=f"puzzle cell {i} has invalid type {type(p_val).__name__}",
            )
        if p_val < 0 or p_val > N:
            return ValidationResult(
                ok=False,
                reason="OUT_OF_RANGE",
                message=f"puzzle cell {i} value {p_val} out of range 0..{N}",
            )
        if p_val != 0:
            c_val = candidate[i]
            if p_val != c_val:
                r = i // N
                c = i % N
                return ValidationResult(
                    ok=False,
                    reason="CLUE_MISMATCH",
                    message=(
                        f"clue mismatch at cell ({r},{c}): "
                        f"puzzle clue is {p_val}, but candidate has {c_val}"
                    ),
                )

    return ValidationResult(
        ok=True,
        reason="OK",
        message="Candidate is a valid solution matching all puzzle clues",
    )
