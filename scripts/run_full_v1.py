#!/usr/bin/env python3
"""Full benchmark v1 runner: primary experiment matrix.

Resumable, serialized, one worker/thread, fresh subprocess per run.
Stages run N=9, N=36, N=81; within a stage a deterministic balanced sample of
puzzle indices is taken per (N, removal_ratio) pair (same k for every pair,
indices sorted so a budget stop leaves a clean prefix). For each sampled
instance the included configurations are run in an order shuffled by a seeded
RNG (seed derived from the instance ID and base seed 42).

Predeclared resource-guard exclusions (pairwise and binary at N=81) are
recorded as BUILD_FAIL / RESOURCE_GUARD without spawning a solver. Live
resource-guard rejections in included cells are recorded as RESOURCE_GUARD_LIVE
and reported separately.

Every SOLVED_VALID record is re-validated by the independent validator
(sudoku.validator.is_valid_solution_for_puzzle); a failure is reclassified as
INVALID_SOLUTION and stops the run.

Output: append-only data/results/full_v1.jsonl plus a CSV copy
(data/results/full_v1.csv). Re-running skips existing run keys, so the run is
resumable without duplicates or gaps.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sudoku.bench.runner import (  # noqa: E402
    RESOURCE_GUARD_FRACTION,
    BenchmarkConfig,
    execute_run_subprocess,
    load_existing_run_keys,
    make_run_key,
)
from sudoku.dataset import load_puzzles  # noqa: E402
from sudoku.solvers.base import (  # noqa: E402
    STATUS_BUILD_FAIL,
    STATUS_INVALID_SOLUTION,
    STATUS_RESOURCE_GUARD_LIVE,
    STATUS_SOLVER_ERROR,
    STATUS_UNSAT_INVESTIGATE,
)
from sudoku.solvers.sat import estimate_encoding_clauses  # noqa: E402
from sudoku.validator import is_valid_solution_for_puzzle  # noqa: E402

RESULTS_DIR = REPO_ROOT / "data" / "results"
JSONL_PATH = RESULTS_DIR / "full_v1.jsonl"
CSV_PATH = RESULTS_DIR / "full_v1.csv"
STOP_PATH = RESULTS_DIR / "full_v1_stop.json"
RUN_INFO_PATH = REPO_ROOT / "data" / "results" / "full_v1_run_info.json"
MATRIX_PATH = REPO_ROOT / "configs" / "full_matrix_v1.csv"
MANIFEST_PATH = REPO_ROOT / "data" / "manifest.csv"
DATASET_CONFIG_PATH = REPO_ROOT / "configs" / "dataset.yaml"
ARCHIVE_CALIBRATION = REPO_ROOT / "data" / "archive_v1" / "results" / "pilot_v2_calibration.json"

BASE_SEED = 42
TIMEOUT_S = 10.0
MAX_WALL_HOURS = 6.0
MAX_WALL_MINUTES = 5.0  # hard wall-clock budget for the preliminary sampled run
DISK_FREE_MIN_BYTES = 1024 ** 3  # 1 GB
SOLVER_ERROR_STAGE_RATE = 0.02
SOLVER_ERROR_MIN_RUNS = 10
PROGRESS_INTERVAL_S = 300.0  # 5 minutes

SIZES = (9, 36, 81)
RATIOS = (0.5, 0.9)


def load_dataset_config() -> dict[str, Any]:
    import yaml

    with open(DATASET_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


DATASET_CFG = load_dataset_config()
INDICES_PER_PAIR = int(DATASET_CFG.get("puzzles_per_pair", 20))
SAMPLE_PER_PAIR = int(DATASET_CFG.get("sample_per_pair", 1))


def sampled_indices(N: int, ratio: float) -> list[int]:
    """Deterministic balanced sample of puzzle indices for a (N, ratio) pair.

    Same k (SAMPLE_PER_PAIR) for every pair. Seed derived from SHA-256 of
    "BASE_SEED|N|ratio|sample", consistent with the puzzle seed rule. Returned
    sorted so the run forms a clean prefix per pair.
    """
    key = f"{BASE_SEED}|{N}|{ratio}|sample".encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(key).digest()[:8], byteorder="big", signed=False)
    rng = random.Random(seed)
    return sorted(rng.sample(range(INDICES_PER_PAIR), SAMPLE_PER_PAIR))

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
    "gurobi": {"solver": "gurobi"},
    "cplex_mip": {"solver": "cplex_mip"},
    "cplex_cp": {"solver": "cplex_cp"},
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

_matrix_cache: list[dict[str, Any]] | None = None
_totals_cache: dict[str, int] | None = None


def load_matrix() -> list[dict[str, Any]]:
    global _matrix_cache
    if _matrix_cache is None:
        with open(MATRIX_PATH, newline="", encoding="utf-8") as f:
            _matrix_cache = list(csv.DictReader(f))
    return _matrix_cache


def totals() -> dict[str, int]:
    global _totals_cache
    if _totals_cache is None:
        matrix = load_matrix()
        included = [r for r in matrix if r["decision"] == "INCLUDE"]
        _totals_cache = {
            "cells": len(matrix),
            "included_cells": len(included),
            "excluded_cells": len(matrix) - len(included),
            "recorded_runs": len(matrix) * INDICES_PER_PAIR,
            "executed_runs": len(included) * INDICES_PER_PAIR,
            "predeclared_records": (len(matrix) - len(included)) * INDICES_PER_PAIR,
            "sample_per_pair": SAMPLE_PER_PAIR,
            "sampled_recorded_runs": len(matrix) * SAMPLE_PER_PAIR,
            "sampled_executed_runs": len(included) * SAMPLE_PER_PAIR,
            "sampled_predeclared_records": (len(matrix) - len(included)) * SAMPLE_PER_PAIR,
        }
    return _totals_cache


def load_calibration() -> dict[str, float]:
    """Bytes-per-clause per encoding from the archived N=36 calibration."""
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


def shuffle_seed(puzzle_id: str) -> int:
    """Seeded RNG seed derived from instance ID and base seed 42."""
    key = f"{BASE_SEED}|{puzzle_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(key).digest()[:8], byteorder="big", signed=False)


def split_for_index(index: int) -> str:
    return "selection" if index < 10 else "evaluation"


def _index_of(puzzle_rec: dict[str, Any]) -> int:
    return int(puzzle_rec["id"].rsplit("_i", 1)[1])


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


def append_record(record: dict[str, Any], csv_file: Any, csv_writer: Any, jsonl_file: Any) -> None:
    jsonl_file.write(json.dumps(record, sort_keys=True) + "\n")
    jsonl_file.flush()
    csv_writer.writerow(_flatten_for_csv(record))
    csv_file.flush()


def _flatten_for_csv(record: dict[str, Any]) -> dict[str, Any]:
    row = {k: record.get(k) for k in FIELDNAMES}
    row["stats"] = json.dumps(row["stats"], sort_keys=True) if row.get("stats") is not None else ""
    return row


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


def write_stop_info(reason: str, detail: str | None = None) -> None:
    STOP_PATH.write_text(
        json.dumps({"stop_reason": reason, "detail": detail,
                    "stopped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                   indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def budget_deadline(max_wall_hours: float) -> float:
    """Experiment deadline: run_info start_time (persisted at step 2) plus budget."""
    start_epoch = None
    if RUN_INFO_PATH.exists():
        try:
            info = json.loads(RUN_INFO_PATH.read_text(encoding="utf-8"))
            start_epoch = time.mktime(time.strptime(info["start_time"], "%Y-%m-%dT%H:%M:%SZ"))
        except Exception:
            start_epoch = None
    if start_epoch is None:
        start_epoch = time.time()
    return start_epoch + max_wall_hours * 3600.0


def disk_free_bytes() -> int:
    return shutil.disk_usage(str(REPO_ROOT)).free


def run_suite(max_wall_hours: float = MAX_WALL_HOURS, max_wall_minutes: float | None = None,
              force: bool = False) -> dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    matrix = load_matrix()
    calibration = load_calibration()
    totals_c = totals()
    existing_keys = set() if force else load_existing_run_keys(JSONL_PATH)
    if existing_keys:
        print(f"Resuming full_v1: {len(existing_keys)} existing runs found in {JSONL_PATH}")

    csv_exists = CSV_PATH.exists() and not force
    csv_file = open(CSV_PATH, "a" if csv_exists else "w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES, extrasaction="ignore")
    if not csv_exists:
        csv_writer.writeheader()
    jsonl_file = open(JSONL_PATH, "a" if not force else "w", encoding="utf-8")

    summary: dict[str, Any] = {
        "suite_name": "full_v1",
        "records_written": 0,
        "executed_runs": 0,
        "predeclared_excluded_records": 0,
        "live_guard_rejections": 0,
        "status_counts": {},
        "stop_reason": None,
        "stop_detail": None,
        "wall_clock_s": 0.0,
        "completed_cleanly": False,
    }
    t_global = time.monotonic()
    if max_wall_minutes is not None:
        deadline = time.time() + max_wall_minutes * 60.0
    else:
        deadline = budget_deadline(max_wall_hours)
    position = 0
    last_progress = [0.0]

    def remaining_wall_s() -> float:
        return max(0.0, deadline - time.time())

    def check_budget() -> str | None:
        if remaining_wall_s() <= 0:
            return "budget"
        return None

    def check_disk() -> str | None:
        if disk_free_bytes() < DISK_FREE_MIN_BYTES:
            return "disk_free_below_1gb"
        return None

    def emit(reason: str, detail: str | None = None) -> None:
        summary["stop_reason"] = reason
        summary["stop_detail"] = detail
        write_stop_info(reason, detail)
        print(f"STOP: {reason}" + (f" ({detail})" if detail else ""),
              f"wall elapsed {time.monotonic() - t_global:.1f}s", flush=True)

    def progress_note(index: int, config_name: str, rec: dict[str, Any], elapsed: float, eta_s: float | None) -> None:
        now = time.monotonic()
        if now - last_progress[0] < PROGRESS_INTERVAL_S:
            return
        last_progress[0] = now
        parts = [
            f"progress N={rec['N']} index={index} config={config_name}: {rec['status']}",
            f"(t_total={rec.get('t_total')}s)", f"records {summary['records_written']}/{totals_c['sampled_recorded_runs']}",
            f"elapsed {elapsed:.1f}s",
        ]
        if eta_s is not None:
            parts.append(f"ETA {eta_s:.1f}s")
        parts.append(f"available RAM {psutil_ram_gb():.2f} GB")
        parts.append(f"disk free {disk_free_bytes() / 2**30:.2f} GB")
        print(" | ".join(parts), flush=True)

    def psutil_ram_gb() -> float:
        import psutil
        return psutil.virtual_memory().available / 2**30

    try:
        # --- Record predeclared guard exclusions (pairwise/binary at N=81) ---
        for ratio in RATIOS:
            for index in sampled_indices(81, ratio):
                puzzle_rec = next(p for p in load_puzzles(MANIFEST_PATH, sizes=81, ratios=(ratio,),
                                                          index_range=(0, INDICES_PER_PAIR))
                                  if _index_of(p) == index)
                for config_name in ("sat_pairwise_cadical153", "sat_binary_cadical153"):
                    key = make_run_key(puzzle_rec["id"], benchmark_config(config_name))
                    if key in existing_keys:
                        continue
                    rec = excluded_record(puzzle_rec, config_name, position)
                    position += 1
                    append_record(rec, csv_file, csv_writer, jsonl_file)
                    summary["records_written"] += 1
                    summary["predeclared_excluded_records"] += 1
                    summary["status_counts"][rec["status"]] = (
                        summary["status_counts"].get(rec["status"], 0) + 1)

        # --- Stages: N=9, N=36, N=81; sampled index order within stage ---
        for N in SIZES:
            stage_t0 = time.monotonic()
            stage_runs = 0
            stage_solver_errors = 0
            stage_stopped = False
            print(f"=== Stage N={N} ===", flush=True)

            puzzles_by_ratio = {
                r: {(p_id := _index_of(p)): p for p in load_puzzles(MANIFEST_PATH, sizes=N, ratios=(r,),
                                                                    index_range=(0, INDICES_PER_PAIR))}
                for r in RATIOS
            }
            included_names = list(
                dict.fromkeys(
                    row["config"]
                    for row in matrix
                    if int(row["N"]) == N and row["decision"] == "INCLUDE"
                )
            )

            for ratio in RATIOS:
                if stage_stopped:
                    break
                for index in sampled_indices(N, ratio):
                    if stage_stopped:
                        break
                    puzzle_rec = puzzles_by_ratio[ratio][index]
                    rng = random.Random(shuffle_seed(puzzle_rec["id"]))
                    order = rng.sample(included_names, len(included_names))

                    for config_name in order:
                        if stage_stopped:
                            break

                        stop = check_budget() or check_disk()
                        if stop is not None:
                            emit(stop, f"N={N} index={index} ratio={ratio} config={config_name}")
                            stage_stopped = True
                            break

                        cfg = benchmark_config(config_name)
                        key = make_run_key(puzzle_rec["id"], cfg)
                        if key in existing_keys:
                            continue

                        # Live resource-guard safety net (SAT builds only).
                        if cfg.solver == "sat" and cfg.encoding in calibration:
                            clauses = estimate_encoding_clauses(
                                puzzle_rec["N"], cfg.encoding, cfg.encoding_opts,
                                clues=sum(1 for v in puzzle_rec["puzzle"] if v != 0),
                            )
                            bpc = calibration[cfg.encoding]
                            available_ram = _available_ram()
                            if (estimated := int(clauses * bpc)) > int(available_ram * RESOURCE_GUARD_FRACTION):
                                rec = live_guard_record(puzzle_rec, cfg, position, clauses, bpc, available_ram)
                                position += 1
                                append_record(rec, csv_file, csv_writer, jsonl_file)
                                summary["records_written"] += 1
                                summary["live_guard_rejections"] += 1
                                summary["status_counts"][rec["status"]] = (
                                    summary["status_counts"].get(rec["status"], 0) + 1)
                                continue

                        t_run0 = time.monotonic()
                        try:
                            rec = execute_run_subprocess(puzzle_rec, cfg,
                                                         memory_bytes_per_clause=(
                                                             calibration.get(cfg.encoding)
                                                             if cfg.solver == "sat" else None))
                        except Exception as exc:  # runner crash / worker chain failure
                            rec = {
                                **_base_record(puzzle_rec, cfg, position),
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

                        rec = revalidate_solved(rec, puzzle_rec)
                        base = _base_record(puzzle_rec, cfg, position)
                        for key, value in base.items():
                            rec.setdefault(key, value)
                        position += 1
                        append_record(rec, csv_file, csv_writer, jsonl_file)
                        summary["records_written"] += 1
                        summary["executed_runs"] += 1
                        stage_runs += 1
                        st = rec["status"]
                        summary["status_counts"][st] = summary["status_counts"].get(st, 0) + 1
                        if st == STATUS_SOLVER_ERROR:
                            stage_solver_errors += 1

                        elapsed = time.monotonic() - t_global
                        eta_s = None
                        if summary["executed_runs"] > 0:
                            avg = elapsed / summary["executed_runs"]
                            eta_s = avg * (totals_c["sampled_executed_runs"] - summary["executed_runs"])
                        progress_note(index, config_name, rec, elapsed, eta_s)

                        if st in (STATUS_UNSAT_INVESTIGATE, STATUS_INVALID_SOLUTION):
                            emit(st, f"{puzzle_rec['id']} {config_name}")
                            stage_stopped = True
                            break

                        if (stage_runs >= SOLVER_ERROR_MIN_RUNS and
                                stage_solver_errors / stage_runs > SOLVER_ERROR_STAGE_RATE):
                            emit("solver_error_rate_stage",
                                 f"{stage_solver_errors}/{stage_runs} > {SOLVER_ERROR_STAGE_RATE:.0%} at N={N}")
                            stage_stopped = True
                            break

            if stage_stopped:
                break

    finally:
        csv_file.close()
        jsonl_file.close()

    summary["wall_clock_s"] = round(time.monotonic() - t_global, 3)
    summary["completed_cleanly"] = summary["stop_reason"] is None
    return summary


def _available_ram() -> int:
    import psutil
    return int(psutil.virtual_memory().available)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full_v1 primary benchmark matrix")
    parser.add_argument("--max-wall-hours", type=float, default=MAX_WALL_HOURS,
                        help="Hard wall-clock budget in hours (full-design run).")
    parser.add_argument("--max-wall-minutes", type=float, default=None,
                        help="Hard wall-clock budget in minutes (takes precedence over --max-wall-hours).")
    parser.add_argument("--force", action="store_true", help="Overwrite existing result files")
    args = parser.parse_args()

    t_c = totals()
    max_wall_minutes = args.max_wall_minutes
    if max_wall_minutes is None:
        max_wall_minutes = args.max_wall_hours * 60.0
    print(f"full_v1: matrix={MATRIX_PATH.name}, timeout={TIMEOUT_S}s, "
          f"sample_per_pair={SAMPLE_PER_PAIR}, one worker/thread, serial")
    print(f"Matrix: {t_c['cells']} cells ({t_c['included_cells']} included + {t_c['excluded_cells']} predeclared excluded)")
    print(f"Sampled plan: {t_c['sampled_recorded_runs']} recorded runs "
          f"(executed {t_c['sampled_executed_runs']} + "
          f"{t_c['sampled_predeclared_records']} predeclared BUILD_FAIL)")
    print(f"Hard wall-clock budget: {max_wall_minutes:.1f} min ({max_wall_minutes/60:.4f} h)")
    print(f"Worst case (10s x {t_c['sampled_executed_runs']} executed): "
          f"{t_c['sampled_executed_runs'] * TIMEOUT_S:.0f}s = {t_c['sampled_executed_runs'] * TIMEOUT_S / 60:.2f} min")
    summary = run_suite(max_wall_hours=args.max_wall_hours,
                        max_wall_minutes=max_wall_minutes, force=args.force)
    print(json.dumps(summary, indent=2, default=str))
    return 0 if summary["completed_cleanly"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
