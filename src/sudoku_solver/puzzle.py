"""Core Sudoku board model: representation, parsing, symbol conversion, validation.

Boards are ``N x N`` integer matrices with ``N = k^2``:
``0`` marks an empty cell, ``1..N`` are the symbols.  All solvers consume this
representation; symbols are converted only at file boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EMPTY = 0

# External alphabet: digits, then uppercase letters, then lowercase letters.
# Covers values 1..61, which is enough for every N = k^2 up to 61x61
# (k=7 -> N=49, k=8 -> N=64 needs 64 symbols, beyond this alphabet).
_ALPHABET = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
# Characters accepted for empty cells in external formats.
_EMPTY_CHARS = ".0"


class PuzzleError(ValueError):
    """Raised for malformed boards, parses, or symbol conversions."""


def is_valid_size(n: int) -> bool:
    """Return True iff ``n`` is a perfect square >= 4 (so k >= 2)."""
    if n < 4:
        return False
    k = int(n**0.5)
    return k * k == n


def subgrid_dims(n: int) -> int:
    """Return ``k`` such that the board is made of ``k x k`` subgrids."""
    if not is_valid_size(n):
        raise PuzzleError(f"board size {n} is not a square k^2 with k >= 2")
    return int(n**0.5)


def symbol_for(value: int) -> str:
    """Map an internal value ``1..N`` to its external symbol."""
    if value < 1 or value >= len(_ALPHABET) + 1:
        raise PuzzleError(f"value {value} out of symbol alphabet range")
    return _ALPHABET[value - 1]


def value_for(symbol: str) -> int:
    """Map an external symbol back to an internal value ``1..N``."""
    idx = _ALPHABET.find(symbol)
    if idx < 0:
        raise PuzzleError(f"unknown symbol {symbol!r}")
    return idx + 1


@dataclass
class Board:
    """An ``N x N`` Sudoku board backed by a list of row lists."""

    cells: list[list[int]]

    def __post_init__(self) -> None:
        self.cells = [list(row) for row in self.cells]

    @property
    def size(self) -> int:
        return len(self.cells)

    @property
    def k(self) -> int:
        return subgrid_dims(self.size)

    def copy(self) -> "Board":
        return Board([row[:] for row in self.cells])

    def at(self, r: int, c: int) -> int:
        return self.cells[r][c]

    def set(self, r: int, c: int, v: int) -> None:
        self.cells[r][c] = v

    def rows(self) -> list[list[int]]:
        return self.cells

    def cols(self) -> list[list[int]]:
        n = self.size
        return [[self.cells[r][c] for r in range(n)] for c in range(n)]

    def subgrids(self) -> list[list[int]]:
        n, k = self.size, self.k
        out = []
        for br in range(0, n, k):
            for bc in range(0, n, k):
                out.append(
                    [
                        self.cells[r][c]
                        for r in range(br, br + k)
                        for c in range(bc, bc + k)
                    ]
                )
        return out

    def empty_cells(self) -> list[tuple[int, int]]:
        return [
            (r, c)
            for r in range(self.size)
            for c in range(self.size)
            if self.cells[r][c] == EMPTY
        ]

    def clue_count(self) -> int:
        return sum(1 for row in self.cells for v in row if v != EMPTY)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Board) and self.cells == other.cells


def empty_board(n: int) -> Board:
    if not is_valid_size(n):
        raise PuzzleError(f"board size {n} is not a square k^2 with k >= 2")
    return Board([[EMPTY] * n for _ in range(n)])


def parse_puzzle(text: str) -> Board:
    """Parse a puzzle from text.

    Accepts rows of length ``N`` separated by newlines (whitespace ignored),
    or a single run of ``N^2`` symbols.  Empty cells are ``.`` or ``0``.
    """
    stripped = [ln for ln in text.splitlines() if ln.strip()]
    joined = "".join(stripped).replace(" ", "")
    if not joined:
        raise PuzzleError("empty puzzle text")
    total = len(joined)
    size = int(total**0.5)
    if size * size != total:
        raise PuzzleError(f"{total} symbols is not a square number")
    if not is_valid_size(size):
        raise PuzzleError(f"parsed size {size} is not a valid Sudoku size")
    vals = [EMPTY if ch in _EMPTY_CHARS else value_for(ch) for ch in joined]
    for v in vals:
        if v > size:
            raise PuzzleError(f"value {v} exceeds board size {size}")
    cells = [vals[r * size : (r + 1) * size] for r in range(size)]
    return Board(cells)


def format_puzzle(board: Board, empty: str = ".") -> str:
    """Serialize a board with one symbol per cell (``empty`` for blanks)."""
    return "\n".join(
        "".join(empty if v == EMPTY else symbol_for(v) for v in row)
        for row in board.cells
    )


def _check_group(group: list[int], size: int) -> list[int]:
    """Return duplicate/out-of-range nonzero symbols in a group."""
    seen: set[int] = set()
    dups: set[int] = set()
    for v in group:
        if v == EMPTY:
            continue
        if v < 1 or v > size or v in seen:
            dups.add(v)
        seen.add(v)
    return sorted(dups)


def validate_partial(board: Board) -> list[str]:
    """Validate a (possibly partial) puzzle.  Returns a list of problems."""
    problems: list[str] = []
    n = board.size
    if not is_valid_size(n):
        problems.append(f"invalid board size {n}")
        return problems
    for r, row in enumerate(board.cells):
        if len(row) != n:
            problems.append(f"row {r} has length {len(row)}, expected {n}")
            return problems
    for r, row in enumerate(board.cells):
        for c, v in enumerate(row):
            if v < 0 or v > n:
                problems.append(f"cell ({r},{c}) has out-of-range value {v}")
    if problems:
        return problems
    for i, group in enumerate(board.rows()):
        dups = _check_group(group, n)
        if dups:
            problems.append(f"row {i} has duplicate/out-of-range values {dups}")
    for i, group in enumerate(board.cols()):
        dups = _check_group(group, n)
        if dups:
            problems.append(f"column {i} has duplicate/out-of-range values {dups}")
    for i, group in enumerate(board.subgrids()):
        dups = _check_group(group, n)
        if dups:
            problems.append(f"subgrid {i} has duplicate/out-of-range values {dups}")
    return problems


def validate_solution(board: Board, givens: Board | None = None) -> list[str]:
    """Validate a completed solution; optionally check givens are preserved."""
    problems = validate_partial(board)
    if problems:
        return problems
    empties = board.empty_cells()
    if empties:
        problems.append(f"solution has {len(empties)} empty cells")
        return problems
    if givens is not None:
        if givens.size != board.size:
            problems.append("givens board size mismatch")
            return problems
        for r in range(board.size):
            for c in range(board.size):
                g = givens.at(r, c)
                if g != EMPTY and board.at(r, c) != g:
                    problems.append(
                        f"given at ({r},{c}) changed: {g} -> {board.at(r, c)}"
                    )
    return problems


def is_valid_solution(board: Board, givens: Board | None = None) -> bool:
    return not validate_solution(board, givens)


@dataclass
class SolverResult:
    """Common result structure returned by every solver."""

    status: str  # "solved" | "unsatisfiable" | "timeout" | "error"
    board: Board | None = None
    runtime: float = 0.0
    stats: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def solved(self) -> bool:
        return self.status == "solved" and self.board is not None

