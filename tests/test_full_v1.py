"""Tests for the full_v1 primary benchmark runner: resume and budget stop.

execute_run_subprocess is monkeypatched with a fast fake solver so these tests
exercise the runner's ordering, dedup/resume, and stop logic without spawning
real solver subprocesses for every cell.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

from sudoku.bench.runner import BenchmarkConfig, execute_run_subprocess  # noqa: E402
import sudoku.bench.runner as _runner_module  # noqa: E402
from sudoku.dataset import load_puzzles  # noqa: E402
from sudoku.solvers.base import STATUS_SOLVED_VALID  # noqa: E402
from sudoku.solvers.sat import solve_sat  # noqa: E402
from sudoku.validator import is_valid_solution_for_puzzle  # noqa: E402


def _load_runner_module():
    spec = importlib.util.spec_from_file_location(
        "run_full_v1_test", REPO_ROOT / "scripts" / "run_full_v1.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ALL_CONFIGS = [
    "sat_pairwise_cadical153",
    "sat_sequential_cadical153",
    "sat_binary_cadical153",
    "sat_commander_cadical153",
    "sat_product_cadical153",
    "sat_sequential_glucose4",
    "sat_sequential_minisat22_extra_backend",
    "cpsat",
    "gurobi",
    "cplex_mip",
    "cplex_cp",
]


def _puzzles_per_pair():
    import yaml

    with open(REPO_ROOT / "configs" / "dataset.yaml", "r", encoding="utf-8") as f:
        return int(yaml.safe_load(f).get("puzzles_per_pair", 20))


SIZES = (9, 36, 81)
RATIOS = (0.5, 0.9)


def _fake_execute(puzzle_rec, cfg, memory_bytes_per_clause=None):
    """Instant fake solver: returns the reference solution as SOLVED_VALID."""
    return {
        "run_key": f"{puzzle_rec['id']}___{cfg.label}",
        "puzzle_id": puzzle_rec["id"],
        "N": puzzle_rec["N"],
        "requested_ratio": puzzle_rec["requested_ratio"],
        "status": "SOLVED_VALID",
        "t_build": 0.001,
        "t_solve": 0.002,
        "t_total": 0.003,
        "peak_rss_mb": 50.0,
        "solution": list(puzzle_rec["solution"]),
        "stats": {},
        "error": None,
        "phase_at_kill": None,
    }


@pytest.fixture
def runner_module(tmp_path, monkeypatch):
    mod = _load_runner_module()
    jsonl = tmp_path / "full_v1.jsonl"
    csv_path = tmp_path / "full_v1.csv"
    monkeypatch.setattr(mod, "JSONL_PATH", jsonl)
    monkeypatch.setattr(mod, "CSV_PATH", csv_path)
    monkeypatch.setattr(mod, "STOP_PATH", tmp_path / "full_v1_stop.json")
    monkeypatch.setattr(mod, "execute_run_subprocess", _fake_execute)
    return mod, jsonl, csv_path


def test_matrix_shape_and_scope():
    mod = _load_runner_module()
    matrix = mod.load_matrix()
    assert len(matrix) == 66
    included = [r for r in matrix if r["decision"] == "INCLUDE"]
    excluded = [r for r in matrix if r["decision"] != "INCLUDE"]
    assert len(included) == 62
    assert len(excluded) == 4
    ppp = _puzzles_per_pair()
    assert {(r["config"], int(r["N"])) for r in excluded} == {
        ("sat_pairwise_cadical153", 81),
        ("sat_binary_cadical153", 81),
    }
    assert all(int(r["expected_runs"]) == ppp for r in matrix)
    assert all(r["indices"] == f"0-{ppp - 1}" for r in matrix)
    assert mod.totals()["recorded_runs"] == len(matrix) * ppp
    assert mod.totals()["executed_runs"] == len(included) * ppp


def test_shuffle_seed_is_deterministic():
    mod = _load_runner_module()
    s1 = mod.shuffle_seed("sudoku_N009_r0.5_i000")
    s2 = mod.shuffle_seed("sudoku_N009_r0.5_i000")
    assert s1 == s2
    assert s1 != mod.shuffle_seed("sudoku_N009_r0.5_i001")
    import random
    order_a = random.Random(s1).sample(ALL_CONFIGS, len(ALL_CONFIGS))
    order_b = random.Random(s1).sample(ALL_CONFIGS, len(ALL_CONFIGS))
    assert order_a == order_b


def test_resume_writes_clean_prefix_no_duplicates_or_gaps(runner_module):
    mod, jsonl, _csv = runner_module
    totals = mod.totals()
    ppp = _puzzles_per_pair()
    spp = totals["sample_per_pair"]
    matrix = mod.load_matrix()

    summary1 = mod.run_suite(max_wall_hours=100.0)
    assert summary1["completed_cleanly"] is True
    assert summary1["records_written"] == totals["sampled_recorded_runs"]
    # Every inclusion attempt is either executed or live-guard rejected; nothing is dropped.
    assert summary1["executed_runs"] + summary1["live_guard_rejections"] == totals["sampled_executed_runs"]
    assert summary1["predeclared_excluded_records"] == totals["sampled_predeclared_records"]

    records = [json.loads(line) for line in jsonl.read_text().splitlines() if line.strip()]
    assert len(records) == totals["sampled_recorded_runs"]
    keys = [r["run_key"] for r in records]
    assert len(keys) == len(set(keys)), "duplicate run keys after first run"

    # Positions are a clean sequential prefix.
    assert [r["run_order_position"] for r in records] == list(range(totals["sampled_recorded_runs"]))

    # Exclusions (pairwise/binary at N=81) are recorded first, not executed.
    exclusions = records[: totals["sampled_predeclared_records"]]
    assert all(r["status"] == "BUILD_FAIL" for r in exclusions)
    assert all(r["N"] == 81 for r in exclusions)

    # Stages run N=9, then N=36, then N=81; sampled index order within stage.
    stage_records = records[totals["sampled_predeclared_records"]:]
    sizes = [r["N"] for r in stage_records]
    per_stage = {
        int(N): sum(1 for r in matrix if int(r["N"]) == int(N) and r["decision"] == "INCLUDE") * spp
        for N in SIZES
    }
    assert sizes == [9] * per_stage[9] + [36] * per_stage[36] + [81] * per_stage[81]

    # Same sampled index is used by every configuration within a (N, ratio) pair.
    n9 = [r for r in stage_records if r["N"] == 9]
    assert len(n9) == per_stage[9]
    idx_seq = [int(r["puzzle_id"].rsplit("_i", 1)[1]) for r in n9]
    ratio_seq = [r["requested_ratio"] for r in n9]
    n_cfg_9 = len({r["config"] for r in matrix if int(r["N"]) == 9 and r["decision"] == "INCLUDE"})
    sampled_9 = {r: mod.sampled_indices(9, r) for r in RATIOS}
    expected_idx = [idx for r in RATIOS for idx in sampled_9[r] for _ in range(n_cfg_9)]
    expected_ratio = [r for r in RATIOS for _ in sampled_9[r] for _ in range(n_cfg_9)]
    assert idx_seq == expected_idx, "stage N=9 is not in sampled index order"
    assert ratio_seq == expected_ratio, "stage N=9 ratio order mismatch"

    n9_configs = {row["config"] for row in mod.load_matrix()
                  if int(row["N"]) == 9 and row["decision"] == "INCLUDE"}

    def record_label(r: dict[str, Any]) -> str:
        if r["solver"] == "sat":
            label = f"{r['solver']}_{r['encoding']}_{r['backend']}"
            if r["backend"] == "minisat22":
                label += "_extra_backend"
            return label
        return r["solver"]

    for ratio in RATIOS:
        for idx in sampled_9[ratio]:
            group = {record_label(r) for r in n9
                     if int(r["puzzle_id"].rsplit("_i", 1)[1]) == idx
                     and r["requested_ratio"] == ratio}
            assert group == n9_configs, f"config set mismatch at N=9 index={idx} ratio={ratio}"

    # Resume: second run skips every existing key, no new records, no gaps.
    summary2 = mod.run_suite(max_wall_hours=100.0)
    records2 = [json.loads(line) for line in jsonl.read_text().splitlines() if line.strip()]
    assert len(records2) == totals["sampled_recorded_runs"]
    assert summary2["records_written"] == 0
    assert summary2["executed_runs"] == 0
    assert summary2["completed_cleanly"] is True


def test_budget_stop_stops_cleanly_and_resumes(runner_module):
    mod, jsonl, _csv = runner_module
    totals = mod.totals()
    stop_path = mod.STOP_PATH

    summary1 = mod.run_suite(max_wall_hours=0.0)
    assert summary1["stop_reason"] == "budget"
    assert summary1["executed_runs"] == 0
    records = [json.loads(line) for line in jsonl.read_text().splitlines() if line.strip()]
    # Only the predeclared exclusions were recorded; no solver runs executed.
    assert len(records) == totals["sampled_predeclared_records"]
    assert all(r["status"] == "BUILD_FAIL" for r in records)
    stop_info = json.loads(stop_path.read_text(encoding="utf-8"))
    assert stop_info["stop_reason"] == "budget"

    # Resuming with the same zero budget writes nothing new and stops again.
    before = jsonl.read_text()
    summary2 = mod.run_suite(max_wall_hours=0.0)
    assert jsonl.read_text() == before
    assert summary2["records_written"] == 0
    assert summary2["executed_runs"] == 0
    assert summary2["stop_reason"] == "budget"


class TestSolutionPayloadPreserved:
    """Regression test for the INVALID_SOLUTION failure on sudoku_N009_r0.5_i006.

    Root cause: execute_run_subprocess (src/sudoku/bench/runner.py) assembled the
    parent record from the child's JSON but omitted the ``solution`` field, so a
    solver that correctly reported SOLVED_VALID had its solution dropped and was
    reclassified as INVALID_SOLUTION ("SOLVED_VALID with no solution payload").
    The encoding, solver, model parsing, and decoding are correct (covered by
    test_phase2_solvers); only the subprocess boundary dropped the payload.

    The test monkeypatches subprocess.Popen so the child returns a real
    SOLVED_VALID result (solution computed by solve_sat for the exact failing
    puzzle) and asserts the solution survives execute_run_subprocess and
    revalidate_solved.
    """

    FAILING_PUZZLE_ID = "sudoku_N009_r0.5_i006"
    FAILING_CONFIG = BenchmarkConfig(
        solver="sat", encoding="sequential", backend="minisat22"
    )

    def _load_failing_puzzle(self) -> dict:
        puzzles = load_puzzles("data/manifest.csv", sizes=9, ratios=0.5)
        matches = [p for p in puzzles if p["id"] == self.FAILING_PUZZLE_ID]
        assert len(matches) == 1, self.FAILING_PUZZLE_ID
        return matches[0]

    def _solved_child_result(self, puzzle_rec: dict) -> dict:
        res = solve_sat(
            puzzle=puzzle_rec["puzzle"],
            N=puzzle_rec["N"],
            encoding=self.FAILING_CONFIG.encoding,
            backend=self.FAILING_CONFIG.backend,
        )
        assert res.status == STATUS_SOLVED_VALID
        assert res.solution is not None
        assert is_valid_solution_for_puzzle(
            puzzle_rec["puzzle"], res.solution, puzzle_rec["N"]
        ).ok
        return {
            "status": res.status,
            "solution": res.solution,
            "t_build": res.t_build,
            "t_solve": res.t_solve,
            "t_total": res.t_total,
            "peak_rss_mb": res.peak_rss_mb,
            "stats": res.stats,
            "error": res.error,
        }

    def test_solution_survives_subprocess_boundary_for_failing_case(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        mod = _load_runner_module()
        puzzle_rec = self._load_failing_puzzle()
        child_result = self._solved_child_result(puzzle_rec)

        class FakePopen:
            def __init__(self, *a, **k):
                self.pid = 999999
                self.returncode = 0

            def poll(self):
                return 0

            def communicate(self):
                return (json.dumps(child_result), "")

            def wait(self, timeout=None):
                return 0

        orig_popen = _runner_module.subprocess.Popen
        _runner_module.subprocess.Popen = FakePopen
        try:
            rec = execute_run_subprocess(puzzle_rec, self.FAILING_CONFIG)
        finally:
            _runner_module.subprocess.Popen = orig_popen

        assert rec["status"] == STATUS_SOLVED_VALID
        assert "solution" in rec
        assert isinstance(rec["solution"], list)
        assert rec["solution"] == child_result["solution"]

        # Independent validation must still pass once the solution is present.
        validated = mod.revalidate_solved(
            dict(rec),
            {
                "id": puzzle_rec["id"],
                "N": puzzle_rec["N"],
                "puzzle": puzzle_rec["puzzle"],
            },
        )
        assert validated["status"] == STATUS_SOLVED_VALID
        assert is_valid_solution_for_puzzle(
            puzzle_rec["puzzle"], validated["solution"], puzzle_rec["N"]
        ).ok
