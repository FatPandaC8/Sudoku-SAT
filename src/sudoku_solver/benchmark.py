"""Common benchmark runner: subprocess execution, timeouts, memory, storage.

Every run executes in its own process so wall-clock timeouts and peak-memory
measurement are reliable.  Raw run-level records are written incrementally
(CSV summary + JSONL detail); aggregation happens in analysis/plotting only.

Run identity: a stable ``run_key`` derived from puzzle id, solver config,
and repetition, so interrupted benchmarks resume without duplicating work.
"""

from __future__ import annotations

import csv
import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .puzzle import Board, SolverResult, validate_solution

# --- configuration ---------------------------------------------------------

DEFAULT_CONFIG: dict = {
    "sizes": [9],
    "difficulties": ["easy", "medium", "hard"],
    "puzzles_per_category": 2,
    "timeout": 30.0,
    "repetitions": 1,
    "puzzle_dir": "data/puzzles",
    "output_dir": "data/results",
    "generation_seed": 42,
    "generation_timeout": 120.0,
    "solver_configs": [
        {"solver": "backtracking"},
        {"solver": "backtracking", "use_ac3": True},
        {"solver": "cpsat"},
        {"solver": "sat", "encoding": "pairwise", "backend": "minisat22"},
    ],
}


@dataclass
class SolverConfig:
    """One solver configuration to benchmark."""

    solver: str  # "backtracking" | "cpsat" | "sat"
    encoding: str | None = None
    backend: str | None = None
    use_ac3: bool = False
    encoding_opts: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        parts = [self.solver]
        if self.solver == "sat":
            parts += [self.encoding or "?", self.backend or "?"]
        if self.solver == "backtracking" and self.use_ac3:
            parts.append("ac3")
        for k, v in sorted(self.encoding_opts.items()):
            parts.append(f"{k}={v}")
        return "/".join(parts)

    @property
    def family(self) -> str:
        return self.solver

    def to_dict(self) -> dict:
        d: dict = {"solver": self.solver}
        if self.encoding:
            d["encoding"] = self.encoding
        if self.backend:
            d["backend"] = self.backend
        if self.use_ac3:
            d["use_ac3"] = True
        if self.encoding_opts:
            d["encoding_opts"] = dict(self.encoding_opts)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SolverConfig":
        known = {"solver", "encoding", "backend", "use_ac3", "encoding_opts"}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"unknown solver config keys: {sorted(unknown)}")
        return cls(
            solver=d["solver"],
            encoding=d.get("encoding"),
            backend=d.get("backend"),
            use_ac3=bool(d.get("use_ac3", False)),
            encoding_opts=dict(d.get("encoding_opts", {})),
        )


def load_config(path: str | Path) -> dict:
    """Load a TOML benchmark config, merged over defaults."""
    import tomllib

    data = tomllib.loads(Path(path).read_text())
    cfg = dict(DEFAULT_CONFIG)
    user = data.get("benchmark", data)
    cfg.update(user)
    return cfg


# --- environment -----------------------------------------------------------

def environment_info() -> dict:
    """Software versions and hardware details for reproducibility records."""
    import importlib.metadata as md

    versions = {}
    for pkg in ("python-sat", "ortools", "matplotlib", "psutil", "pytest"):
        try:
            versions[pkg] = md.version(pkg)
        except Exception:
            versions[pkg] = "not installed"
    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": None,
        "total_memory_mb": None,
        "packages": versions,
    }
    try:
        import os

        info["cpu_count"] = os.cpu_count()
    except Exception:
        pass
    try:
        import psutil

        info["total_memory_mb"] = round(psutil.virtual_memory().total / (1024 * 1024))
    except Exception:
        pass
    return info


# --- in-process dispatch ---------------------------------------------------

