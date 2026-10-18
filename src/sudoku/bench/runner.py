"""Benchmark runner with subprocess isolation, explicit timeouts, and peak RSS tracking.

Executes solver runs in isolated subprocesses so timeouts are enforced by OS signals
and peak memory (ru_maxrss) is measured cleanly per run.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import resource
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import psutil

REPO_ROOT = Path(__file__).resolve().parents[3]

from ..solvers.base import (
    STATUS_BUILD_FAIL,
    STATUS_INVALID_SOLUTION,
    STATUS_SOLVER_ERROR,
    STATUS_TIMEOUT,
    STATUS_UNSAT_INVESTIGATE,
    SolverResult,
)
from ..solvers.cplex_cp import solve_cplex_cp
from ..solvers.cplex_mip import solve_cplex_mip
from ..solvers.cpsat import solve_cpsat
from ..solvers.gurobi import solve_gurobi
from ..solvers.sat import estimate_encoding_clauses, solve_sat
from sudoku_solver.backtracking import solve_backtracking, Board

RSS_SAMPLING_INTERVAL_S = 0.02
RESOURCE_GUARD_FRACTION = 0.6


def get_peak_rss_mb() -> float:
    """Return peak resident set size of the current process in MiB."""
    # On Linux ru_maxrss is in KiB
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(rss / 1024.0, 2)


@dataclass
class BenchmarkConfig:
    """Configuration for a single solver run."""

    solver: str  # "sat", "cpsat", "gurobi", "cplex_mip", "cplex_cp"
    encoding: str = "pairwise"  # for sat
    backend: str = "minisat22"  # for sat
    threads: int = 1
    timeout_s: float = 10.0
    encoding_opts: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        if self.solver == "sat":
            extra_tag = "_extra_backend" if self.backend == "minisat22" else ""
            return f"sat_{self.encoding}_{self.backend}{extra_tag}"
        return self.solver

    def to_dict(self) -> dict[str, Any]:
        return {
            "solver": self.solver,
            "encoding": self.encoding,
            "backend": self.backend,
            "threads": self.threads,
            "timeout_s": self.timeout_s,
            "encoding_opts": self.encoding_opts,
        }


def make_run_key(puzzle_id: str, cfg: BenchmarkConfig) -> str:
    """Generate unique deterministic key for a puzzle and solver configuration."""
    return f"{puzzle_id}___{cfg.label}"


def run_solver_in_process(puzzle_rec: dict[str, Any], cfg: BenchmarkConfig) -> SolverResult:
    """Dispatch solve call to appropriate solver adapter in the current process."""
    puzzle = puzzle_rec["puzzle"]
    N = puzzle_rec["N"]
    solver = cfg.solver.lower()

    if solver == "sat":
        return solve_sat(
            puzzle=puzzle,
            N=N,
            encoding=cfg.encoding,
            backend=cfg.backend,
            timeout=cfg.timeout_s,
            opts=cfg.encoding_opts,
        )
    elif solver in ("cpsat", "ortools"):
        return solve_cpsat(
            puzzle=puzzle,
            N=N,
            timeout=cfg.timeout_s,
            num_workers=cfg.threads,
        )
    elif solver in ("gurobi", "gurobi_mip"):
        return solve_gurobi(
            puzzle=puzzle,
            N=N,
            timeout=cfg.timeout_s,
            threads=cfg.threads,
        )
    elif solver in ("cplex_mip", "cplex"):
        return solve_cplex_mip(
            puzzle=puzzle,
            N=N,
            timeout=cfg.timeout_s,
            threads=cfg.threads,
        )
    elif solver in ("cplex_cp", "cpoptimizer"):
        return solve_cplex_cp(
            puzzle=puzzle,
            N=N,
            timeout=cfg.timeout_s,
            workers=cfg.threads,
        )
    elif solver == "backtracking":
        # Backtracking solver expects a Board object (list of row lists).
        # puzzle_rec["puzzle"] is a flat list; reshape to N x N grid.
        n = puzzle_rec["N"]
        grid = [puzzle[r * n : (r + 1) * n] for r in range(n)]
        return solve_backtracking(
            board=Board(grid),
            use_ac3=False,
            randomize=False,
        )
    else:
        return SolverResult(
            status=STATUS_SOLVER_ERROR,
            error=f"Unknown solver family: {cfg.solver}",
        )


def execute_single_run_child(puzzle_json: str, config_json: str) -> None:
    """Child process entrypoint: runs one puzzle with one solver configuration."""
    puzzle_rec = json.loads(puzzle_json)
    cfg_dict = json.loads(config_json)
    cfg = BenchmarkConfig(**cfg_dict)

    baseline_rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
    baseline_ru_maxrss_mb = get_peak_rss_mb()
    baseline_path = os.environ.get("SUDOKU_WORKER_BASELINE_FILE")
    if baseline_path:
        Path(baseline_path).write_text(
            json.dumps({
                "worker_baseline_rss_mb": baseline_rss_mb,
                "worker_ru_maxrss_baseline_mb": baseline_ru_maxrss_mb,
            }),
            encoding="utf-8",
        )

    res = run_solver_in_process(puzzle_rec, cfg)
    res.peak_rss_mb = get_peak_rss_mb()

    out_data = res.to_dict()
    out_data["worker_baseline_rss_mb"] = round(baseline_rss_mb, 2)
    out_data["worker_ru_maxrss_baseline_mb"] = round(baseline_ru_maxrss_mb, 2)
    out_data["worker_ru_maxrss_final_mb"] = res.peak_rss_mb
    # Print JSON line for parent process to read
    print(json.dumps(out_data))


def _read_rss_mb(process: psutil.Process) -> float | None:
    try:
        return process.memory_info().rss / (1024 * 1024)
    except psutil.NoSuchProcess:
        return None


def monitor_process(
    proc: subprocess.Popen[str],
    timeout_s: float,
    sampling_interval_s: float = RSS_SAMPLING_INTERVAL_S,
) -> tuple[float | None, bool]:
    """Sample a worker's RSS until exit or timeout, killing its process group on timeout."""
    try:
        worker = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        return None, False
    peak_rss_mb: float | None = None
    deadline = time.monotonic() + timeout_s

    while proc.poll() is None:
        sample = _read_rss_mb(worker)
        if sample is not None:
            peak_rss_mb = max(peak_rss_mb or 0.0, sample)

        remaining_s = deadline - time.monotonic()
        if remaining_s <= 0:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            return peak_rss_mb, True
        time.sleep(min(sampling_interval_s, remaining_s))

    sample = _read_rss_mb(worker)
    if sample is not None:
        peak_rss_mb = max(peak_rss_mb or 0.0, sample)
    return peak_rss_mb, False


