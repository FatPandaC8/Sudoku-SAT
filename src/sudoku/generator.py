"""Sudoku puzzle generator using deterministic seeded validity-preserving shuffles.

Algorithm:
1. Construct base pattern: (box * (r % box) + r // box + c) % N + 1.
2. Apply seeded validity-preserving transformations:
   - Row permutation within each band
   - Column permutation within each stack
   - Band permutation
   - Stack permutation
   - Transposition (optional, conditioned on RNG)
   - Digit relabeling (random symbol permutation)
3. Validate complete grid with `is_valid_complete_grid`.
4. Clue removal:
   - n_remove = floor(ratio * N^2 + 0.5) (round half up)
   - Sample n_remove cells to empty using per-puzzle seeded RNG.
   - Sort removed indices for stable storage.

Limitations:
- This method is extremely fast and produces strictly valid Sudoku grids for
  any size N = k^2, but does NOT sample uniformly from the space of all valid
  Sudoku grids. It samples from the automorphism equivalence orbit of the
  standard base pattern.
- Generated puzzles are NOT guaranteed to possess unique solutions; any valid
  completion matching the clues counts as a correct solver solution.
- The removal ratio is an experimental condition factor, not a difficulty label.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any

from .validator import is_valid_complete_grid, is_valid_puzzle

GENERATOR_VERSION = "gen-v1"


def round_half_up(val: float) -> int:
    """Round half up: math.floor(val + 0.5).

    Unlike Python's built-in round() which performs banker's rounding (round half to even),
    this strictly rounds 0.5 up towards positive infinity.
    """
    return math.floor(val + 0.5)


def make_puzzle_seed(base_seed: int, N: int, ratio: float, index: int) -> int:
    """Derive deterministic 64-bit unsigned integer seed for a specific puzzle.

    Formula:
        first 8 bytes (big-endian, unsigned) of SHA-256(f"{base_seed}|{N}|{ratio:.1f}|{index}")
    """
    key = f"{base_seed}|{N}|{ratio:.1f}|{index}".encode("utf-8")
    digest = hashlib.sha256(key).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def puzzle_id_for(N: int, ratio: float, index: int) -> str:
    """Return canonical puzzle identifier: sudoku_N{N:03d}_r{ratio:.1f}_i{index:03d}."""
    return f"sudoku_N{N:03d}_r{ratio:.1f}_i{index:03d}"


def canonical_content_json(puzzle_id: str, N: int, puzzle: list[int], solution: list[int]) -> str:
    """Return canonical JSON string (sorted keys, no whitespace) of {id, N, puzzle, solution}."""
    payload = {
        "N": N,
        "id": puzzle_id,
        "puzzle": puzzle,
        "solution": solution,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute_content_sha256(puzzle_id: str, N: int, puzzle: list[int], solution: list[int]) -> str:
    """Return SHA-256 hex digest of canonical JSON serialization of puzzle content."""
    canonical_str = canonical_content_json(puzzle_id, N, puzzle, solution)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def generate_complete_grid(N: int, rng: random.Random) -> list[int]:
    """Generate a valid complete Sudoku grid of size N using validity-preserving shuffles.

    Args:
        N: Board size (must be a perfect square, e.g. 4, 9, 16, 36, 81).
        rng: Isolated seeded random.Random instance.

    Returns:
        Flat row-major list of N*N ints in range 1..N.
    """
    box = math.isqrt(N)
    if box * box != N or N <= 0:
        raise ValueError(f"N={N} must be a positive perfect square")

    # Base grid
    rows: list[list[int]] = [
        [(box * (r % box) + r // box + c) % N + 1 for c in range(N)]
        for r in range(N)
    ]

    # 1. Row permutation within each band
    for b in range(box):
        band = rows[b * box : (b + 1) * box]
        rng.shuffle(band)
        rows[b * box : (b + 1) * box] = band

    # 2. Column permutation within each stack
    for s in range(box):
        stack_cols = [[rows[r][c] for r in range(N)] for c in range(s * box, (s + 1) * box)]
        rng.shuffle(stack_cols)
        for idx, c in enumerate(range(s * box, (s + 1) * box)):
            for r in range(N):
                rows[r][c] = stack_cols[idx][r]

    # 3. Band permutation
    bands = [rows[b * box : (b + 1) * box] for b in range(box)]
    rng.shuffle(bands)
    rows = [row for band in bands for row in band]

    # 4. Stack permutation
    stacks = [
        [[rows[r][c] for r in range(N)] for c in range(s * box, (s + 1) * box)]
        for s in range(box)
    ]
    rng.shuffle(stacks)
    cols = [col for stack in stacks for col in stack]
    rows = [[cols[c][r] for c in range(N)] for r in range(N)]

    # 5. Optional transpose
    if rng.random() < 0.5:
        rows = [[rows[c][r] for c in range(N)] for r in range(N)]

    # 6. Digit permutation
    digits = list(range(1, N + 1))
    rng.shuffle(digits)

    solution = [digits[rows[r][c] - 1] for r in range(N) for c in range(N)]

    # Always validate
    val_res = is_valid_complete_grid(solution, N)
    if not val_res.ok:
        raise RuntimeError(
            f"Generated complete grid failed validation: {val_res.reason} ({val_res.message})"
        )

    return solution


def generate_puzzle(
    N: int,
    ratio: float,
    index: int,
    base_seed: int = 42,
    generator_version: str = GENERATOR_VERSION,
) -> dict[str, Any]:
    """Generate a single puzzle record.

    Args:
        N: Grid size (9, 36, 81).
        ratio: Removal ratio (e.g. 0.3, 0.5, 0.7, 0.9).
        index: Puzzle index (0..99).
        base_seed: Master experiment seed (default: 42).
        generator_version: Version identifier string.

    Returns:
        Structured dictionary matching the Phase 1 schema.
    """
    box = math.isqrt(N)
    if box * box != N or N <= 0:
        raise ValueError(f"N={N} must be a positive perfect square")

    puzzle_id = puzzle_id_for(N, ratio, index)
    seed = make_puzzle_seed(base_seed, N, ratio, index)
    rng = random.Random(seed)

    solution = generate_complete_grid(N, rng)

    total_cells = N * N
    n_remove = round_half_up(ratio * total_cells)
    realized_ratio = n_remove / total_cells
    n_clues = total_cells - n_remove
    n_empty = n_remove

    removed_indices = sorted(rng.sample(range(total_cells), n_remove))
    puzzle = list(solution)
    for idx in removed_indices:
        puzzle[idx] = 0

    # Validate puzzle against solution
    puz_res = is_valid_puzzle(puzzle, solution, N)
    if not puz_res.ok:
        raise RuntimeError(
            f"Generated puzzle failed validation against solution: {puz_res.reason} ({puz_res.message})"
        )

    content_sha = compute_content_sha256(puzzle_id, N, puzzle, solution)

    return {
        "id": puzzle_id,
        "N": N,
        "box": box,
        "requested_ratio": ratio,
        "realized_ratio": realized_ratio,
        "n_clues": n_clues,
        "n_empty": n_empty,
        "base_seed": base_seed,
        "seed": seed,
        "generator_version": generator_version,
        "puzzle": puzzle,
        "solution": solution,
        "content_sha256": content_sha,
    }
