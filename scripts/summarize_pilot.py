#!/usr/bin/env python3
"""Create pilot v2 status and continuation tables; does not launch solver runs."""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "data" / "results"
EXPECTED_PILOT_RUNS_PER_CELL = 3
SELECTION_INDICES = range(0, 20)
EVALUATION_INDICES = range(20, 100)


def _config_label(run: dict[str, Any]) -> str:
    if run["solver"] == "sat":
        extra_tag = "_extra_backend" if run["backend"] == "minisat22" else ""
        return f"sat_{run['encoding']}_{run['backend']}{extra_tag}"
    return run["solver"]


def _read_runs(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing pilot results: {path}")
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON in {path}:{line_number}: {exc}") from exc
    return records


def _decision(runs: list[dict[str, Any]]) -> tuple[str, str]:
    statuses = [run.get("status", "MISSING_STATUS") for run in runs]
    resource_guard_count = sum(
        run.get("status") == "BUILD_FAIL"
        and run.get("stats", {}).get("reason") == "RESOURCE_GUARD"
        for run in runs
    )
    if resource_guard_count == len(runs) == EXPECTED_PILOT_RUNS_PER_CELL:
        return "EXCLUDE_BUILD_INFEASIBLE", "all pilot runs rejected by RESOURCE_GUARD"
    if resource_guard_count:
        return "REVIEW_REQUIRED", f"mixed RESOURCE_GUARD outcomes ({resource_guard_count}/{len(runs)})"
    if len(runs) == EXPECTED_PILOT_RUNS_PER_CELL and all(s == "BLOCKED_LICENSE" for s in statuses):
        return "ENVIRONMENT_BLOCKER_LICENSE", "all pilot runs blocked by license"
    if any(s == "BLOCKED_LICENSE" for s in statuses):
        return "REVIEW_REQUIRED", "mixed license and non-license outcomes"
    if len(runs) == EXPECTED_PILOT_RUNS_PER_CELL and all(s == "TIMEOUT" for s in statuses):
        return "REDUCE_TO_FIRST_30", "every pilot run timed out"
    if any(s == "SOLVED_VALID" for s in statuses):
        return "CONTINUE_ALL_100", "at least one pilot run solved and validated"
    return "REVIEW_REQUIRED", f"no predeclared continuation rule matched: {dict(Counter(statuses))}"


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 6) if values else None


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    runs = _read_runs(RESULTS_DIR / "pilot_v2.jsonl")
    timeout_s = float(runs[0]["timeout_s"])
    groups: dict[tuple[str, int, float], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        groups[(_config_label(run), int(run["N"]), float(run["requested_ratio"]))].append(run)

    summary_rows: list[dict[str, Any]] = []
    continuation_rows: list[dict[str, Any]] = []
    decisions: dict[tuple[str, int, float], str] = {}
    medians_total: dict[tuple[str, int, float], float | None] = {}

    for key in sorted(groups):
        config, n, ratio = key
        cell_runs = groups[key]
        status_counts = Counter(run["status"] for run in cell_runs)
        build_fail_reasons = Counter(
            run.get("stats", {}).get("reason", "UNSPECIFIED")
            for run in cell_runs
            if run.get("status") == "BUILD_FAIL"
        )
        solve_median = _median([
            float(run["t_solve"]) for run in cell_runs
            if run.get("status") == "SOLVED_VALID" and run.get("t_solve") is not None
        ])
        peak_median = _median([
            float(run["peak_rss_mb"]) for run in cell_runs
            if run.get("peak_rss_mb") is not None
        ])
        total_median = _median([
            float(run["t_total"]) for run in cell_runs
            if run.get("t_total") is not None
        ])
        decision, reason = _decision(cell_runs)
        decisions[key] = decision
        medians_total[key] = total_median
        summary_rows.append({
            "config": config,
            "N": n,
            "ratio": ratio,
            "n": len(cell_runs),
            "solved": status_counts["SOLVED_VALID"],
            "timeout": status_counts["TIMEOUT"],
            "build_fail": sum(build_fail_reasons.values()),
            "build_fail_by_reason": json.dumps(dict(build_fail_reasons), sort_keys=True),
            "blocked": status_counts["BLOCKED_LICENSE"],
            "invalid": status_counts["INVALID_SOLUTION"],
            "unsat": status_counts["UNSAT_INVESTIGATE"],
            "median_solve_time_s_solved": solve_median,
            "median_peak_rss_mb": peak_median,
            "median_total_time_s": total_median,
            "other_statuses": json.dumps({
                status: count for status, count in status_counts.items()
                if status not in {
                    "SOLVED_VALID", "TIMEOUT", "BUILD_FAIL", "BLOCKED_LICENSE",
                    "INVALID_SOLUTION", "UNSAT_INVESTIGATE",
                }
            }, sort_keys=True),
        })
        continuation_rows.append({
            "config": config,
            "N": n,
            "ratio": ratio,
            "pilot_n": len(cell_runs),
            "pilot_statuses": json.dumps(dict(status_counts), sort_keys=True),
            "decision": decision,
            "decision_reason": reason,
        })

    _write_csv(
        RESULTS_DIR / "pilot_v2_summary.csv",
        summary_rows,
        [
            "config", "N", "ratio", "n", "solved", "timeout", "build_fail",
            "build_fail_by_reason", "blocked", "invalid", "unsat",
            "median_solve_time_s_solved", "median_peak_rss_mb",
            "median_total_time_s", "other_statuses",
        ],
    )
    _write_csv(
        RESULTS_DIR / "pilot_v2_continuation.csv",
        continuation_rows,
        ["config", "N", "ratio", "pilot_n", "pilot_statuses", "decision", "decision_reason"],
    )

    matrix_rows: list[dict[str, Any]] = []
    for key in sorted(groups):
        config, n, ratio = key
        decision = decisions[key]
        if decision == "CONTINUE_ALL_100":
            count, indices = 100, "0-99"
        elif decision == "REDUCE_TO_FIRST_30":
            count, indices = 30, "0-29"
        elif decision == "REVIEW_REQUIRED":
            count, indices = None, "pending"
        else:
            count, indices = 0, "none"
        cell_runs = groups[key]
        total_median = medians_total[key]
        matrix_rows.append({
            "config": config,
            "N": n,
            "ratio": ratio,
            "decision": decision,
            "instance_indices": indices,
            "selection_run_count_indices_0_19": (
                min(count, len(SELECTION_INDICES)) if count is not None else None
            ),
            "evaluation_run_count_indices_20_99": (
                max(0, min(count - 20, len(EVALUATION_INDICES))) if count is not None else None
            ),
            "planned_run_count": count,
            "pilot_median_total_s": total_median,
            "expected_wall_s": (
                round(count * total_median, 3)
                if count is not None and total_median is not None
                else None
            ),
            "worst_case_wall_s_at_timeout": (
                round(count * timeout_s, 3) if count is not None else None
            ),
            "pilot_cell_n": len(cell_runs),
            "note": (
                "Evaluation rows are not used for configuration selection."
                if count else next(
                    row["decision_reason"] for row in continuation_rows
                    if (row["config"], row["N"], row["ratio"]) == key
                )
            ),
        })

    _write_csv(
        RESULTS_DIR / "pilot_v2_full_matrix.csv",
        matrix_rows,
        [
            "config", "N", "ratio", "decision", "instance_indices",
            "selection_run_count_indices_0_19", "evaluation_run_count_indices_20_99",
            "planned_run_count", "pilot_median_total_s", "expected_wall_s",
            "worst_case_wall_s_at_timeout", "pilot_cell_n", "note",
        ],
    )

    stop_statuses = [run for run in runs if run.get("status") in {"UNSAT_INVESTIGATE", "INVALID_SOLUTION"}]
    total_run_count = sum(
        int(row["planned_run_count"])
        for row in matrix_rows
        if row["planned_run_count"] is not None
    )
    expected_seconds = sum(float(row["expected_wall_s"] or 0) for row in matrix_rows)
    worst_seconds = sum(float(row["worst_case_wall_s_at_timeout"] or 0) for row in matrix_rows)
    print(f"Pilot rows: {len(runs)}; cells summarized: {len(summary_rows)}")
    print(f"UNSAT/INVALID rows: {len(stop_statuses)}")
    print(f"Proposed all-config matrix: {total_run_count} runs")
    print(f"Expected wall time from pilot median t_total: {expected_seconds / 3600:.2f} h")
    print(f"Worst-case wall time at timeout_s={timeout_s:g}: {worst_seconds / 3600:.2f} h")
    print(f"Created {RESULTS_DIR / 'pilot_v2_summary.csv'}")
    print(f"Created {RESULTS_DIR / 'pilot_v2_continuation.csv'}")
    print(f"Created {RESULTS_DIR / 'pilot_v2_full_matrix.csv'}")
    return 1 if stop_statuses else 0


if __name__ == "__main__":
    raise SystemExit(main())
