#!/usr/bin/env python3
"""CLI script to validate an existing Sudoku benchmark dataset against specification.

Checks:
1. Manifest structure, column integrity, and 1,200 row count.
2. File existence and line count for all 12 referenced JSONL files.
3. Strict line-by-line verification:
   - Record JSON matches manifest row for all metadata fields.
   - Solution is a valid complete grid (is_valid_complete_grid).
   - Puzzle is valid and consistent with solution (is_valid_puzzle).
   - Empty cell count matches n_empty and realized_ratio.
   - Content SHA-256 matches canonical serialization of {id, N, puzzle, solution}.
   - Seed matches SHA-256 derivation formula.
4. Exits 0 if all checks pass; exits non-zero on any error or discrepancy.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

# Ensure 'src' is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sudoku.dataset import _resolve_puzzle_file, read_manifest
from sudoku.generator import (
    compute_content_sha256,
    make_puzzle_seed,
    round_half_up,
)
from sudoku.validator import is_valid_complete_grid, is_valid_puzzle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify integrity of generated Sudoku dataset."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPO_ROOT / "data" / "manifest.csv",
        help="Path to manifest.csv to validate.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = args.manifest.resolve()

    if not manifest_path.is_file():
        print(f"ERROR: Manifest file not found at {manifest_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("SUDOKU BENCHMARK — DATASET VALIDATION")
    print("=" * 70)
    print(f"Validating manifest: {manifest_path}")

    try:
        rows = read_manifest(manifest_path)
    except Exception as e:
        print(f"ERROR: Failed to parse manifest CSV: {e}", file=sys.stderr)
        sys.exit(1)

    total_rows = len(rows)
    print(f"Manifest rows read: {total_rows}")

    if total_rows != 1200:
        print(
            f"ERROR: Manifest must contain exactly 1,200 rows, found {total_rows}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check uniqueness of IDs and seeds
    ids = [r["id"] for r in rows]
    seeds = [r["seed"] for r in rows]
    if len(set(ids)) != len(ids):
        print("ERROR: Duplicate puzzle IDs detected in manifest!", file=sys.stderr)
        sys.exit(1)
    if len(set(seeds)) != len(seeds):
        print("ERROR: Duplicate puzzle seeds detected in manifest!", file=sys.stderr)
        sys.exit(1)

    # Group rows by referenced file
    rows_by_file: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        rows_by_file.setdefault(r["file"], []).append(r)

    print(f"Referenced files:   {len(rows_by_file)} files")
    if len(rows_by_file) != 12:
        print(
            f"ERROR: Expected 12 distinct JSONL files, found {len(rows_by_file)}",
            file=sys.stderr,
        )
        sys.exit(1)

    errors: list[str] = []
    validated_count = 0

    for file_str, file_rows in sorted(rows_by_file.items()):
        try:
            resolved_file = _resolve_puzzle_file(manifest_path, file_str)
        except FileNotFoundError as e:
            errors.append(str(e))
            continue

        if len(file_rows) != 100:
            errors.append(f"File {file_str} has {len(file_rows)} manifest entries (expected 100)")

        with open(resolved_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) != 100:
            errors.append(f"File {resolved_file} has {len(lines)} lines (expected 100)")
            continue

        for i, (m_row, line) in enumerate(zip(file_rows, lines), start=1):
            if m_row["line"] != i:
                errors.append(
                    f"Line number mismatch in {file_str}: manifest line={m_row['line']}, actual={i}"
                )

            try:
                rec = json.loads(line)
            except Exception as e:
                errors.append(f"JSON decode error in {file_str} line {i}: {e}")
                continue

            # Check metadata matches between manifest and JSON record
            for field in [
                "id",
                "N",
                "box",
                "requested_ratio",
                "realized_ratio",
                "n_clues",
                "n_empty",
                "seed",
                "generator_version",
                "content_sha256",
            ]:
                if rec.get(field) != m_row[field]:
                    errors.append(
                        f"Field mismatch for {m_row['id']} on '{field}': "
                        f"manifest={m_row[field]}, json={rec.get(field)}"
                    )

            N = rec["N"]
            ratio = rec["requested_ratio"]
            puzzle = rec["puzzle"]
            solution = rec["solution"]

            # Validate solution
            sol_res = is_valid_complete_grid(solution, N)
            if not sol_res.ok:
                errors.append(
                    f"Invalid solution in {m_row['id']}: {sol_res.reason} ({sol_res.message})"
                )

            # Validate puzzle against solution
            puz_res = is_valid_puzzle(puzzle, solution, N)
            if not puz_res.ok:
                errors.append(
                    f"Invalid puzzle in {m_row['id']}: {puz_res.reason} ({puz_res.message})"
                )

            # Check expected empty cells
            expected_empty = round_half_up(ratio * N * N)
            if rec["n_empty"] != expected_empty:
                errors.append(
                    f"Empty cell count mismatch in {m_row['id']}: "
                    f"recorded={rec['n_empty']}, expected={expected_empty}"
                )

            # Recompute content_sha256
            recomputed_sha = compute_content_sha256(rec["id"], N, puzzle, solution)
            if recomputed_sha != rec["content_sha256"]:
                errors.append(
                    f"Content SHA-256 mismatch in {m_row['id']}: "
                    f"recorded={rec['content_sha256']}, recomputed={recomputed_sha}"
                )

            # Verify seed derivation
            # extract index from ID
            idx = int(rec["id"].rsplit("_i", 1)[1])
            expected_seed = make_puzzle_seed(rec["base_seed"], N, ratio, idx)
            if rec["seed"] != expected_seed:
                errors.append(
                    f"Seed mismatch in {m_row['id']}: "
                    f"recorded={rec['seed']}, expected={expected_seed}"
                )

            validated_count += 1

    print("-" * 70)
    if errors:
        print(f"VALIDATION FAILED with {len(errors)} error(s):", file=sys.stderr)
        for err in errors[:20]:
            print(f"  - {err}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors", file=sys.stderr)
        sys.exit(1)

    print(f"SUCCESS: All {validated_count} puzzles across 12 files verified 100% valid.")
    print("All content hashes, seeds, ratios, and manifest cross-references matched perfectly.")
    sys.exit(0)


if __name__ == "__main__":
    main()
