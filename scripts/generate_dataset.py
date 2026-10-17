#!/usr/bin/env python3
"""CLI script to generate the fixed Sudoku benchmark dataset.

Generates 1,200 puzzles across 12 (size, ratio) pairs deterministically,
validates each puzzle before writing, and writes JSONL files and manifest.csv.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

import yaml

# Ensure 'src' is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sudoku.dataset import (
    get_puzzle_filename,
    write_dataset_info,
    write_manifest,
    write_puzzle_jsonl,
)
from sudoku.generator import (
    GENERATOR_VERSION,
    generate_puzzle,
    round_half_up,
)
from sudoku.validator import is_valid_puzzle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic Sudoku benchmark dataset."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "configs" / "dataset.yaml",
        help="Path to YAML configuration file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing dataset files if present.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override output directory for puzzle JSONL files.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Override manifest CSV path.",
    )
    return parser.parse_args()


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        print(f"Error: Configuration file not found at {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    sizes: list[int] = cfg.get("sizes", [9, 36, 81])
    ratios: list[float] = [float(r) for r in cfg.get("ratios", [0.3, 0.5, 0.7, 0.9])]
    puzzles_per_pair: int = int(cfg.get("puzzles_per_pair", 100))
    base_seed: int = int(cfg.get("base_seed", 42))
    version: str = str(cfg.get("generator_version", GENERATOR_VERSION))

    output_dir = args.output_dir or (REPO_ROOT / cfg.get("output_dir", "data/puzzles"))
    manifest_path = args.manifest or (REPO_ROOT / cfg.get("manifest_path", "data/manifest.csv"))
    info_path = REPO_ROOT / cfg.get("info_path", "data/dataset_info.json")

    output_dir = output_dir.resolve()
    manifest_path = manifest_path.resolve()
    info_path = info_path.resolve()

    # Safety check: refuse to overwrite existing dataset unless --force is given
    target_files = [output_dir / get_puzzle_filename(N, r) for N in sizes for r in ratios]
    existing = [f for f in target_files if f.exists()]
    if manifest_path.exists():
        existing.append(manifest_path)

    if existing and not args.force:
        print(
            f"Error: Existing dataset files found ({len(existing)} files exist).\n"
            f"Use --force to overwrite.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("=" * 70)
    print("SUDOKU BENCHMARK — DATASET GENERATION")
    print("=" * 70)
    print(f"Base seed:         {base_seed}")
    print(f"Generator version: {version}")
    print(f"Sizes:             {sizes}")
    print(f"Ratios:            {ratios}")
    print(f"Puzzles per pair:  {puzzles_per_pair}")
    print(f"Total puzzles:     {len(sizes) * len(ratios) * puzzles_per_pair}")
    print(f"Output directory:  {output_dir}")
    print(f"Manifest path:     {manifest_path}")
    print("-" * 70)

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    all_manifest_rows: list[dict[str, Any]] = []
    summary_stats: list[dict[str, Any]] = []

    total_t0 = time.perf_counter()
    time_per_size: dict[int, float] = {N: 0.0 for N in sizes}

    for N in sizes:
        size_t0 = time.perf_counter()
        for ratio in ratios:
            filename = get_puzzle_filename(N, ratio)
            puzzle_file_path = output_dir / filename

            # Compute relative path for manifest
            try:
                rel_file_str = str(puzzle_file_path.relative_to(REPO_ROOT))
            except ValueError:
                rel_file_str = str(puzzle_file_path)

            records: list[dict[str, Any]] = []
            realized_ratios: list[float] = []

            for idx in range(puzzles_per_pair):
                rec = generate_puzzle(
                    N=N,
                    ratio=ratio,
                    index=idx,
                    base_seed=base_seed,
                    generator_version=version,
                )

                # Validate BEFORE writing
                val_res = is_valid_puzzle(rec["puzzle"], rec["solution"], N)
                if not val_res.ok:
                    print(
                        f"FATAL: Validation failed for {rec['id']}: {val_res.reason} ({val_res.message})",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                records.append(rec)
                realized_ratios.append(rec["realized_ratio"])

                manifest_row = {
                    "id": rec["id"],
                    "N": rec["N"],
                    "box": rec["box"],
                    "requested_ratio": rec["requested_ratio"],
                    "realized_ratio": rec["realized_ratio"],
                    "n_clues": rec["n_clues"],
                    "n_empty": rec["n_empty"],
                    "seed": rec["seed"],
                    "generator_version": rec["generator_version"],
                    "content_sha256": rec["content_sha256"],
                    "file": rel_file_str,
                    "line": idx + 1,
                }
                all_manifest_rows.append(manifest_row)

            # Write JSONL for this pair
            write_puzzle_jsonl(records, puzzle_file_path)

            expected_n_remove = round_half_up(ratio * N * N)
            actual_n_remove = records[0]["n_empty"]
            min_rr = min(realized_ratios)
            max_rr = max(realized_ratios)
            mean_rr = sum(realized_ratios) / len(realized_ratios)

            summary_stats.append(
                {
                    "N": N,
                    "ratio": ratio,
                    "count": len(records),
                    "expected_empty": expected_n_remove,
                    "actual_empty": actual_n_remove,
                    "min_realized": min_rr,
                    "max_realized": max_rr,
                    "mean_realized": mean_rr,
                    "file": filename,
                    "file_size_kb": puzzle_file_path.stat().st_size / 1024,
                }
            )

        time_per_size[N] = time.perf_counter() - size_t0

    # Write manifest
    write_manifest(all_manifest_rows, manifest_path)

    # Write dataset info
    write_dataset_info(
        info_path=info_path,
        base_seed=base_seed,
        generator_version=version,
        sizes=sizes,
        ratios=ratios,
        puzzles_per_pair=puzzles_per_pair,
        manifest_path=manifest_path,
    )

    total_time = time.perf_counter() - total_t0

    # Print summary
    print(f"\nGenerated {len(all_manifest_rows)} puzzles in {total_time:.2f}s total.")
    print("\nSummary by (Size, Ratio) pair:")
    header = (
        f"{'Size':>5} | {'Req Ratio':>9} | {'Count':>5} | "
        f"{'Exp Empty':>9} | {'Act Empty':>9} | "
        f"{'Min Realized':>12} | {'Max Realized':>12} | {'File Size (KB)':>14}"
    )
    print(header)
    print("-" * len(header))
    for s in summary_stats:
        print(
            f"{s['N']:>5} | {s['ratio']:>9.1f} | {s['count']:>5} | "
            f"{s['expected_empty']:>9} | {s['actual_empty']:>9} | "
            f"{s['min_realized']:>12.6f} | {s['max_realized']:>12.6f} | "
            f"{s['file_size_kb']:>14.1f}"
        )

    print("\nGeneration Time by Size N:")
    for N in sizes:
        print(f"  N = {N:2d} (400 puzzles): {time_per_size[N]:6.2f}s ({time_per_size[N] / 400 * 1000:5.2f} ms/puzzle)")

    print(f"\nManifest written to: {manifest_path} ({manifest_path.stat().st_size / 1024:.1f} KB)")
    print(f"Dataset info to:     {info_path}")
    print("Generation complete and successfully validated.")


if __name__ == "__main__":
    main()