def run_solver(puzzle: Board, config: SolverConfig) -> SolverResult:
    """Run one solver configuration in this process."""
    if config.solver == "backtracking":
        from .backtracking import BacktrackingSolver

        return BacktrackingSolver(puzzle, use_ac3=config.use_ac3).solve()
    if config.solver == "cpsat":
        from .cpsat_solver import solve_cpsat

        return solve_cpsat(puzzle)
    if config.solver == "sat":
        from .sat_solver import solve_sat

        return solve_sat(
            puzzle,
            encoding=config.encoding or "pairwise",
            backend=config.backend or "minisat22",
            encoding_opts=config.encoding_opts or None,
        )
    raise ValueError(f"unknown solver {config.solver!r}")


# --- subprocess execution --------------------------------------------------

def _peak_rss_mb() -> float | None:
    """Peak resident set size of *this* process, in MB (Linux ru_maxrss is KB)."""
    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(rss / 1024.0, 2)
    except Exception:
        return None


def _single_run(puzzle_path: str, config_dict: dict) -> dict:
    """Execute one run in-process and return a JSON-safe result record."""
    from .generator import load_puzzle

    config = SolverConfig.from_dict(config_dict)
    puzzle, _solution, record = load_puzzle(puzzle_path)
    t0 = time.perf_counter()
    try:
        result = run_solver(puzzle, config)
    except Exception as exc:
        result = SolverResult(
            status="error", runtime=time.perf_counter() - t0,
            error=f"{type(exc).__name__}: {exc}",
        )
    validated = False
    if result.board is not None:
        validated = not validate_solution(result.board, puzzle)
        if not validated and result.status == "solved":
            result.status = "error"
            result.error = "solution failed validation"
    return {
        "puzzle_id": record.get("puzzle_id", Path(puzzle_path).stem),
        "size": record.get("size", puzzle.size),
        "difficulty": record.get("difficulty", "unknown"),
        "solver_family": config.family,
        "solver_config": config.label,
        "encoding": config.encoding or "",
        "backend": config.backend or (
            "ortools-cpsat" if config.solver == "cpsat"
            else ("reference-bt" if config.solver == "backtracking" else "")
        ),
        "status": result.status,
        "runtime": round(result.runtime, 6),
        "validated": validated,
        "peak_rss_mb": _peak_rss_mb(),
        "error": result.error or "",
        "stats": result.stats,
    }


def execute_run(
    puzzle_path: str,
    config_dict: dict,
    timeout: float,
    run_key: str,
) -> dict:
    """Run one puzzle/config pair in a subprocess with a wall-clock timeout.

    On timeout the child is killed and the record keeps status ``timeout``;
    partial output is never treated as a result.
    """
    cfg = SolverConfig.from_dict(config_dict)
    cmd = [
        sys.executable, "-m", "sudoku_solver.benchmark",
        "--single", puzzle_path, json.dumps(config_dict),
    ]
    import os

    env = dict(os.environ)  # inherit (LD_LIBRARY_PATH etc.), then pin PYTHONPATH
    src_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = (
        src_root + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    )
    t0 = time.perf_counter()

    def _fail(status: str, error: str, runtime: float) -> dict:
        return {
            "run_key": run_key, "puzzle_id": Path(puzzle_path).stem,
            "status": status, "runtime": round(runtime, 6),
            "validated": False, "error": error,
            "solver_family": cfg.family, "solver_config": cfg.label,
            "encoding": config_dict.get("encoding") or "",
            "backend": config_dict.get("backend") or "",
            "size": "", "difficulty": "", "peak_rss_mb": None, "stats": {},
        }

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return _fail("timeout", f"wall-clock timeout ({timeout}s)", timeout)
    wall = time.perf_counter() - t0
    if proc.returncode != 0:
        return _fail(
            "error",
            f"child failed (rc={proc.returncode}): "
            f"{(proc.stderr or proc.stdout)[-500:]}",
            wall,
        )
    try:
        row = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return _fail(
            "error", f"unreadable child output ({exc}): {proc.stdout[-500:]}", wall
        )
    row["run_key"] = run_key
    return row


# --- persistence -----------------------------------------------------------

CSV_COLUMNS = [
    "run_key", "puzzle_id", "size", "difficulty", "solver_family",
    "solver_config", "encoding", "backend", "status", "runtime",
    "validated", "peak_rss_mb", "cnf_vars", "cnf_clauses",
    "sat_conflicts", "sat_propagations", "bt_nodes", "bt_decisions",
    "bt_backtracks", "bt_propagations", "cpsat_branches", "cpsat_conflicts",
    "error",
]

