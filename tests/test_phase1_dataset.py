"""Tests for Phase 1 dataset generation, storage, loader, and tamper detection.

Dataset scope: 6 (size, ratio) pairs x 20 puzzles = 120 puzzles total,
6 JSONL files, 120 manifest rows.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import pytest

from sudoku.dataset import (
    load_puzzle_by_id,
    load_puzzles,
    read_manifest,
)
from sudoku.generator import compute_content_sha256, generate_puzzle


def sha256_of_file(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


TOTAL_PUZZLES = 120
TOTAL_FILES = 6
PUZZLES_PER_PAIR = 20
PUZZLES_PER_SIZE = 40
PUZZLES_PER_RATIO = 60


class TestDatasetGenerationAndReproducibility:
    def test_reproducible_across_runs_in_temp_dirs(self, tmp_path: Path):
        dir1 = tmp_path / "run1"
        dir2 = tmp_path / "run2"

        # Run generate_dataset into dir1 (300 puzzles total, fast)
        cmd1 = [
            sys.executable,
            "scripts/generate_dataset.py",
            "--output-dir",
            str(dir1 / "puzzles"),
            "--manifest",
            str(dir1 / "manifest.csv"),
            "--force",
        ]
        res1 = subprocess.run(cmd1, capture_output=True, text=True, check=True)
        assert res1.returncode == 0

        cmd2 = [
            sys.executable,
            "scripts/generate_dataset.py",
            "--output-dir",
            str(dir2 / "puzzles"),
            "--manifest",
            str(dir2 / "manifest.csv"),
            "--force",
        ]
        res2 = subprocess.run(cmd2, capture_output=True, text=True, check=True)
        assert res2.returncode == 0

        # Validate both directories with validate_dataset.py
        val_cmd1 = [
            sys.executable,
            "scripts/validate_dataset.py",
            "--manifest",
            str(dir1 / "manifest.csv"),
        ]
        assert subprocess.run(val_cmd1, capture_output=True, text=True).returncode == 0

        val_cmd2 = [
            sys.executable,
            "scripts/validate_dataset.py",
            "--manifest",
            str(dir2 / "manifest.csv"),
        ]
        assert subprocess.run(val_cmd2, capture_output=True, text=True).returncode == 0

        # Verify all 6 puzzle JSONL files have byte-identical SHA-256
        files1 = sorted((dir1 / "puzzles").glob("*.jsonl"))
        files2 = sorted((dir2 / "puzzles").glob("*.jsonl"))
        assert len(files1) == TOTAL_FILES
        assert len(files2) == TOTAL_FILES

        for f1, f2 in zip(files1, files2):
            assert f1.name == f2.name
            assert sha256_of_file(f1) == sha256_of_file(f2)

        # Verify manifest content is identical
        m_rows1 = read_manifest(dir1 / "manifest.csv")
        m_rows2 = read_manifest(dir2 / "manifest.csv")
        assert len(m_rows1) == TOTAL_PUZZLES
        assert len(m_rows2) == TOTAL_PUZZLES
        for r1, r2 in zip(m_rows1, m_rows2):
            for col in [
                "id", "N", "box", "requested_ratio", "realized_ratio",
                "n_clues", "n_empty", "seed", "generator_version", "content_sha256", "line"
            ]:
                assert r1[col] == r2[col]


@pytest.fixture(scope="module")
def sample_dataset(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp_dir = tmp_path_factory.mktemp("loader_dataset")
    cmd = [
        sys.executable,
        "scripts/generate_dataset.py",
        "--output-dir",
        str(tmp_dir / "puzzles"),
        "--manifest",
        str(tmp_dir / "manifest.csv"),
        "--force",
    ]
    subprocess.run(cmd, check=True)
    return tmp_dir / "manifest.csv"


class TestDatasetLoader:

    def test_load_all_puzzles(self, sample_dataset: Path):
        all_puzzles = load_puzzles(sample_dataset)
        assert len(all_puzzles) == TOTAL_PUZZLES
        first = all_puzzles[0]
        assert "id" in first
        assert "puzzle" in first
        assert "solution" in first

    def test_filter_by_size(self, sample_dataset: Path):
        puzzles_9 = load_puzzles(sample_dataset, sizes=9)
        assert len(puzzles_9) == PUZZLES_PER_SIZE
        assert all(p["N"] == 9 for p in puzzles_9)

        puzzles_multi = load_puzzles(sample_dataset, sizes=[9, 36])
        assert len(puzzles_multi) == 2 * PUZZLES_PER_SIZE
        assert all(p["N"] in {9, 36} for p in puzzles_multi)

    def test_filter_by_ratio(self, sample_dataset: Path):
        puzzles_05 = load_puzzles(sample_dataset, ratios=0.5)
        assert len(puzzles_05) == PUZZLES_PER_RATIO
        assert all(abs(p["requested_ratio"] - 0.5) < 1e-5 for p in puzzles_05)

        puzzles_09 = load_puzzles(sample_dataset, ratios=0.9)
        assert len(puzzles_09) == PUZZLES_PER_RATIO
        assert all(abs(p["requested_ratio"] - 0.9) < 1e-5 for p in puzzles_09)

    def test_filter_by_index_range(self, sample_dataset: Path):
        # Selection set (index 0..19)
        selective = load_puzzles(sample_dataset, index_range=(0, 20))
        assert len(selective) == TOTAL_FILES * PUZZLES_PER_PAIR  # 120 puzzles
        for p in selective:
            idx = int(p["id"].rsplit("_i", 1)[1])
            assert 0 <= idx < 20

        # Evaluation set (index 10..19)
        eval_set = load_puzzles(sample_dataset, index_range=(10, 20))
        assert len(eval_set) == TOTAL_FILES * 10  # 60 puzzles
        for p in eval_set:
            idx = int(p["id"].rsplit("_i", 1)[1])
            assert 10 <= idx < 20

    def test_combined_filters(self, sample_dataset: Path):
        subset = load_puzzles(
            sample_dataset,
            sizes=81,
            ratios=0.5,
            index_range=(10, 15),
        )
        assert len(subset) == 5
        assert [p["id"] for p in subset] == [
            f"sudoku_N081_r0.5_i{i:03d}" for i in range(10, 15)
        ]

    def test_load_puzzle_by_id(self, sample_dataset: Path):
        p = load_puzzle_by_id("sudoku_N036_r0.5_i007", sample_dataset)
        assert p["id"] == "sudoku_N036_r0.5_i007"
        assert p["N"] == 36
        assert len(p["puzzle"]) == 36 * 36


class TestTamperDetection:
    def test_tampering_with_one_cell_is_detected(self, tmp_path: Path):
        dataset_dir = tmp_path / "tamper_data"
        cmd = [
            sys.executable,
            "scripts/generate_dataset.py",
            "--output-dir",
            str(dataset_dir / "puzzles"),
            "--manifest",
            str(dataset_dir / "manifest.csv"),
            "--force",
        ]
        subprocess.run(cmd, check=True)

        manifest_file = dataset_dir / "manifest.csv"
        # Validate that untampered dataset passes
        val_cmd = [sys.executable, "scripts/validate_dataset.py", "--manifest", str(manifest_file)]
        assert subprocess.run(val_cmd, capture_output=True, text=True).returncode == 0

        # Tamper with the first line of N009_r0.5.jsonl
        puzzle_file = dataset_dir / "puzzles" / "N009_r0.5.jsonl"
        with open(puzzle_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        rec0 = json.loads(lines[0])
        # Find a non-zero cell in solution and corrupt it in puzzle or corrupt solution
        rec0["puzzle"][0] = 999  # Out of range corrupted value
        lines[0] = json.dumps(rec0, sort_keys=True, separators=(",", ":")) + "\n"

        with open(puzzle_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # Validation must fail with non-zero exit code
        val_res = subprocess.run(val_cmd, capture_output=True, text=True)
        assert val_res.returncode != 0
        assert "VALIDATION FAILED" in val_res.stderr or "OUT_OF_RANGE" in val_res.stderr or "mismatch" in val_res.stderr
