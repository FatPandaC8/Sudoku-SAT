"""Generic Sudoku puzzle generation for any N = k^2.

Pipeline: randomized complete grid -> clue removal in randomized order ->
uniqueness check after every removal -> stop at target or budget.

No suitable third-party generator supports arbitrary N=k^2 sizes with clue
removal and uniqueness checks, so the smallest practical generic generator is
implemented here, reusing :mod:`sudoku_solver.backtracking` for solution
counting (early-stopping at two solutions).

Difficulty
----------
``easy`` / ``medium`` / ``hard`` are *presets* that set a clue-removal target
(fraction of cells emptied).  Clue count alone does not prove difficulty, so
every puzzle also gets a deterministic ``difficulty_score``: the number of
search nodes visited by the reference solver (MRV + forward checking,
deterministic tie-breaking, no AC-3) on that puzzle.  Higher = more search
effort.  For a fixed puzzle and configuration the score is reproducible.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Callable, NamedTuple

from .backtracking import BacktrackingSolver
from .puzzle import (
    EMPTY,
    Board,
    format_puzzle,
    is_valid_size,
    validate_partial,
    validate_solution,
)

# Fraction of cells that are EMPTIED, per difficulty preset (initial target).
DIFFICULTY_PRESETS: dict[str, float] = {
    "easy": 0.45,
    "medium": 0.55,
    "hard": 0.65,
}

# Board sizes above this threshold use the SAT-based solution counter for
# uniqueness checks: PySAT is dramatically faster than backtracking on the
# sparse boards produced during clue removal for large N.
_SAT_COUNTER_THRESHOLD = 13


def _make_counter(size: int) -> tuple[Callable[[Board, int], int], Callable[[], None]]:
    """Return ``(count_fn, cleanup_fn)`` appropriate for ``size``.

    Backtracking is used for small boards (fast, low overhead); for larger
    boards the SAT-based counter is used because backtracking search explodes
    on sparse large grids.  The SAT counter builds its base CNF once and is
    reused across all clue-removal checks; ``cleanup`` releases the solver.
    """
    if size <= _SAT_COUNTER_THRESHOLD:
        def _bt_counter(board: Board, max_solutions: int) -> int:
            return BacktrackingSolver(board).count_solutions(max_solutions)
        return _bt_counter, lambda: None
    from .sat_solver import SatCounter
    counter = SatCounter(size)
    return counter.count, counter.delete


class GenerationError(RuntimeError):
    """Raised when no valid uniquely-solvable puzzle could be produced."""


class GeneratedPuzzle(NamedTuple):
    puzzle: Board
    solution: Board
    metadata: dict


def _complete_grid(size: int, rng: random.Random) -> Board:
    """Build a complete valid grid via randomized backtracking."""
    empty = Board([[EMPTY] * size for _ in range(size)])
    solver = BacktrackingSolver(
        empty, randomize=True, seed=rng.randrange(2**31)
    )
    result = solver.solve()
    if result.status != "solved" or result.board is None:
        raise GenerationError("failed to build a complete grid")
    return result.board


def difficulty_score(puzzle: Board) -> int:
    """Deterministic effort estimate.

    For small boards (N <= 12) the score is the number of search nodes visited
    by the reference backtracking solver (MRV + forward checking, no AC-3,
    deterministic tie-breaking).  For larger boards backtracking on the sparse
    generated puzzles is intractable, so the score is the number of SAT
    conflicts reported by PySAT (pairwise encoding, minisat22) when solving
    the same puzzle — a comparable measure of search effort that scales.
    """
    if puzzle.size <= 12:
        solver = BacktrackingSolver(puzzle)  # deterministic configuration
        solver.solve()
        return solver.stats.nodes
    from .sat_solver import solve_sat
    result = solve_sat(puzzle, encoding="pairwise", backend="minisat22")
    return int(result.stats.get("conflicts") or 0)


def _count_solutions_for(size: int, board: Board, max_solutions: int = 2) -> int:
    """Uniqueness counter chosen by board size (BT for small, SAT for large).

    Convenience wrapper that creates and tears down a counter per call.
    """
    count_fn, cleanup = _make_counter(size)
    try:
        return count_fn(board, max_solutions)
    finally:
        cleanup()


def generate(
    size: int = 9,
    difficulty: str = "easy",
    seed: int | None = None,
    timeout: float | None = 30.0,
    max_passes: int = 4,
) -> GeneratedPuzzle:
    """Generate a unique-solution puzzle.

    Returns ``(puzzle, solution, metadata)``.  The puzzle is always valid and
    uniquely solvable; ``metadata['target_reached']`` says whether the clue
    target was hit before ``timeout`` seconds elapsed (actual clue count and
    difficulty score are always recorded).  Raises :class:`GenerationError`
    only when no valid unique puzzle could be produced at all.
    ``max_passes`` bounds how many random-removal passes are attempted when
    the clue target is not reached in a single pass.
    """
    if not is_valid_size(size):
        raise ValueError(f"size {size} is not a valid Sudoku size (k^2, k >= 2)")
    if difficulty not in DIFFICULTY_PRESETS:
        raise ValueError(
            f"unknown difficulty {difficulty!r}; "
            f"choose from {sorted(DIFFICULTY_PRESETS)}"
        )
    t0 = time.perf_counter()
    rng = random.Random(seed)
    solution = _complete_grid(size, rng)
    puzzle = solution.copy()
    target_clues = round(size * size * (1 - DIFFICULTY_PRESETS[difficulty]))
    count_solutions, cleanup_counter = _make_counter(size)

    cells = [(r, c) for r in range(size) for c in range(size)]
    removals = 0
    target_reached = False
    try:
        for _pass in range(max_passes):
            rng.shuffle(cells)
            removed_this_pass = 0
            for (r, c) in cells:
                if puzzle.at(r, c) == EMPTY:
                    continue
                if puzzle.clue_count() <= target_clues:
                    target_reached = True
                    break
                if timeout is not None and time.perf_counter() - t0 > timeout:
                    break
                saved = puzzle.at(r, c)
                puzzle.set(r, c, EMPTY)
                if count_solutions(puzzle, 2) == 1:
                    removals += 1
                    removed_this_pass += 1
                else:
                    puzzle.set(r, c, saved)  # not unique (or unsat): restore
            if target_reached or removed_this_pass == 0:
                break
    finally:
        cleanup_counter()
    # The removal that hits the target may occur on the last cell of a pass.
    if puzzle.clue_count() <= target_clues:
        target_reached = True

    elapsed = time.perf_counter() - t0
    # Final guarantees: valid, unique, and the original grid is THE solution.
    problems = validate_partial(puzzle)
    if problems:
        raise GenerationError(f"generated puzzle is invalid: {problems}")
    count_solutions2, cleanup2 = _make_counter(size)
    try:
        if count_solutions2(puzzle, 2) != 1:
            raise GenerationError("generated puzzle does not have a unique solution")
    finally:
        cleanup2()
    if validate_solution(solution, puzzle):
        raise GenerationError(
            f"known solution violates the puzzle's givens: "
            f"{validate_solution(solution, puzzle)}"
        )
    # Reaching the clue target is best-effort: when the budget runs out first,
    # the puzzle is still returned (valid and unique) with target_reached=False
    # and the actual clue count recorded.  Failure is only raised when no
    # valid unique puzzle could be produced at all (above).

    metadata = {
        "size": size,
        "difficulty": difficulty,
        "seed": seed,
        "clue_count": puzzle.clue_count(),
        "target_clues": target_clues,
        "target_reached": target_reached,
        "removals": removals,
        "unique": True,
        "difficulty_score": difficulty_score(puzzle),
        "generation_time": elapsed,
    }
    return GeneratedPuzzle(puzzle, solution, metadata)


def puzzle_filename(size: int, difficulty: str, index: int, seed: int) -> str:
    return f"{size}x{size}_{difficulty}_{index:03d}_seed{seed}.json"


def save_puzzle(
    out_dir,
    size: int,
    difficulty: str,
    index: int,
    gen: GeneratedPuzzle,
) -> str:
    """Persist one generated puzzle as JSON; returns the file path."""
    puzzle, solution, metadata = gen
    directory = Path(out_dir) / f"{size}x{size}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / puzzle_filename(
        size, difficulty, index, int(metadata.get("seed") or 0)
    )
    record = {
        "puzzle_id": path.stem,
        "size": size,
        "difficulty": difficulty,
        "index": index,
        "puzzle": format_puzzle(puzzle),
        "solution": format_puzzle(solution),
        "metadata": metadata,
    }
    path.write_text(json.dumps(record, indent=2))
    return str(path)


def load_puzzle(path):
    """Load a puzzle record saved by :func:`save_puzzle`."""
    from .puzzle import parse_puzzle

    record = json.loads(Path(path).read_text())
    return (
        parse_puzzle(record["puzzle"]),
        parse_puzzle(record["solution"]),
        record,
    )


def load_dataset(root, size: int | None = None, difficulty: str | None = None):
    """Yield ``(puzzle, solution, record)`` for every saved puzzle file."""
    root = Path(root)
    dirs = sorted(root.glob("*x*")) if size is None else [root / f"{size}x{size}"]
    for d in dirs:
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            puzzle, solution, record = load_puzzle(path)
            if size is not None and record["size"] != size:
                continue
            if difficulty is not None and record["difficulty"] != difficulty:
                continue
            yield puzzle, solution, record