# Stats keys copied from JSONL detail into flat CSV columns.
_STAT_MAP = {
    "cnf_vars": "total_vars",
    "cnf_clauses": "clauses",
    "sat_conflicts": "conflicts",
    "sat_propagations": "propagations",
    "bt_nodes": "nodes",
    "bt_decisions": "decisions",
    "bt_backtracks": "backtracks",
    "bt_propagations": "propagation_steps",
    "cpsat_branches": "branches",
    "cpsat_conflicts": "conflicts",
}


def _flatten(row: dict) -> dict:
    stats = row.get("stats") or {}
    flat = {col: row.get(col, "") for col in CSV_COLUMNS}
    family = row.get("solver_family", "")
    for col, key in _STAT_MAP.items():
        # Keep solver-specific counters from leaking across families
        # ('conflicts' exists in both SAT and CP-SAT stats).
        if col.startswith("sat_") and family != "sat":
            continue
        if col.startswith("cpsat_") and family != "cpsat":
            continue
        if col.startswith("bt_") and family != "backtracking":
            continue
        if key in stats and stats[key] is not None:
            flat[col] = stats[key]
    flat["peak_rss_mb"] = row.get("peak_rss_mb", "")
    return flat


class RunStore:
    """Incremental CSV + JSONL persistence with resume support."""

    def __init__(self, out_dir: str | Path) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.out_dir / "runs.csv"
        self.jsonl_path = self.out_dir / "runs.jsonl"

    def completed_keys(self) -> set[str]:
        keys: set[str] = set()
        if self.csv_path.exists():
            with self.csv_path.open(newline="") as fh:
                for rec in csv.DictReader(fh):
                    if rec.get("run_key"):
                        keys.add(rec["run_key"])
        return keys

    def append(self, row: dict) -> None:
        flat = _flatten(row)
        new_csv = not self.csv_path.exists()
        with self.csv_path.open("a", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
            if new_csv:
                writer.writeheader()
            writer.writerow(flat)
        with self.jsonl_path.open("a") as fh:
            fh.write(json.dumps(row, default=str) + "\n")

    def rows(self) -> list[dict]:
        if not self.jsonl_path.exists():
            return []
        with self.jsonl_path.open() as fh:
            return [json.loads(line) for line in fh if line.strip()]


# --- main benchmark loop ---------------------------------------------------

def run_key_for(puzzle_id: str, config: SolverConfig, repetition: int) -> str:
    """Stable identity of one puzzle x config x repetition combination."""
    return f"{puzzle_id}|{config.label}|r{repetition}"


def run_benchmark(config: dict, quiet: bool = False) -> dict:
    """Run all configured experiments; resumable; returns a summary dict.

    Missing puzzle datasets are generated first (same saved instances for
    every solver).  Completed run keys are skipped, so re-running after an
    interruption continues without duplicating records.
    """
    from .generator import GenerationError, generate, save_puzzle

    def log(msg: str) -> None:
        if not quiet:
            print(msg, flush=True)

    # Deterministic seed derivation (str.hash is process-randomized — never use it).
    diff_offsets = {"easy": 0, "medium": 31, "hard": 62}
    puzzle_dir = Path(config["puzzle_dir"])
    out_dir = Path(config["output_dir"])
    timeout = float(config["timeout"])
    repetitions = int(config.get("repetitions", 1))
    solver_configs = [
        SolverConfig.from_dict(d) for d in config["solver_configs"]
    ]

    # 1. Ensure the dataset exists (generated once, then reused by everyone).
    puzzle_paths: list[Path] = []
    for size in config["sizes"]:
        for difficulty in config["difficulties"]:
            existing = sorted(
                (puzzle_dir / f"{size}x{size}").glob(f"{size}x{size}_{difficulty}_*.json")
            ) if (puzzle_dir / f"{size}x{size}").exists() else []
            for idx in range(len(existing), int(config["puzzles_per_category"])):
                seed = (
                    int(config.get("generation_seed", 42))
                    + size * 1000
                    + idx * 7
                    + diff_offsets.get(difficulty, 99)
                )
                try:
                    gen = generate(
                        size=size, difficulty=difficulty, seed=seed,
                        timeout=float(config.get("generation_timeout", 120.0)),
                    )
                except (GenerationError, Exception) as exc:
                    log(f"  generation FAILED {size}x{size} {difficulty} #{idx}: {exc}")
                    continue
                path = save_puzzle(puzzle_dir, size, difficulty, idx, gen)
                log(
                    f"  generated {Path(path).name}: "
                    f"{gen.metadata['clue_count']} clues "
                    f"(target {gen.metadata['target_clues']}, "
                    f"reached={gen.metadata['target_reached']})"
                )
            puzzle_paths.extend(
                sorted((puzzle_dir / f"{size}x{size}").glob(f"*_{difficulty}_*.json"))
            )

    # De-duplicate while keeping order.
    seen: set[str] = set()
    unique_paths: list[Path] = []
    for p in puzzle_paths:
        if str(p) not in seen:
            seen.add(str(p))
            unique_paths.append(p)
    puzzle_paths = unique_paths

    if not puzzle_paths:
        raise SystemExit(f"no puzzles found under {puzzle_dir}")

    # 2. Persist environment + effective config for reproducibility.
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "environment.json").write_text(json.dumps(environment_info(), indent=2))
    (out_dir / "config_used.json").write_text(
        json.dumps(config, indent=2, default=str)
    )

    # 3. Execute runs, skipping completed keys.
    store = RunStore(out_dir)
    done = store.completed_keys()
    total = skipped = recorded = 0
    status_counts: dict[str, int] = {}
    for path in puzzle_paths:
        for scfg in solver_configs:
            for rep in range(repetitions):
                key = run_key_for(path.stem, scfg, rep)
                total += 1
                if key in done:
                    skipped += 1
                    continue
                row = execute_run(str(path), scfg.to_dict(), timeout, key)
                store.append(row)
                recorded += 1
                status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
                log(
                    f"  [{recorded}] {path.stem} {scfg.label} rep{rep}: "
                    f"{row['status']} {row['runtime']}s"
                )

    summary = {
        "puzzles": len(puzzle_paths),
        "configs": len(solver_configs),
        "repetitions": repetitions,
        "total_planned_runs": total,
        "skipped_completed": skipped,
        "recorded_now": recorded,
        "status_counts": status_counts,
        "output_dir": str(out_dir),
    }
    log(
        f"benchmark done: {recorded} recorded, {skipped} skipped (already done), "
        f"statuses={status_counts}"
    )
    return summary


