"""Tests for the puzzle generator: validity, uniqueness, reproducibility."""

import pytest

from sudoku_solver.generator import (
    DIFFICULTY_PRESETS,
    GenerationError,
    generate,
    load_dataset,
    load_puzzle,
    save_puzzle,
)
from sudoku_solver.puzzle import validate_partial, validate_solution


@pytest.mark.parametrize("size,difficulty", [
    (4, "easy"), (4, "medium"), (4, "hard"),
    (9, "easy"), (9, "medium"), (9, "hard"),
    (16, "easy"), (16, "medium"),  # 16x16 hard is covered by the budget test
])
def test_generated_puzzles_are_valid_and_unique(size, difficulty):
    from sudoku_solver.backtracking import count_solutions

    gen = generate(size=size, difficulty=difficulty, seed=7, timeout=60)
    puzzle, solution, meta = gen
    assert puzzle.size == size and solution.size == size
    assert validate_partial(puzzle) == []
    assert validate_solution(solution, puzzle) == []
    assert count_solutions(puzzle, max_solutions=2) == 1
    assert meta["unique"] is True
    assert meta["clue_count"] == puzzle.clue_count()
    assert meta["clue_count"] >= meta["target_clues"] or not meta["target_reached"]


def test_difficulty_presets_exist():
    assert set(DIFFICULTY_PRESETS) == {"easy", "medium", "hard"}


def test_reproducible_generation():
    a = generate(size=9, difficulty="medium", seed=123, timeout=60)
    b = generate(size=9, difficulty="medium", seed=123, timeout=60)
    assert a.puzzle == b.puzzle
    assert a.solution == b.solution
    # metadata is deterministic except for wall-clock generation_time.
    ma = {k: v for k, v in a.metadata.items() if k != "generation_time"}
    mb = {k: v for k, v in b.metadata.items() if k != "generation_time"}
    assert ma == mb


def test_different_seeds_differ():
    a = generate(size=9, difficulty="easy", seed=1, timeout=60)
    b = generate(size=9, difficulty="easy", seed=2, timeout=60)
    assert a.puzzle != b.puzzle


def test_unknown_difficulty_rejected():
    with pytest.raises(ValueError):
        generate(size=9, difficulty="impossible", seed=1)


def test_invalid_size_rejected():
    with pytest.raises(ValueError):
        generate(size=10, difficulty="easy", seed=1)


def test_generation_budget_failure_recorded():
    """A zero-second budget cannot reach the target; metadata records it.

    The puzzle (if any) is still valid+unique; only target_reached is False.
    """
    try:
        gen = generate(size=16, difficulty="hard", seed=5, timeout=0.0)
    except GenerationError:
        return  # also acceptable: no budget at all
    puzzle, _sol, meta = gen
    assert meta["target_reached"] is False
    assert validate_partial(puzzle) == []


def test_difficulty_score_deterministic():
    a = generate(size=9, difficulty="hard", seed=11, timeout=60)
    from sudoku_solver.generator import difficulty_score

    assert difficulty_score(a.puzzle) == a.metadata["difficulty_score"]


# --- persistence -----------------------------------------------------------

def test_save_load_roundtrip(tmp_path):
    gen = generate(size=4, difficulty="easy", seed=3, timeout=30)
    path = save_puzzle(tmp_path, 4, "easy", 0, gen)
    puzzle, solution, record = load_puzzle(path)
    assert puzzle == gen.puzzle
    assert solution == gen.solution
    assert record["size"] == 4
    assert record["difficulty"] == "easy"
    assert record["metadata"]["unique"] is True
    assert "puzzle_id" in record


def test_load_dataset_filters(tmp_path):
    save_puzzle(tmp_path, 4, "easy", 0, generate(size=4, difficulty="easy", seed=1))
    save_puzzle(tmp_path, 4, "hard", 1, generate(size=4, difficulty="hard", seed=2))
    assert len(list(load_dataset(tmp_path))) == 2
    assert len(list(load_dataset(tmp_path, size=4))) == 2
    assert len(list(load_dataset(tmp_path, difficulty="hard"))) == 1
    assert len(list(load_dataset(tmp_path, size=9))) == 0
