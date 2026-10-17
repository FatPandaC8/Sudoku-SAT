"""Tests for Phase 1 dataset generation, storage, loader, and tamper detection."""

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


class TestDatasetGenerationAndReproducibility:
    def test_reproducible_across_runs_in_temp_dirs(self, tmp_path: Path):
        dir1 = tmp_path / "run1"
        dir2 = tmp_path / "run2"

        # Run generate_dataset into dir1 (using a smaller config or full? Full dataset generation takes ~2 seconds!)
        # Let's test with full config!
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

        # Verify all 12 puzzle JSONL files have byte-identical SHA-256
        files1 = sorted((dir1 / "puzzles").glob("*.jsonl"))
        files2 = sorted((dir2 / "puzzles").glob("*.jsonl"))
        assert len(files1) == 12
        assert len(files2) == 12

        for f1, f2 in zip(files1, files2):
            assert f1.name == f2.name
            assert sha256_of_file(f1) == sha256_of_file(f2)

        # Verify manifest content is identical
        # (Note: file column contains dir path if outside repo, so compare data content)
        m_rows1 = read_manifest(dir1 / "manifest.csv")
        m_rows2 = read_manifest(dir2 / "manifest.csv")
        assert len(m_rows1) == 1200
        assert len(m_rows2) == 1200
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
        assert len(all_puzzles) == 1200
        first = all_puzzles[0]
        assert "id" in first
        assert "puzzle" in first
        assert "solution" in first

    def test_filter_by_size(self, sample_dataset: Path):
        puzzles_9 = load_puzzles(sample_dataset, sizes=9)
        assert len(puzzles_9) == 400
        assert all(p["N"] == 9 for p in puzzles_9)

        puzzles_multi = load_puzzles(sample_dataset, sizes=[9, 36])
        assert len(puzzles_multi) == 800

    def test_filter_by_ratio(self, sample_dataset: Path):
        puzzles_07 = load_puzzles(sample_dataset, ratios=0.7)
        assert len(puzzles_07) == 300
        assert all(abs(p["requested_ratio"] - 0.7) < 1e-5 for p in puzzles_07)

    def test_filter_by_index_range(self, sample_dataset: Path):
        # Stage 1 selective set (index 0..19)
        selective = load_puzzles(sample_dataset, index_range=(0, 20))
        assert len(selective) == 12 * 20  # 240 puzzles
        for p in selective:
            idx = int(p["id"].rsplit("_i", 1)[1])
            assert 0 <= idx < 20

        # Evaluation set (index 20..100)
        eval_set = load_puzzles(sample_dataset, index_range=(20, 100))
        assert len(eval_set) == 12 * 80  # 960 puzzles
        for p in eval_set:
            idx = int(p["id"].rsplit("_i", 1)[1])
            assert 20 <= idx < 100

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
        p = load_puzzle_by_id("sudoku_N036_r0.3_i007", sample_dataset)
        assert p["id"] == "sudoku_N036_r0.3_i007"
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

        # Tamper with the first line of N009_r0.3.jsonl
        puzzle_file = dataset_dir / "puzzles" / "N009_r0.3.jsonl"
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