# --- plotting utilities ----------------------------------------------------
# Matplotlib-only analysis over saved results; never re-runs solvers.
# Solver-specific counters (SAT conflicts, backtracking nodes, CP-SAT
# branches) are plotted on separate axes — they are not comparable units.

def load_rows(results_dir: str | Path) -> list[dict]:
    """Load raw run records from a results directory (JSONL preferred)."""
    store = RunStore(results_dir)
    rows = store.rows()
    if rows:
        return rows
    csv_path = Path(results_dir) / "runs.csv"
    if csv_path.exists():
        with csv_path.open(newline="") as fh:
            return list(csv.DictReader(fh))
    return []


def filter_rows(
    rows: list[dict],
    size: int | None = None,
    difficulty: str | None = None,
    solver: str | None = None,
    encoding: str | None = None,
    backend: str | None = None,
) -> list[dict]:
    """Filter run records; each filter is optional and matches exactly."""
    out = []
    for row in rows:
        if size is not None and str(row.get("size")) != str(size):
            continue
        if difficulty is not None and row.get("difficulty") != difficulty:
            continue
        if solver is not None and row.get("solver_family") != solver:
            continue
        if encoding is not None and row.get("encoding") != encoding:
            continue
        if backend is not None and row.get("backend") != backend:
            continue
        out.append(row)
    return out


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _is_solved(row: dict) -> bool:
    return row.get("status") == "solved" and str(row.get("validated")) in (
        "True", "true", "1"
    )


