#!/usr/bin/env python3
"""Run the full benchmark for SAT vs. Non-SAT solvers on all 120 puzzles.

Scope:
- SAT solvers (PySAT): pairwise, sequential, binary, commander, product (CaDiCaL 1.5.3),
  sequential (Glucose 4), sequential (MiniSat 2.2).
- Non-SAT solver: Google OR-Tools CP-SAT.
- Gurobi and CPLEX are completely excluded.
- Evaluates on all 120 puzzles (N in {9, 36, 81}, ratios in {0.5, 0.9}, 20 puzzles/stratum).
- 10.0-second per-run timeout.
- Maximum 5-minute wall-clock budget per invocation; resumable without duplicate records.
- Predeclared resource guard exclusions (pairwise and binary at N=81) are recorded as BUILD_FAIL
  without spawning a solver subprocess.
- Every returned solution is independently validated with sudoku.validator.is_valid_solution_for_puzzle.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sudoku.bench.runner import (
    RESOURCE_GUARD_FRACTION,
    BenchmarkConfig,
    execute_run_subprocess,
    load_existing_run_keys,
    make_run_key,
)
from sudoku.dataset import load_puzzles
from sudoku.solvers.base import (
    STATUS_BUILD_FAIL,
    STATUS_INVALID_SOLUTION,
    STATUS_RESOURCE_GUARD_LIVE,
    STATUS_SOLVER_ERROR,
    STATUS_UNSAT_INVESTIGATE,
)
from sudoku.solvers.sat import estimate_encoding_clauses
from sudoku.validator import is_valid_solution_for_puzzle

RESULTS_DIR = REPO_ROOT / "data" / "results"
JSONL_PATH = RESULTS_DIR / "full_v1.jsonl"
CSV_PATH = RESULTS_DIR / "full_v1.csv"
STOP_PATH = RESULTS_DIR / "full_v1_stop.json"
RUN_INFO_PATH = RESULTS_DIR / "full_v1_run_info.json"
MATRIX_PATH = REPO_ROOT / "configs" / "matrix_sat_vs_nonsat.csv"
MANIFEST_PATH = REPO_ROOT / "data" / "manifest.csv"
ARCHIVE_CALIBRATION = REPO_ROOT / "data" / "archive_v1" / "results" / "pilot_v2_calibration.json"

BASE_SEED = 42
TIMEOUT_S = 10.0
DEFAULT_MAX_WALL_MINUTES = 5.0
DISK_FREE_MIN_BYTES = 1024 ** 3  # 1 GB
SOLVER_ERROR_STAGE_RATE = 0.05
SOLVER_ERROR_MIN_RUNS = 10

SIZES = (9, 36, 81)
RATIOS = (0.5, 0.9)

CONFIG_SPECS: dict[str, dict[str, Any]] = {
    "sat_pairwise_cadical153": {"solver": "sat", "encoding": "pairwise", "backend": "cadical153", "encoding_opts": {}},
    "sat_sequential_cadical153": {"solver": "sat", "encoding": "sequential", "backend": "cadical153", "encoding_opts": {}},
    "sat_binary_cadical153": {"solver": "sat", "encoding": "binary", "backend": "cadical153", "encoding_opts": {}},
    "sat_commander_cadical153": {"solver": "sat", "encoding": "commander", "backend": "cadical153",
                                 "encoding_opts": {"commander_group_size": 4}},
    "sat_product_cadical153": {"solver": "sat", "encoding": "product", "backend": "cadical153", "encoding_opts": {}},
    "sat_sequential_glucose4": {"solver": "sat", "encoding": "sequential", "backend": "glucose4", "encoding_opts": {}},
    "sat_sequential_minisat22_extra_backend": {"solver": "sat", "encoding": "sequential", "backend": "minisat22",
                                               "encoding_opts": {}},
    "cpsat": {"solver": "cpsat"},
}

PREDECLARED_EXCLUDED: set[tuple[str, int]] = {
    ("sat_pairwise_cadical153", 81),
    ("sat_binary_cadical153", 81),
}

FIELDNAMES = [
    "run_key", "puzzle_id", "N", "requested_ratio", "split", "experiment",
    "run_order_position", "solver", "encoding", "backend", "threads",
    "timeout_s", "status", "t_build", "t_solve", "t_total",
    "available_ram_bytes_at_start", "peak_rss_mb",
    "worker_baseline_rss_mb", "worker_ru_maxrss_baseline_mb",
    "worker_ru_maxrss_final_mb", "peak_rss_above_baseline_mb",
    "rss_sampling_interval_ms", "phase_at_kill", "stats", "error",
]


def load_calibration() -> dict[str, float]:
    """Bytes-per-clause per encoding from archived N=36 calibration."""
    if not ARCHIVE_CALIBRATION.exists():
        return {}
    records = json.loads(ARCHIVE_CALIBRATION.read_text(encoding="utf-8"))
    out: dict[str, float] = {}
    for rec in records:
        if rec.get("N") == 36 and rec.get("status") == "BUILT" and rec.get("bytes_per_clause"):
            out[str(rec["encoding"])] = float(rec["bytes_per_clause"])
    return out


def benchmark_config(name: str) -> BenchmarkConfig:
    spec = CONFIG_SPECS[name]
    return BenchmarkConfig(
        solver=spec["solver"],
        encoding=spec.get("encoding", ""),
        backend=spec.get("backend", ""),
        threads=1,
        timeout_s=TIMEOUT_S,
        encoding_opts=dict(spec.get("encoding_opts", {})),
    )


def _index_of(puzzle_rec: dict[str, Any]) -> int:
    return int(puzzle_rec["id"].rsplit("_i", 1)[1])


def split_for_index(index: int) -> str:
    return "selection" if index < 10 else "evaluation"


def _base_record(puzzle_rec: dict[str, Any], cfg: BenchmarkConfig, position: int) -> dict[str, Any]:
    import psutil
    return {
        "run_key": make_run_key(puzzle_rec["id"], cfg),
        "puzzle_id": puzzle_rec["id"],
        "N": puzzle_rec["N"],
        "requested_ratio": puzzle_rec["requested_ratio"],
        "split": split_for_index(_index_of(puzzle_rec)),
        "experiment": "primary",
        "run_order_position": position,
        "solver": cfg.solver,
        "encoding": cfg.encoding if cfg.solver == "sat" else "",
        "backend": cfg.backend if cfg.solver == "sat" else cfg.solver,
        "threads": cfg.threads,
        "timeout_s": cfg.timeout_s,
        "available_ram_bytes_at_start": int(psutil.virtual_memory().available),
    }


def excluded_record(puzzle_rec: dict[str, Any], config_name: str, position: int) -> dict[str, Any]:
    cfg = benchmark_config(config_name)
    base = _base_record(puzzle_rec, cfg, position)
    return {
        **base,
        "status": STATUS_BUILD_FAIL,
        "t_build": 0.0,
        "t_solve": 0.0,
        "t_total": 0.0,
        "peak_rss_mb": None,
        "worker_baseline_rss_mb": None,
        "worker_ru_maxrss_baseline_mb": None,
        "worker_ru_maxrss_final_mb": None,
        "peak_rss_above_baseline_mb": None,
        "stats": {"reason": "RESOURCE_GUARD", "predeclared_exclusion": True},
        "error": ("RESOURCE_GUARD: predeclared exclusion (pilot calibration estimates build memory "
                  "above the 0.60 x available-RAM guard at N=81); not executed"),
        "phase_at_kill": None,
    }


def live_guard_record(puzzle_rec: dict[str, Any], cfg: BenchmarkConfig, position: int,
                      clauses: int, bpc: float, available_ram: int) -> dict[str, Any]:
    base = _base_record(puzzle_rec, cfg, position)
    estimated = int(clauses * bpc)
    threshold = int(available_ram * RESOURCE_GUARD_FRACTION)
    return {
        **base,
        "status": STATUS_RESOURCE_GUARD_LIVE,
        "t_build": 0.0,
        "t_solve": 0.0,
        "t_total": 0.0,
        "peak_rss_mb": None,
        "worker_baseline_rss_mb": None,
        "worker_ru_maxrss_baseline_mb": None,
        "worker_ru_maxrss_final_mb": None,
        "peak_rss_above_baseline_mb": None,
        "stats": {
            "reason": "RESOURCE_GUARD_LIVE",
            "estimated_clauses": clauses,
            "bytes_per_clause": bpc,
            "estimated_memory_bytes": estimated,
            "guard_fraction": RESOURCE_GUARD_FRACTION,
            "guard_threshold_bytes": threshold,
            "available_ram_bytes": available_ram,
        },
        "error": (f"RESOURCE_GUARD_LIVE: estimated {estimated} bytes exceeds "
                  f"{threshold} bytes ({RESOURCE_GUARD_FRACTION:.0%} of {available_ram})"),
        "phase_at_kill": None,
    }


def _flatten_for_csv(record: dict[str, Any]) -> dict[str, Any]:
    row = {k: record.get(k) for k in FIELDNAMES}
    row["stats"] = json.dumps(row["stats"], sort_keys=True) if row.get("stats") is not None else ""
    return row


def append_record(record: dict[str, Any], csv_file: Any, csv_writer: Any, jsonl_file: Any) -> None:
    jsonl_file.write(json.dumps(record, sort_keys=True) + "\n")
    jsonl_file.flush()
    csv_writer.writerow(_flatten_for_csv(record))
    csv_file.flush()


def revalidate_solved(record: dict[str, Any], puzzle_rec: dict[str, Any]) -> dict[str, Any]:
    """Independently re-validate SOLVED_VALID runs; reclassify failures."""
    if record.get("status") != "SOLVED_VALID":
        return record
    solution = record.get("solution")
    if not isinstance(solution, list):
        record["status"] = STATUS_INVALID_SOLUTION
        record["error"] = "SOLVED_VALID with no solution payload"
        return record
    val_res = is_valid_solution_for_puzzle(puzzle_rec["puzzle"], solution, puzzle_rec["N"])
    if not val_res.ok:
        record["status"] = STATUS_INVALID_SOLUTION
        record["error"] = f"Independent validation failed: {val_res.reason} ({val_res.message})"
    return record


def disk_free_bytes() -> int:
    return shutil.disk_usage(str(REPO_ROOT)).free


def run_batch(max_wall_minutes: float = DEFAULT_MAX_WALL_MINUTES, force: bool = False) -> dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    calibration = load_calibration()
    existing_keys = set() if force else load_existing_run_keys(JSONL_PATH)

    all_puzzles = load_puzzles(MANIFEST_PATH)
    puzzles_by_stratum: dict[tuple[int, float], list[dict[str, Any]]] = {}
    for p in all_puzzles:
        key = (p["N"], p["requested_ratio"])
        puzzles_by_stratum.setdefault(key, []).append(p)
    for k in puzzles_by_stratum:
        puzzles_by_stratum[k].sort(key=_index_of)

    csv_exists = CSV_PATH.exists() and not force
    csv_file = open(CSV_PATH, "a" if csv_exists else "w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES, extrasaction="ignore")
    if not csv_exists:
        csv_writer.writeheader()
    jsonl_file = open(JSONL_PATH, "a" if not force else "w", encoding="utf-8")

    summary: dict[str, Any] = {
        "existing_runs_at_start": len(existing_keys),
        "executed_runs": 0,
        "predeclared_excluded_records": 0,
        "live_guard_rejections": 0,
        "records_written": 0,
        "status_counts": {},
        "stop_reason": None,
        "stop_detail": None,
        "wall_clock_s": 0.0,
    }

    t_batch_start = time.monotonic()
    deadline = t_batch_start + max_wall_minutes * 60.0
    position = len(existing_keys)

    def check_budget() -> str | None:
        if time.monotonic() >= deadline:
            return "wall_clock_budget_exhausted"
        return None

    def check_disk() -> str | None:
        if disk_free_bytes() < DISK_FREE_MIN_BYTES:
            return "disk_free_below_1gb"
        return None

    try:
        # Step 1: Write predeclared exclusions for N=81 pairwise and binary
        for ratio in RATIOS:
            for p in puzzles_by_stratum.get((81, ratio), []):
                for cfg_name in ("sat_pairwise_cadical153", "sat_binary_cadical153"):
                    cfg = benchmark_config(cfg_name)
                    k = make_run_key(p["id"], cfg)
                    if k in existing_keys:
                        continue
                    rec = excluded_record(p, cfg_name, position)
                    position += 1
                    append_record(rec, csv_file, csv_writer, jsonl_file)
                    existing_keys.add(k)
                    summary["records_written"] += 1
                    summary["predeclared_excluded_records"] += 1
                    summary["status_counts"][rec["status"]] = summary["status_counts"].get(rec["status"], 0) + 1

        # Step 2: Main execution loop ordered by size (9, 36, 81), then ratio, then puzzle
        batch_stopped = False
        for N in SIZES:
            if batch_stopped:
                break
            for ratio in RATIOS:
                if batch_stopped:
                    break
                puzzles = puzzles_by_stratum.get((N, ratio), [])
                config_names = [name for name in CONFIG_SPECS if (name, N) not in PREDECLARED_EXCLUDED]

                for p in puzzles:
                    if batch_stopped:
                        break
                    for cfg_name in config_names:
                        cfg = benchmark_config(cfg_name)
                        k = make_run_key(p["id"], cfg)
                        if k in existing_keys:
                            continue

                        stop = check_budget() or check_disk()
                        if stop is not None:
                            summary["stop_reason"] = stop
                            summary["stop_detail"] = f"Stopped at {p['id']} {cfg_name}"
                            print(f"\n[STOP] {stop} ({summary['stop_detail']})")
                            batch_stopped = True
                            break

                        # Live resource guard check for SAT models
                        if cfg.solver == "sat" and cfg.encoding in calibration:
                            clues_count = sum(1 for v in p["puzzle"] if v != 0)
                            clauses = estimate_encoding_clauses(p["N"], cfg.encoding, cfg.encoding_opts, clues=clues_count)
                            bpc = calibration[cfg.encoding]
                            import psutil
                            avail_ram = int(psutil.virtual_memory().available)
                            estimated_mem = int(clauses * bpc)
                            threshold = int(avail_ram * RESOURCE_GUARD_FRACTION)
                            if estimated_mem > threshold:
                                rec = live_guard_record(p, cfg, position, clauses, bpc, avail_ram)
                                position += 1
                                append_record(rec, csv_file, csv_writer, jsonl_file)
                                existing_keys.add(k)
                                summary["records_written"] += 1
                                summary["live_guard_rejections"] += 1
                                summary["status_counts"][rec["status"]] = summary["status_counts"].get(rec["status"], 0) + 1
                                continue

                        t_run0 = time.monotonic()
                        print(f"[{position + 1}] Running {p['id']} with {cfg.label} ... ", end="", flush=True)
                        try:
                            rec = execute_run_subprocess(
                                p, cfg,
                                memory_bytes_per_clause=(calibration.get(cfg.encoding) if cfg.solver == "sat" else None)
                            )
                        except Exception as exc:
                            rec = {
                                **_base_record(p, cfg, position),
                                "status": STATUS_SOLVER_ERROR,
                                "t_build": 0.0, "t_solve": 0.0,
                                "t_total": round(time.monotonic() - t_run0, 6),
                                "peak_rss_mb": None,
                                "worker_baseline_rss_mb": None,
                                "worker_ru_maxrss_baseline_mb": None,
                                "worker_ru_maxrss_final_mb": None,
                                "peak_rss_above_baseline_mb": None,
                                "stats": {"runner_crash": True},
                                "error": f"Runner crash executing run: {exc}",
                                "phase_at_kill": None,
                            }

                        rec = revalidate_solved(rec, p)
                        base = _base_record(p, cfg, position)
                        for b_key, b_val in base.items():
                            rec.setdefault(b_key, b_val)

                        position += 1
                        append_record(rec, csv_file, csv_writer, jsonl_file)
                        existing_keys.add(k)
                        summary["records_written"] += 1
                        summary["executed_runs"] += 1
                        st = rec["status"]
                        summary["status_counts"][st] = summary["status_counts"].get(st, 0) + 1
                        t_tot = rec["t_total"]
                        print(f"{st} ({t_tot:.3f}s)")

                        if st == STATUS_INVALID_SOLUTION:
                            print(f"\n[ALERT] INVALID_SOLUTION on {p['id']} {cfg_name}: {rec.get('error')}")
                            summary["stop_reason"] = STATUS_INVALID_SOLUTION
                            summary["stop_detail"] = f"{p['id']} {cfg_name}"
                            batch_stopped = True
                            break

    finally:
        csv_file.close()
        jsonl_file.close()

    summary["wall_clock_s"] = round(time.monotonic() - t_batch_start, 3)
    summary["total_records_in_file"] = len(existing_keys)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full SAT vs Non-SAT benchmark across all 120 puzzles")
    parser.add_argument("--max-wall-minutes", type=float, default=DEFAULT_MAX_WALL_MINUTES,
                        help="Hard budget per batch in minutes (default: 5.0).")
    parser.add_argument("--force", action="store_true", help="Overwrite existing results")
    args = parser.parse_args()

    summary = run_batch(max_wall_minutes=args.max_wall_minutes, force=args.force)
    print("\nBatch execution summary:")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
