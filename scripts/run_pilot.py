#!/usr/bin/env python3
"""Run the resumable Phase 2.5 pilot v2 matrix; never starts the full benchmark."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sudoku.bench.runner import (  # noqa: E402
    BenchmarkConfig,
    run_benchmark_suite,
)
from sudoku.dataset import load_puzzles  # noqa: E402

SIZES = (9, 36, 81)
RATIOS = (0.3, 0.5, 0.7, 0.9)
PILOT_INDICES = (0, 1, 2)
ENCODINGS = ("pairwise", "sequential", "binary", "commander", "product")
STOP_STATUSES = {"UNSAT_INVESTIGATE", "INVALID_SOLUTION"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_number}: {exc}") from exc
    return records


def _load_calibration(results_dir: Path) -> dict[str, float]:
    calibration_path = results_dir / "pilot_v2_calibration.json"
    if not calibration_path.exists():
        raise FileNotFoundError(
            f"Missing {calibration_path}; run scripts/calibrate_memory.py before pilot v2"
        )
    records = json.loads(calibration_path.read_text(encoding="utf-8"))
    result: dict[str, float] = {}
    for encoding in ENCODINGS:
        measured = next(
            (
                record for record in records
                if record.get("N") == 36
                and record.get("encoding") == encoding
                and record.get("status") == "BUILT"
            ),
            None,
        )
        if measured is None:
            raise ValueError(f"No successful isolated N=36 memory calibration for {encoding}")
        result[encoding] = float(measured["bytes_per_clause"])
    return result


def _configs(pilot_config: dict[str, Any]) -> list[BenchmarkConfig]:
    timeout_s = float(pilot_config["timeout_s"])
    threads = int(pilot_config["threads_per_solver"])
    commander_group_size = int(pilot_config["commander_group_size"])
    backend_comparison_encoding = str(pilot_config["backend_comparison_encoding"])
    configs = [
        BenchmarkConfig(
            solver="sat",
            encoding=encoding,
            backend="cadical153",
            threads=threads,
            timeout_s=timeout_s,
            encoding_opts=(
                {"commander_group_size": commander_group_size}
                if encoding == "commander"
                else {}
            ),
        )
        for encoding in ENCODINGS
    ]
    configs.extend(
        BenchmarkConfig(
            solver="sat",
            encoding=backend_comparison_encoding,
            backend=backend,
            threads=threads,
            timeout_s=timeout_s,
        )
        for backend in ("glucose4", "minisat22")
    )
    configs.extend(
        BenchmarkConfig(
            solver=solver,
            threads=threads,
            timeout_s=timeout_s,
        )
        for solver in ("cpsat", "gurobi", "cplex_mip", "cplex_cp")
    )
    return configs


def main() -> int:
    results_dir = REPO_ROOT / "data" / "results"
    config_path = REPO_ROOT / "configs" / "pilot_v2.toml"
    pilot_config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    if int(pilot_config["worker_count"]) != 1 or int(pilot_config["threads_per_solver"]) != 1:
        raise ValueError("Pilot v2 is predeclared for one worker and one solver thread")
    output_path = results_dir / "pilot_v2.jsonl"
    prior = _read_jsonl(output_path)
    prior_issue = next((run for run in prior if run.get("status") in STOP_STATUSES), None)
    if prior_issue is not None:
        print(
            f"STOP: existing pilot v2 row {prior_issue.get('run_key')} has "
            f"status {prior_issue['status']}; investigate before resuming."
        )
        return 2

    puzzles = load_puzzles(
        REPO_ROOT / "data" / "manifest.csv",
        sizes=SIZES,
        ratios=RATIOS,
        index_range=(min(PILOT_INDICES), max(PILOT_INDICES) + 1),
    )
    expected_instances = len(SIZES) * len(RATIOS) * len(PILOT_INDICES)
    if len(puzzles) != expected_instances:
        raise RuntimeError(f"Expected {expected_instances} frozen pilot instances, loaded {len(puzzles)}")
    timeout_s = float(pilot_config["timeout_s"])
    configs = _configs(pilot_config)
    planned_runs = len(puzzles) * len(configs)
    worst_case_minutes = planned_runs * timeout_s / 60
    print(
        f"Pilot v2 upper-bound estimate before runs: {planned_runs} runs x "
        f"{timeout_s:g}s = {worst_case_minutes:.1f} minutes (~67 min worst case).",
        flush=True,
    )
    print(
        "Scope: indices 0-2 across all 12 (size, ratio) pairs; "
        f"{len(configs)} configurations; timeout_s={timeout_s:g}; one worker/thread.",
        flush=True,
    )

    bytes_per_clause = _load_calibration(results_dir)
    new_runs = run_benchmark_suite(
        puzzles=puzzles,
        configs=configs,
        output_dir=results_dir,
        suite_name="pilot_v2",
        force=False,
        memory_bytes_per_clause=bytes_per_clause,
    )
    issue = next((run for run in new_runs if run.get("status") in STOP_STATUSES), None)
    if issue is not None:
        print(
            f"STOP: {issue.get('run_key')} returned {issue['status']}; "
            "investigate before continuing the pilot."
        )
        return 2
    print(f"Pilot v2 run file: {output_path}")
    print(f"Newly executed runs: {len(new_runs)}; planned matrix size: {planned_runs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
