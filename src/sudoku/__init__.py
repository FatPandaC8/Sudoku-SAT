"""Sudoku benchmark foundational package: validator, generator, dataset.

Phase 1 implementation for empirical comparison of Sudoku solvers.
"""

from .dataset import (
    get_puzzle_filename,
    load_puzzle_by_id,
    load_puzzles,
    read_manifest,
    write_dataset_info,
    write_manifest,
    write_puzzle_jsonl,
)
from .generator import (
    GENERATOR_VERSION,
    canonical_content_json,
    compute_content_sha256,
    generate_complete_grid,
    generate_puzzle,
    make_puzzle_seed,
    puzzle_id_for,
    round_half_up,
)
from .validator import (
    ValidationResult,
    is_valid_complete_grid,
    is_valid_puzzle,
    is_valid_solution_for_puzzle,
)

__all__ = [
    "ValidationResult",
    "is_valid_complete_grid",
    "is_valid_puzzle",
    "is_valid_solution_for_puzzle",
    "GENERATOR_VERSION",
    "round_half_up",
    "make_puzzle_seed",
    "puzzle_id_for",
    "canonical_content_json",
    "compute_content_sha256",
    "generate_complete_grid",
    "generate_puzzle",
    "get_puzzle_filename",
    "write_puzzle_jsonl",
    "write_manifest",
    "write_dataset_info",
    "read_manifest",
    "load_puzzles",
    "load_puzzle_by_id",
]