def _base_run_record(
    puzzle_rec: dict[str, Any],
    cfg: BenchmarkConfig,
    available_ram_bytes: int,
) -> dict[str, Any]:
    return {
        "run_key": make_run_key(puzzle_rec["id"], cfg),
        "puzzle_id": puzzle_rec["id"],
        "N": puzzle_rec["N"],
        "requested_ratio": puzzle_rec["requested_ratio"],
        "solver": cfg.solver,
        "encoding": cfg.encoding if cfg.solver == "sat" else "",
        "backend": cfg.backend if cfg.solver == "sat" else cfg.solver,
        "threads": cfg.threads,
        "timeout_s": cfg.timeout_s,
        "available_ram_bytes_at_start": available_ram_bytes,
        "rss_sampling_interval_ms": round(RSS_SAMPLING_INTERVAL_S * 1000),
    }


def execute_run_subprocess(
    puzzle_rec: dict[str, Any],
    cfg: BenchmarkConfig,
    memory_bytes_per_clause: float | None = None,
) -> dict[str, Any]:
    """Execute a single run in an isolated subprocess with wall-clock timeout."""
    available_ram_bytes = psutil.virtual_memory().available
    base_record = _base_run_record(puzzle_rec, cfg, available_ram_bytes)

    if cfg.solver == "sat" and memory_bytes_per_clause is not None:
        clauses = estimate_encoding_clauses(
            puzzle_rec["N"],
            cfg.encoding,
            cfg.encoding_opts,
            clues=sum(value != 0 for value in puzzle_rec["puzzle"]),
        )
        estimated_memory_bytes = int(clauses * memory_bytes_per_clause)
        guard_threshold_bytes = int(available_ram_bytes * RESOURCE_GUARD_FRACTION)
        if estimated_memory_bytes > guard_threshold_bytes:
            return {
                **base_record,
                "status": STATUS_BUILD_FAIL,
                "t_build": 0.0,
                "t_solve": 0.0,
                "t_total": 0.0,
                "peak_rss_mb": None,
                "worker_baseline_rss_mb": None,
                "peak_rss_above_baseline_mb": None,
                "stats": {
                    "reason": "RESOURCE_GUARD",
                    "estimated_clauses": clauses,
                    "bytes_per_clause": memory_bytes_per_clause,
                    "estimated_memory_bytes": estimated_memory_bytes,
                    "guard_fraction": RESOURCE_GUARD_FRACTION,
                    "guard_threshold_bytes": guard_threshold_bytes,
                    "available_ram_bytes": available_ram_bytes,
                },
                "error": (
                    f"RESOURCE_GUARD: estimated {estimated_memory_bytes} bytes exceeds "
                    f"{guard_threshold_bytes} bytes ({RESOURCE_GUARD_FRACTION:.0%} of "
                    f"{available_ram_bytes} available bytes)"
                ),
            }

    cmd = [
        sys.executable,
        "-m",
        "sudoku.bench.runner",
        "--single-run",
        json.dumps(puzzle_rec),
        json.dumps(cfg.to_dict()),
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="sudoku-worker-") as temp_dir:
        baseline_file = Path(temp_dir) / "baseline_rss_mb"
        env["SUDOKU_WORKER_BASELINE_FILE"] = str(baseline_file)
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO_ROOT),
            start_new_session=True,
        )
        sampled_peak_rss_mb, timed_out = monitor_process(proc, cfg.timeout_s)
        stdout, stderr = proc.communicate()
        t_elapsed = time.perf_counter() - t0

        baseline_data = (
            json.loads(baseline_file.read_text(encoding="utf-8"))
            if baseline_file.exists()
            else {}
        )
        baseline_rss_mb = baseline_data.get("worker_baseline_rss_mb")
        baseline_ru_maxrss_mb = baseline_data.get("worker_ru_maxrss_baseline_mb")
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        child_result: dict[str, Any] = {}
        if lines and not timed_out:
            try:
                child_result = json.loads(lines[-1])
            except json.JSONDecodeError:
                child_result = {}

        child_ru_maxrss_mb = child_result.get("worker_ru_maxrss_final_mb")
        if (
            child_ru_maxrss_mb is not None
            and child_result.get("worker_ru_maxrss_baseline_mb") is not None
            and child_ru_maxrss_mb > child_result["worker_ru_maxrss_baseline_mb"]
        ):
            child_peak_rss_mb = child_ru_maxrss_mb
        else:
            child_peak_rss_mb = None
        peak_rss_mb = max(
            (rss for rss in (sampled_peak_rss_mb, child_peak_rss_mb) if rss is not None),
            default=None,
        )
        baseline_rss_mb = child_result.get("worker_baseline_rss_mb", baseline_rss_mb)
        baseline_ru_maxrss_mb = child_result.get(
            "worker_ru_maxrss_baseline_mb",
            baseline_ru_maxrss_mb,
        )
        peak_above_baseline_mb = (
            max(0.0, peak_rss_mb - baseline_rss_mb)
            if peak_rss_mb is not None and baseline_rss_mb is not None
            else None
        )

        if timed_out:
            return {
                **base_record,
                "status": STATUS_TIMEOUT,
                "t_build": None,
                "t_solve": None,
                "t_total": round(t_elapsed, 6),
                "peak_rss_mb": round(peak_rss_mb, 2) if peak_rss_mb is not None else None,
                "worker_baseline_rss_mb": round(baseline_rss_mb, 2) if baseline_rss_mb is not None else None,
                "worker_ru_maxrss_baseline_mb": round(baseline_ru_maxrss_mb, 2) if baseline_ru_maxrss_mb is not None else None,
                "worker_ru_maxrss_final_mb": None,
                "peak_rss_above_baseline_mb": round(peak_above_baseline_mb, 2) if peak_above_baseline_mb is not None else None,
                "phase_at_kill": "unknown",
                "stats": {"timeout_s": cfg.timeout_s},
                "error": f"Wall-clock timeout expired after {cfg.timeout_s}s (phase at kill unknown)",
            }

        if proc.returncode != 0:
            return {
                **base_record,
                "status": STATUS_SOLVER_ERROR,
                "t_build": 0.0,
                "t_solve": 0.0,
                "t_total": round(t_elapsed, 6),
                "peak_rss_mb": round(peak_rss_mb, 2) if peak_rss_mb is not None else None,
                "worker_baseline_rss_mb": round(baseline_rss_mb, 2) if baseline_rss_mb is not None else None,
                "worker_ru_maxrss_baseline_mb": round(baseline_ru_maxrss_mb, 2) if baseline_ru_maxrss_mb is not None else None,
                "worker_ru_maxrss_final_mb": child_ru_maxrss_mb,
                "peak_rss_above_baseline_mb": round(peak_above_baseline_mb, 2) if peak_above_baseline_mb is not None else None,
                "stats": {},
                "error": f"Child process failed (code {proc.returncode}): {stderr.strip()}",
            }

        if not child_result:
            return {
                **base_record,
                "status": STATUS_SOLVER_ERROR,
                "t_build": 0.0,
                "t_solve": 0.0,
                "t_total": round(t_elapsed, 6),
                "peak_rss_mb": round(peak_rss_mb, 2) if peak_rss_mb is not None else None,
                "worker_baseline_rss_mb": round(baseline_rss_mb, 2) if baseline_rss_mb is not None else None,
                "worker_ru_maxrss_baseline_mb": round(baseline_ru_maxrss_mb, 2) if baseline_ru_maxrss_mb is not None else None,
                "worker_ru_maxrss_final_mb": child_ru_maxrss_mb,
                "peak_rss_above_baseline_mb": round(peak_above_baseline_mb, 2) if peak_above_baseline_mb is not None else None,
                "stats": {},
                "error": "No valid JSON result received from solver child process",
            }

        return {
            **base_record,
            "status": child_result["status"],
            "solution": child_result.get("solution"),
            "t_build": child_result.get("t_build", 0.0),
            "t_solve": child_result.get("t_solve", 0.0),
            "t_total": child_result.get("t_total", round(t_elapsed, 6)),
            "peak_rss_mb": round(peak_rss_mb, 2) if peak_rss_mb is not None else None,
            "worker_baseline_rss_mb": round(baseline_rss_mb, 2) if baseline_rss_mb is not None else None,
            "worker_ru_maxrss_baseline_mb": round(baseline_ru_maxrss_mb, 2) if baseline_ru_maxrss_mb is not None else None,
            "worker_ru_maxrss_final_mb": child_ru_maxrss_mb,
            "peak_rss_above_baseline_mb": round(peak_above_baseline_mb, 2) if peak_above_baseline_mb is not None else None,
            "stats": child_result.get("stats", {}),
            "error": child_result.get("error"),
        }


