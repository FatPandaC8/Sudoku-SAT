"""Dataset persistence, manifest management, and filtered dataset loading.

All solvers in subsequent phases must load puzzle instances exclusively via
this module to guarantee byte-identical input representations.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence


def get_puzzle_filename(N: int, ratio: float) -> str:
    """Return canonical JSONL filename for an (N, ratio) pair.

    Example: N081_r0.7.jsonl
    """
    return f"N{N:03d}_r{ratio:.1f}.jsonl"


def write_puzzle_jsonl(records: Sequence[dict[str, Any]], target_file: Path | str) -> None:
    """Write puzzle records deterministically to a JSONL file.

    Sorted keys, explicit separators, UTF-8, LF newlines.
    """
    path = Path(target_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            line = json.dumps(rec, sort_keys=True, separators=(",", ":"))
            f.write(f"{line}\n")


def write_manifest(manifest_rows: Sequence[dict[str, Any]], manifest_path: Path | str) -> None:
    """Write dataset manifest to CSV deterministically.

    Columns: id, N, box, requested_ratio, realized_ratio, n_clues, n_empty,
             seed, generator_version, content_sha256, file, line.
    """
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
        "file",
        "line",
    ]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in manifest_rows:
            writer.writerow({k: row[k] for k in fieldnames})


def write_dataset_info(
    info_path: Path | str,
    base_seed: int,
    generator_version: str,
    sizes: list[int],
    ratios: list[float],
    puzzles_per_pair: int,
    manifest_path: Path | str,
) -> dict[str, Any]:
    """Write optional dataset_info.json containing dataset metadata and manifest SHA-256."""
    info_file = Path(info_path)
    info_file.parent.mkdir(parents=True, exist_ok=True)

    with open(manifest_path, "rb") as f:
        manifest_sha = hashlib.sha256(f.read()).hexdigest()

    info_data = {
        "base_seed": base_seed,
        "counts": {
            "puzzles_per_pair": puzzles_per_pair,
            "total_pairs": len(sizes) * len(ratios),
            "total_puzzles": len(sizes) * len(ratios) * puzzles_per_pair,
        },
        "generator_version": generator_version,
        "manifest_sha256": manifest_sha,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "ratios": ratios,
        "sizes": sizes,
    }

    with open(info_file, "w", encoding="utf-8", newline="\n") as f:
        json.dump(info_data, f, indent=2, sort_keys=True)
        f.write("\n")

    return info_data


def read_manifest(manifest_path: Path | str) -> list[dict[str, Any]]:
    """Read manifest CSV into a list of row dicts with parsed types."""
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest file not found: {path}")

    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "id": row["id"],
                    "N": int(row["N"]),
                    "box": int(row["box"]),
                    "requested_ratio": float(row["requested_ratio"]),
                    "realized_ratio": float(row["realized_ratio"]),
                    "n_clues": int(row["n_clues"]),
                    "n_empty": int(row["n_empty"]),
                    "seed": int(row["seed"]),
                    "generator_version": row["generator_version"],
                    "content_sha256": row["content_sha256"],
                    "file": row["file"],
                    "line": int(row["line"]),
                }
            )
    return rows


def _resolve_puzzle_file(manifest_path: Path, file_field: str) -> Path:
    """Resolve the JSONL puzzle file path across various working directory contexts."""
    candidate = Path(file_field)
    if candidate.is_file():
        return candidate

    # Relative to manifest's parent directory (e.g. data/)
    cand_rel_parent = manifest_path.parent / file_field
    if cand_rel_parent.is_file():
        return cand_rel_parent

    # Relative to manifest's parent's parent (e.g. repo root when file_field starts with data/)
    cand_rel_root = manifest_path.parent.parent / file_field
    if cand_rel_root.is_file():
        return cand_rel_root

    # Try resolving just filename within data/puzzles or manifest_dir/puzzles
    cand_basename = manifest_path.parent / "puzzles" / candidate.name
    if cand_basename.is_file():
        return cand_basename

    raise FileNotFoundError(f"Could not locate puzzle file '{file_field}' referenced in manifest {manifest_path}")


def load_puzzles(
    manifest_path: Path | str = "data/manifest.csv",
    sizes: int | Sequence[int] | None = None,
    ratios: float | Sequence[float] | None = None,
    index_range: tuple[int, int] | range | None = None,
) -> list[dict[str, Any]]:
    """Load puzzle instances from the dataset, filtered by size, ratio, and index range.

    Instances are read strictly from the stored JSONL files.

    Args:
        manifest_path: Path to manifest.csv.
        sizes: Target size or list of sizes (e.g. 9 or [9, 36]).
        ratios: Target ratio or list of ratios (e.g. 0.7 or [0.3, 0.7]).
        index_range: (start, end) index bounds [start, end) or range object.

    Returns:
        List of puzzle records directly deserialized from stored JSONL lines.
    """
    manifest_file = Path(manifest_path)
    rows = read_manifest(manifest_file)

    if sizes is not None:
        target_sizes = {sizes} if isinstance(sizes, int) else set(sizes)
        rows = [r for r in rows if r["N"] in target_sizes]

    if ratios is not None:
        target_ratios = [ratios] if isinstance(ratios, (int, float)) else list(ratios)
        rows = [
            r
            for r in rows
            if any(abs(r["requested_ratio"] - tr) < 1e-5 for tr in target_ratios)
        ]

    if index_range is not None:
        if isinstance(index_range, tuple):
            start_idx, end_idx = index_range
        else:
            start_idx, end_idx = index_range.start, index_range.stop

        def _get_idx(row_id: str) -> int:
            # Format: sudoku_N{N:03d}_r{ratio:.1f}_i{index:03d}
            return int(row_id.rsplit("_i", 1)[1])

        rows = [r for r in rows if start_idx <= _get_idx(r["id"]) < end_idx]

    # Group by file to minimize open/seek overhead while preserving deterministic manifest order
    loaded_puzzles: list[dict[str, Any]] = []
    file_cache: dict[Path, list[str]] = {}

    for row in rows:
        resolved_file = _resolve_puzzle_file(manifest_file, row["file"])
        if resolved_file not in file_cache:
            with open(resolved_file, "r", encoding="utf-8") as f:
                file_cache[resolved_file] = f.readlines()

        line_num = row["line"]  # 1-indexed
        raw_line = file_cache[resolved_file][line_num - 1]
        record = json.loads(raw_line)
        loaded_puzzles.append(record)

    return loaded_puzzles


def load_puzzle_by_id(puzzle_id: str, manifest_path: Path | str = "data/manifest.csv") -> dict[str, Any]:
    """Load a single puzzle record by its canonical ID."""
    manifest_file = Path(manifest_path)
    rows = read_manifest(manifest_file)
    matching = [r for r in rows if r["id"] == puzzle_id]
    if not matching:
        raise KeyError(f"Puzzle with ID '{puzzle_id}' not found in manifest {manifest_path}")

    row = matching[0]
    resolved_file = _resolve_puzzle_file(manifest_file, row["file"])
    with open(resolved_file, "r", encoding="utf-8") as f:
        for cur_line_num, line in enumerate(f, start=1):
            if cur_line_num == row["line"]:
                return json.loads(line)

    raise ValueError(f"Line {row['line']} not found in {resolved_file}")
