#!/usr/bin/env python3
"""Measure isolated CNF build memory and run guarded N=81 build-only probes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sudoku.bench.runner import (  # noqa: E402
    RESOURCE_GUARD_FRACTION,
    RSS_SAMPLING_INTERVAL_S,
    monitor_process,
)
from sudoku.solvers.sat import count_sudoku_cnf, estimate_encoding_clauses  # noqa: E402

ENCODINGS = ("pairwise", "sequential", "binary", "commander", "product")
COMMANDER_OPTS = {"commander_group_size": 4}
BUILD_WORKER = r"""
import gc
import json
import resource
import sys
import time
import psutil
from sudoku.solvers.sat import build_sudoku_cnf

n = int(sys.argv[1])
encoding = sys.argv[2]
opts = json.loads(sys.argv[3])
baseline_rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
baseline_ru_maxrss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
clauses, info = build_sudoku_cnf([0] * (n * n), n, encoding=encoding, opts=opts)
result = {
    "N": n,
    "encoding": encoding,
    "clauses": info["clauses"],
    "aux_vars": info["aux_vars"],
    "t_build": info["t_build"],
    "baseline_rss_mb": baseline_rss_mb,
    "baseline_ru_maxrss_mb": baseline_ru_maxrss_mb,
    "final_ru_maxrss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
}
print(json.dumps(result), flush=True)
del clauses
gc.collect()
"""


def _one_build(n: int, encoding: str, available_ram_bytes: int) -> dict[str, Any]:
    opts = COMMANDER_OPTS if encoding == "commander" else {}
    expected_aux, expected_clauses = count_sudoku_cnf(n, encoding, opts)
    guard_clauses = estimate_encoding_clauses(n, encoding, opts, clues=n * n)
    threshold_bytes = int(available_ram_bytes * RESOURCE_GUARD_FRACTION)
    result: dict[str, Any] = {
        "N": n,
        "encoding": encoding,
        "expected_aux_vars": expected_aux,
        "expected_clauses": expected_clauses,
        "guard_estimated_clauses": guard_clauses,
        "available_ram_bytes_at_start": available_ram_bytes,
        "guard_fraction": RESOURCE_GUARD_FRACTION,
        "guard_threshold_bytes": threshold_bytes,
    }

    if n > 9:
        previous_n = 9 if n == 36 else 36
        previous = _measurements.get((previous_n, encoding))
        if previous is None:
            result.update({"status": "ABORTED_NO_CALIBRATION", "reason": f"missing N={previous_n} measurement"})
            return result
        projected_bytes = int(guard_clauses * previous["bytes_per_clause"])
        result["projected_build_bytes"] = projected_bytes
        if projected_bytes > threshold_bytes:
            result.update({
                "status": "ABORTED_RESOURCE_GUARD",
                "reason": "projected build memory exceeds the predeclared guard",
            })
            return result

    cmd = [
        sys.executable,
        "-c",
        BUILD_WORKER,
        str(n),
        encoding,
        json.dumps(opts),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    started = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    sampled_peak_mb, timed_out = monitor_process(
        proc,
        timeout_s=600,
        sampling_interval_s=RSS_SAMPLING_INTERVAL_S,
    )
    stdout, stderr = proc.communicate()
    if timed_out:
        result.update({"status": "TIMEOUT", "t_total": time.perf_counter() - started, "peak_rss_mb": sampled_peak_mb})
        return result
    if proc.returncode != 0:
        result.update({
            "status": "BUILD_FAIL",
            "t_total": time.perf_counter() - started,
            "peak_rss_mb": sampled_peak_mb,
            "error": stderr.strip(),
        })
        return result
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        result.update({"status": "BUILD_FAIL", "error": "build worker emitted no result", "stderr": stderr.strip()})
        return result

    build = json.loads(lines[-1])
    measured_peak_mb = sampled_peak_mb or 0.0
    if build["final_ru_maxrss_mb"] > build["baseline_ru_maxrss_mb"]:
        measured_peak_mb = max(measured_peak_mb, build["final_ru_maxrss_mb"])
    delta_bytes = max(0.0, measured_peak_mb - build["baseline_rss_mb"]) * (1024 * 1024)
    result.update({
        **build,
        "status": "BUILT",
        "sampled_peak_rss_mb": sampled_peak_mb,
        "peak_rss_mb": round(measured_peak_mb, 2),
        "peak_rss_above_baseline_mb": round(delta_bytes / (1024 * 1024), 2),
        "bytes_per_clause": delta_bytes / build["clauses"],
        "rss_sampling_interval_ms": round(RSS_SAMPLING_INTERVAL_S * 1000),
        "t_total": time.perf_counter() - started,
    })
    if (build["aux_vars"], build["clauses"]) != (expected_aux, expected_clauses):
        result["status"] = "COUNT_MISMATCH"
    return result


def main() -> int:
    global _measurements
    _measurements = {}
    results: list[dict[str, Any]] = []

    for encoding in ENCODINGS:
        for n in (9, 36):
            available_ram_bytes = psutil.virtual_memory().available
            result = _one_build(n, encoding, available_ram_bytes)
            results.append(result)
            print(json.dumps(result), flush=True)
            if result.get("status") == "BUILT":
                _measurements[(n, encoding)] = result

    for encoding in ENCODINGS:
        available_ram_bytes = psutil.virtual_memory().available
        result = _one_build(81, encoding, available_ram_bytes)
        results.append(result)
        print(json.dumps(result), flush=True)
        if result.get("status") == "BUILT":
            _measurements[(81, encoding)] = result

    output = REPO_ROOT / "data" / "results" / "pilot_v2_calibration.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 1 if any(r["status"] == "COUNT_MISMATCH" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