def load_existing_run_keys(results_jsonl: Path) -> set[str]:
    """Read existing run keys from JSONL to support safe resumption."""
    if not results_jsonl.exists():
        return set()
    keys = set()
    with open(results_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    d = json.loads(line)
                    if "run_key" in d:
                        keys.add(d["run_key"])
                except Exception:
                    pass
    return keys


def run_benchmark_suite(
    puzzles: Sequence[dict[str, Any]],
    configs: Sequence[BenchmarkConfig],
    output_dir: Path | str = "data/results",
    suite_name: str = "pilot",
    force: bool = False,
    memory_bytes_per_clause: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Execute a matrix of puzzles and solver configurations with resume support."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = out_dir / f"{suite_name}.jsonl"
    csv_path = out_dir / f"{suite_name}.csv"
    meta_path = out_dir / f"{suite_name}_meta.json"

    existing_keys = set() if force else load_existing_run_keys(jsonl_path)
    if existing_keys:
        print(f"Resuming benchmark: {len(existing_keys)} existing runs found in {jsonl_path}")

    # Metadata record
    meta = {
        "suite_name": suite_name,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "total_puzzles": len(puzzles),
        "total_configs": len(configs),
        "planned_runs": len(puzzles) * len(configs),
        "timeout_s": sorted({cfg.timeout_s for cfg in configs}),
        "rss_sampling_interval_ms": round(RSS_SAMPLING_INTERVAL_S * 1000),
        "resource_guard_fraction": RESOURCE_GUARD_FRACTION,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    fieldnames = [
        "run_key", "puzzle_id", "N", "requested_ratio", "solver",
        "encoding", "backend", "threads", "timeout_s", "status",
        "t_build", "t_solve", "t_total", "available_ram_bytes_at_start",
        "peak_rss_mb", "worker_baseline_rss_mb", "worker_ru_maxrss_baseline_mb",
        "worker_ru_maxrss_final_mb", "peak_rss_above_baseline_mb",
        "rss_sampling_interval_ms", "phase_at_kill", "stats", "error",
    ]

    csv_exists = csv_path.exists() and not force
    csv_file = open(csv_path, "a" if csv_exists else "w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
    if not csv_exists:
        csv_writer.writeheader()

    jsonl_file = open(jsonl_path, "a" if not force else "w", encoding="utf-8")

    all_results: list[dict[str, Any]] = []
    total_runs = len(puzzles) * len(configs)
    current_idx = 0

    print(f"\nRunning benchmark suite '{suite_name}': {len(puzzles)} puzzles x {len(configs)} configs = {total_runs} runs.")

    try:
        for p in puzzles:
            for cfg in configs:
                current_idx += 1
                key = make_run_key(p["id"], cfg)
                if key in existing_keys:
                    continue

                print(f"[{current_idx}/{total_runs}] Running {p['id']} with {cfg.label} ... ", end="", flush=True)
                run_res = execute_run_subprocess(
                    p,
                    cfg,
                    memory_bytes_per_clause=(
                        memory_bytes_per_clause.get(cfg.encoding)
                        if memory_bytes_per_clause and cfg.solver == "sat"
                        else None
                    ),
                )
                all_results.append(run_res)

                # Incremental persistence
                jsonl_file.write(json.dumps(run_res) + "\n")
                jsonl_file.flush()
                csv_writer.writerow(run_res)
                csv_file.flush()

                status = run_res["status"]
                t_tot = run_res["t_total"]
                t_sol = run_res["t_solve"]
                solve_text = f"{t_sol:.3f}s" if t_sol is not None else "unknown"
                rss = run_res.get("peak_rss_mb", "-")
                print(f"{status} (solve: {solve_text}, total: {t_tot:.3f}s, rss: {rss}MB)")
                if status in (STATUS_UNSAT_INVESTIGATE, STATUS_INVALID_SOLUTION):
                    print(f"Stopping suite after {status}; investigate this result before continuing.")
                    break
    finally:
        csv_file.close()
        jsonl_file.close()

    return all_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Sudoku Benchmark Subprocess Runner")
    parser.add_argument("--single-run", nargs=2, metavar=("PUZZLE_JSON", "CONFIG_JSON"),
                        help="Execute single run child process")
    args = parser.parse_args()

    if args.single_run:
        execute_single_run_child(args.single_run[0], args.single_run[1])
        sys.exit(0)


if __name__ == "__main__":
    main()
