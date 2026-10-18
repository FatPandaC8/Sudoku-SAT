from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from sudoku.bench.runner import BenchmarkConfig, execute_run_subprocess, monitor_process
from sudoku.solvers.sat import build_sudoku_cnf, count_sudoku_cnf


ENCODINGS = ("pairwise", "sequential", "binary", "commander", "product")
COMMANDER_OPTS = {"commander_group_size": 4}


def documented_counts(n: int, encoding: str) -> tuple[int, int]:
    groups = 4 * n * n
    if encoding == "pairwise":
        aux_per_group = 0
        clauses_per_group = 1 + n * (n - 1) // 2
    elif encoding == "sequential":
        aux_per_group = max(0, n - 1)
        clauses_per_group = 1 + max(0, 3 * n - 4)
    elif encoding == "binary":
        bits = math.ceil(math.log2(n)) if n > 1 else 0
        aux_per_group = bits
        clauses_per_group = 1 + n * bits
    elif encoding == "commander":
        size = COMMANDER_OPTS["commander_group_size"]
        parts = [min(size, n - start) for start in range(0, n, size)]
        aux_per_group = len(parts)
        commander_pairs = len(parts) * (len(parts) - 1) // 2
        member_pairs = sum(part * (part - 1) // 2 for part in parts)
        clauses_per_group = 1 + n + commander_pairs + member_pairs
    else:
        rows = max(1, math.ceil(math.sqrt(n)))
        cols = math.ceil(n / rows)
        aux_per_group = rows + cols
        clauses_per_group = 1 + 2 * n + rows * (rows - 1) // 2 + cols * (cols - 1) // 2
    return groups * aux_per_group, groups * clauses_per_group


@pytest.mark.parametrize("n", [9, 36])
@pytest.mark.parametrize("encoding", ENCODINGS)
def test_measured_build_counts_match_documented_formulas(n: int, encoding: str) -> None:
    opts = COMMANDER_OPTS if encoding == "commander" else None
    _, info = build_sudoku_cnf([0] * (n * n), n, encoding=encoding, opts=opts)
    assert (info["aux_vars"], info["clauses"]) == documented_counts(n, encoding)


@pytest.mark.parametrize("encoding", ENCODINGS)
def test_n81_counts_without_storing_cnf(encoding: str) -> None:
    opts = COMMANDER_OPTS if encoding == "commander" else None
    assert count_sudoku_cnf(81, encoding, opts) == documented_counts(81, encoding)


def _run_rss_worker(allocation_mb: int) -> tuple[float, dict[str, float]]:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    worker_code = """
import json, resource, sys, time
import psutil
import sudoku.bench.runner
baseline = psutil.Process().memory_info().rss / (1024 * 1024)
ru_baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
allocation_mb = int(sys.argv[1])
buffer = bytearray(allocation_mb * 1024 * 1024)
for offset in range(0, len(buffer), 4096):
    buffer[offset] = 1
time.sleep(0.3)
ru_final = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
print(json.dumps({"baseline": baseline, "ru_baseline": ru_baseline, "ru_final": ru_final}))
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", worker_code, str(allocation_mb)],
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    sampled_peak, timed_out = monitor_process(proc, timeout_s=15, sampling_interval_s=0.01)
    stdout, stderr = proc.communicate()
    assert not timed_out
    assert proc.returncode == 0, stderr
    report = json.loads(stdout.strip().splitlines()[-1])
    assert sampled_peak is not None
    ru_peak = report["ru_final"] if report["ru_final"] > report["ru_baseline"] else 0
    return max(sampled_peak, ru_peak), report


def test_parent_sampling_measures_allocations_and_distinguishes_workers() -> None:
    large_peak, large = _run_rss_worker(320)
    assert large_peak - large["baseline"] >= 300

    smaller_peak, smaller = _run_rss_worker(32)
    larger_peak, larger = _run_rss_worker(128)
    assert smaller["ru_final"] == smaller["ru_baseline"]
    assert larger["ru_final"] == larger["ru_baseline"]
    smaller_delta = smaller_peak - smaller["baseline"]
    larger_delta = larger_peak - larger["baseline"]
    assert larger_delta - smaller_delta >= 80


def test_parent_sampling_keeps_peak_for_killed_worker() -> None:
    worker_code = (
        "import time; data=bytearray(96*1024*1024); "
        "[(data.__setitem__(i, 1)) for i in range(0, len(data), 4096)]; "
        "time.sleep(5)"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", worker_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    peak_rss_mb, timed_out = monitor_process(proc, timeout_s=0.3, sampling_interval_s=0.01)
    stdout, stderr = proc.communicate()
    assert timed_out
    assert proc.returncode == -signal.SIGKILL
    assert not stdout
    assert not stderr
    assert peak_rss_mb is not None
    assert peak_rss_mb >= 96


def test_completed_run_records_available_memory_and_worker_rss() -> None:
    puzzle_rec = {
        "id": "measurement-smoke",
        "N": 4,
        "requested_ratio": 0.0,
        "puzzle": [0] * 16,
    }
    result = execute_run_subprocess(
        puzzle_rec,
        BenchmarkConfig(
            solver="sat",
            encoding="sequential",
            backend="cadical153",
            timeout_s=10,
        ),
    )
    assert result["status"] == "SOLVED_VALID"
    assert result["available_ram_bytes_at_start"] > 0
    assert result["peak_rss_mb"] >= result["worker_baseline_rss_mb"]
    assert result["worker_ru_maxrss_final_mb"] is not None
    assert result["peak_rss_above_baseline_mb"] >= 0