def _as_float(val, default: float | None = None) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _grouped_key(row: dict) -> str:
    return str(row.get("solver_config") or row.get("solver_family") or "?")


def plot_runtime(rows: list[dict], path: str | Path) -> None:
    """Median runtime by solver config, grouped by size and difficulty.

    Bars show solved-run medians (log scale); timeout/error counts are
    annotated so summaries never hide failed instances.
    """
    plt = _plt()
    sizes = sorted({str(r.get("size")) for r in rows if r.get("size") not in ("", None)})
    diffs = sorted({str(r.get("difficulty")) for r in rows if r.get("difficulty")})
    configs = sorted({_grouped_key(r) for r in rows})
    if not sizes or not diffs or not configs:
        plt.close("all")
        return
    fig, axes = plt.subplots(1, len(sizes), figsize=(5.5 * len(sizes), 4.5),
                             squeeze=False)
    import statistics

    width = 0.8 / max(len(configs), 1)
    for ax, size in zip(axes[0], sizes):
        xs = range(len(diffs))
        for ci, cfg in enumerate(configs):
            medians, notes = [], []
            for diff in diffs:
                grp = [r for r in rows
                       if str(r.get("size")) == size
                       and r.get("difficulty") == diff
                       and _grouped_key(r) == cfg]
                solved = [t for r in grp if _is_solved(r)
                          for t in [_as_float(r.get("runtime"))] if t is not None]
                failed = sum(1 for r in grp if not _is_solved(r))
                medians.append(statistics.median(solved) if solved else None)
                notes.append(failed)
            xpos = [x + ci * width for x in xs]
            heights = [m if m is not None else 0 for m in medians]
            ax.bar(xpos, heights, width=width, label=cfg)
            for x, m, failed in zip(xpos, medians, notes):
                if m is None and failed:
                    ax.annotate(f"{failed} fail", (x, 0.0001), fontsize=7,
                                rotation=90, ha="center", va="bottom", color="red")
                elif failed:
                    ax.annotate(f"+{failed}to/fail", (x, m), fontsize=6,
                                ha="center", va="bottom", color="red")
        ax.set_xticks(list(xs))
        ax.set_xticklabels(diffs)
        ax.set_yscale("log")
        ax.set_xlabel("difficulty")
        ax.set_ylabel("median runtime (s, solved runs)")
        ax.set_title(f"{size}x{size}")
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_cactus(rows: list[dict], path: str | Path) -> None:
    """Cactus plot: instances solved within each runtime threshold.

    Timeouts/errors are excluded from the curves but annotated explicitly
    per configuration — never silently dropped from the summary.
    """
    plt = _plt()
    import statistics

    configs = sorted({_grouped_key(r) for r in rows})
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for cfg in configs:
        grp = [r for r in rows if _grouped_key(r) == cfg]
        times = sorted(t for r in grp if _is_solved(r)
                       for t in [_as_float(r.get("runtime"))] if t is not None)
        failed = sum(1 for r in grp if not _is_solved(r))
        timeouts = sum(1 for r in grp if r.get("status") == "timeout")
        label = f"{cfg} (n={len(times)}, {timeouts} timeout"
        label += "s)" if timeouts != 1 else ")"
        if failed > timeouts:
            label = f"{cfg} (n={len(times)}, {failed} failed)"
        if times:
            ax.step(times, range(1, len(times) + 1), where="post", label=label)
    ax.set_xscale("log")
    ax.set_xlabel("runtime (s) — log scale")
    ax.set_ylabel("instances solved")
    ax.set_title("Cactus plot (timeouts annotated in legend)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_solved_rate(rows: list[dict], path: str | Path) -> None:
    """Fraction of instances solved (validated) within the time limit."""
    plt = _plt()
    configs = sorted({_grouped_key(r) for r in rows})
    sizes = sorted({str(r.get("size")) for r in rows if r.get("size") not in ("", None)})
    fig, ax = plt.subplots(figsize=(max(6.0, 1.1 * len(configs)), 4.5))
    width = 0.8 / max(len(sizes), 1)
    for si, size in enumerate(sizes):
        rates, totals = [], []
        for cfg in configs:
            grp = [r for r in rows if _grouped_key(r) == cfg
                   and str(r.get("size")) == size]
            total = len(grp)
            solved = sum(1 for r in grp if _is_solved(r))
            rates.append(solved / total if total else 0.0)
            totals.append(total)
        xpos = [x + si * width for x in range(len(configs))]
        ax.bar(xpos, rates, width=width, label=f"{size}x{size}")
        for x, rate, total in zip(xpos, rates, totals):
            ax.annotate(f"{round(rate * total)}/{total}", (x, rate), fontsize=6,
                        ha="center", va="bottom")
    ax.set_xticks(range(len(configs)))
    ax.set_xticklabels(configs, rotation=30, ha="right", fontsize=8)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("solved rate (validated / total)")
    ax.set_title("Solved rate within time limit")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_encoding_size(rows: list[dict], path: str | Path) -> None:
    """CNF variable and clause counts across AMO encodings (SAT runs only)."""
    plt = _plt()
    sat_rows = [r for r in rows if r.get("solver_family") == "sat"]
    encodings = sorted({str(r.get("encoding")) for r in sat_rows if r.get("encoding")})
    sizes = sorted({str(r.get("size")) for r in sat_rows if r.get("size") not in ("", None)})
    if not encodings:
        plt.close("all")
        return
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    width = 0.8 / max(len(sizes), 1)

    def _val(r, key):
        # JSONL rows keep full stats; CSV fallbacks use flat columns.
        stats = r.get("stats")
        if isinstance(stats, dict) and key in stats:
            return _as_float(stats[key], 0.0)
        flat = {"total_vars": "cnf_vars", "clauses": "cnf_clauses"}.get(key, key)
        return _as_float(r.get(flat), 0.0)

    def _agg(size, enc, key):
        vals = [_val(r, key) for r in sat_rows
                if str(r.get("size")) == size and r.get("encoding") == enc]
        return max(vals) if vals else 0.0

    for si, size in enumerate(sizes):
        xpos = [x + si * width for x in range(len(encodings))]
        ax1.bar(xpos, [_agg(size, e, "total_vars") for e in encodings],
                width=width, label=f"{size}x{size}")
        ax2.bar(xpos, [_agg(size, e, "clauses") for e in encodings],
                width=width, label=f"{size}x{size}")
    for ax, ylabel, title in (
        (ax1, "total CNF variables", "Encoding size: variables"),
        (ax2, "clauses", "Encoding size: clauses"),
    ):
        ax.set_xticks(range(len(encodings)))
        ax.set_xticklabels(encodings, rotation=20, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_memory(rows: list[dict], path: str | Path) -> None:
    """Peak RSS by solver config and board size."""
    plt = _plt()
    configs = sorted({_grouped_key(r) for r in rows})
    sizes = sorted({str(r.get("size")) for r in rows if r.get("size") not in ("", None)})
    fig, ax = plt.subplots(figsize=(max(6.0, 1.1 * len(configs)), 4.5))
    width = 0.8 / max(len(sizes), 1)
    for si, size in enumerate(sizes):
        means = []
        for cfg in configs:
            vals = [_as_float(r.get("peak_rss_mb")) for r in rows
                    if _grouped_key(r) == cfg and str(r.get("size")) == size]
            vals = [v for v in vals if v is not None]
            means.append(sum(vals) / len(vals) if vals else 0.0)
        xpos = [x + si * width for x in range(len(configs))]
        ax.bar(xpos, means, width=width, label=f"{size}x{size}")
    ax.set_xticks(range(len(configs)))
    ax.set_xticklabels(configs, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("peak RSS (MB, mean over runs)")
    ax.set_title("Peak memory by solver")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_search_effort(rows: list[dict], path: str | Path) -> None:
    """Solver-specific effort metrics — one panel per unit, never shared axes.

    Panel 1: SAT conflicts (per encoding).  Panel 2: backtracking search
    nodes (per config).  Panel 3: CP-SAT branches (per config).
    """
    plt = _plt()
    fig, (ax_sat, ax_bt, ax_cp) = plt.subplots(1, 3, figsize=(15, 4.5))

    def _stats_val(r, key):
        stats = r.get("stats")
        if isinstance(stats, dict):
            return _as_float(stats.get(key))
        return None

    # Panel 1: SAT conflicts by encoding.
    sat_rows = [r for r in rows if r.get("solver_family") == "sat"]
    encs = sorted({str(r.get("encoding")) for r in sat_rows if r.get("encoding")})
    data = [[v for r in sat_rows if r.get("encoding") == enc and _is_solved(r)
             for v in [_stats_val(r, "conflicts")] if v is not None] for enc in encs]
    if any(data):
        ax_sat.boxplot(data, tick_labels=encs)
    ax_sat.set_ylabel("SAT conflicts")
    ax_sat.set_title("SAT search effort (conflicts)")
    ax_sat.tick_params(axis="x", rotation=20)

    # Panel 2: backtracking nodes by config.
    bt_rows = [r for r in rows if r.get("solver_family") == "backtracking"]
    bt_cfgs = sorted({_grouped_key(r) for r in bt_rows})
    data = [[v for r in bt_rows if _grouped_key(r) == cfg and _is_solved(r)
             for v in [_stats_val(r, "nodes")] if v is not None] for cfg in bt_cfgs]
    if any(data):
        ax_bt.boxplot(data, tick_labels=bt_cfgs)
    ax_bt.set_ylabel("search nodes")
    ax_bt.set_title("Backtracking search effort (nodes)")
    ax_bt.tick_params(axis="x", rotation=20)

    # Panel 3: CP-SAT branches by config.
    cp_rows = [r for r in rows if r.get("solver_family") == "cpsat"]
    cp_cfgs = sorted({_grouped_key(r) for r in cp_rows})
    data = [[v for r in cp_rows if _grouped_key(r) == cfg and _is_solved(r)
             for v in [_stats_val(r, "branches")] if v is not None] for cfg in cp_cfgs]
    if any(data):
        ax_cp.boxplot(data, tick_labels=cp_cfgs)
    ax_cp.set_ylabel("branches")
    ax_cp.set_title("CP-SAT search effort (branches)")
    ax_cp.tick_params(axis="x", rotation=20)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def generate_all_plots(
    results_dir: str | Path,
    out_dir: str | Path | None = None,
    **filters,
) -> list[str]:
    """Produce every required figure from saved results (no solver runs).

    ``filters`` are passed to :func:`filter_rows` (size, difficulty, solver,
    encoding, backend).  Returns the list of files written.
    """
    rows = filter_rows(load_rows(results_dir), **filters)
    if not rows:
        raise ValueError(f"no rows match filters {filters} in {results_dir}")
    out = Path(out_dir or results_dir) / "figures"
    out.mkdir(parents=True, exist_ok=True)
    targets = {
        "runtime.png": plot_runtime,
        "cactus.png": plot_cactus,
        "solved_rate.png": plot_solved_rate,
        "encoding_size.png": plot_encoding_size,
        "memory.png": plot_memory,
        "search_effort.png": plot_search_effort,
    }
    written = []
    for name, fn in targets.items():
        try:
            fn(rows, out / name)
            written.append(str(out / name))
        except Exception as exc:
            print(f"plot {name} failed: {exc}", flush=True)
    return written


# --- entry points ----------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI: ``--single PUZZLE CONFIG_JSON`` runs one worker; otherwise run a
    full benchmark with ``--config PATH`` (default: configs/benchmark.toml)."""
    import argparse

    parser = argparse.ArgumentParser(prog="sudoku_solver.benchmark")
    parser.add_argument("--single", nargs=2, metavar=("PUZZLE", "CONFIG_JSON"))
    parser.add_argument("--config", default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if args.single:
        puzzle_path, config_json = args.single
        row = _single_run(puzzle_path, json.loads(config_json))
        print(json.dumps(row, default=str))
        return 0

    config_path = args.config or "configs/benchmark.toml"
    config = load_config(config_path)
    summary = run_benchmark(config, quiet=args.quiet)
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



