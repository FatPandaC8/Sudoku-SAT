"""Tests for Phase 1 Sudoku generator: determinism, validity, round-half-up, and IDs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import pytest

from sudoku.generator import (
    GENERATOR_VERSION,
    compute_content_sha256,
    generate_puzzle,
    make_puzzle_seed,
    puzzle_id_for,
    round_half_up,
)
from sudoku.validator import is_valid_complete_grid, is_valid_puzzle


EXPECTED_N_REMOVE: dict[tuple[int, float], int] = {
    # N=9 (81 cells)
    (9, 0.3): 24,   # 81 * 0.3 = 24.3 -> 24
    (9, 0.5): 41,   # 81 * 0.5 = 40.5 -> 41
    (9, 0.7): 57,   # 81 * 0.7 = 56.7 -> 57
    (9, 0.9): 73,   # 81 * 0.9 = 72.9 -> 73
    # N=36 (1296 cells)
    (36, 0.3): 389,  # 1296 * 0.3 = 388.8 -> 389
    (36, 0.5): 648,  # 1296 * 0.5 = 648.0 -> 648
    (36, 0.7): 907,  # 1296 * 0.7 = 907.2 -> 907
    (36, 0.9): 1166, # 1296 * 0.9 = 1166.4 -> 1166
    # N=81 (6561 cells)
    (81, 0.3): 1968, # 6561 * 0.3 = 1968.3 -> 1968
    (81, 0.5): 3281, # 6561 * 0.5 = 3280.5 -> 3281
    (81, 0.7): 4593, # 6561 * 0.7 = 4592.7 -> 4593
    (81, 0.9): 5905, # 6561 * 0.9 = 5904.9 -> 5905
}


class TestGeneratorDeterminism:
    def test_same_call_produces_identical_output(self):
        a = generate_puzzle(N=9, ratio=0.5, index=42, base_seed=42)
        b = generate_puzzle(N=9, ratio=0.5, index=42, base_seed=42)
        assert a == b
        assert a["content_sha256"] == b["content_sha256"]
        assert a["puzzle"] == b["puzzle"]
        assert a["solution"] == b["solution"]

    def test_subprocess_determinism(self):
        repo_root = Path(__file__).resolve().parent.parent
        cmd = [
            sys.executable,
            "-c",
            "import sys; "
            "from sudoku.generator import generate_puzzle; "
            "p = generate_puzzle(9, 0.7, 5, 42); "
            "print(p['content_sha256'])",
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo_root / "src")
        out1 = subprocess.check_output(cmd, env=env, text=True, cwd=str(repo_root)).strip()
        out2 = subprocess.check_output(cmd, env=env, text=True, cwd=str(repo_root)).strip()
        assert out1 == out2

        local = generate_puzzle(9, 0.7, 5, 42)
        assert local["content_sha256"] == out1

    def test_independent_of_pythonhashseed(self):
        repo_root = Path(__file__).resolve().parent.parent
        code = (
            "from sudoku.generator import generate_puzzle; "
            "p = generate_puzzle(9, 0.3, 10, 42); "
            "print(p['content_sha256'], p['seed'])"
        )
        env1 = os.environ.copy()
        env1["PYTHONHASHSEED"] = "0"
        env1["PYTHONPATH"] = str(repo_root / "src")
        out1 = subprocess.check_output(
            [sys.executable, "-c", code], env=env1, text=True, cwd=str(repo_root)
        ).strip()

        env2 = os.environ.copy()
        env2["PYTHONHASHSEED"] = "12345678"
        env2["PYTHONPATH"] = str(repo_root / "src")
        out2 = subprocess.check_output(
            [sys.executable, "-c", code], env=env2, text=True, cwd=str(repo_root)
        ).strip()

        assert out1 == out2


class TestGeneratorVariation:
    def test_different_indices_produce_different_seeds_and_puzzles(self):
        p0 = generate_puzzle(N=9, ratio=0.5, index=0, base_seed=42)
        p1 = generate_puzzle(N=9, ratio=0.5, index=1, base_seed=42)
        assert p0["seed"] != p1["seed"]
        assert p0["puzzle"] != p1["puzzle"]
        assert p0["solution"] != p1["solution"]
        assert p0["content_sha256"] != p1["content_sha256"]

    def test_different_base_seeds_differ(self):
        p_seed42 = generate_puzzle(N=9, ratio=0.5, index=0, base_seed=42)
        p_seed99 = generate_puzzle(N=9, ratio=0.5, index=0, base_seed=99)
        assert p_seed42["seed"] != p_seed99["seed"]
        assert p_seed42["puzzle"] != p_seed99["puzzle"]


class TestGeneratorValidityAndFormulas:
    @pytest.mark.parametrize("N", [9, 36, 81])
    @pytest.mark.parametrize("ratio", [0.3, 0.5, 0.7, 0.9])
    def test_expected_n_remove_matches_all_12_pairs(self, N: int, ratio: float):
        expected = EXPECTED_N_REMOVE[(N, ratio)]
        calc = round_half_up(ratio * N * N)
        assert calc == expected

        puz = generate_puzzle(N=N, ratio=ratio, index=0, base_seed=42)
        assert puz["n_empty"] == expected
        assert puz["n_clues"] == N * N - expected
        assert puz["realized_ratio"] == expected / (N * N)
        assert is_valid_complete_grid(puz["solution"], N).ok is True
        assert is_valid_puzzle(puz["puzzle"], puz["solution"], N).ok is True

    def test_id_format(self):
        id_str = puzzle_id_for(81, 0.7, 42)
        assert id_str == "sudoku_N081_r0.7_i042"

        puz = generate_puzzle(N=9, ratio=0.3, index=7, base_seed=42)
        assert puz["id"] == "sudoku_N009_r0.3_i007"
        assert puz["generator_version"] == GENERATOR_VERSION

    def test_seeds_and_ids_are_unique_across_1200_pairs(self):
        ids = set()
        seeds = set()
        for N in [9, 36, 81]:
            for ratio in [0.3, 0.5, 0.7, 0.9]:
                for idx in range(100):
                    pid = puzzle_id_for(N, ratio, idx)
                    seed = make_puzzle_seed(42, N, ratio, idx)
                    assert pid not in ids
                    assert seed not in seeds
                    ids.add(pid)
                    seeds.add(seed)

        assert len(ids) == 1200
        assert len(seeds) == 1200
