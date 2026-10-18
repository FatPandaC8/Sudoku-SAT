# Experimental Protocol Reconstruction

## Source of Truth

- `src/sudoku/bench/runner.py` — Benchmark runner implementation
- `src/sudoku/solvers/base.py` — Status vocabulary and SolverResult schema
- `src/sudoku/solvers/sat.py` — SAT solver adapter and CNF builder
- `src/sudoku/solvers/cpsat.py` — OR-Tools CP-SAT adapter
- `src/sudoku/solvers/gurobi.py` — Gurobi MIP adapter
- `src/sudoku/solvers/cplex_cp.py` — CPLEX CP adapter
- `src/sudoku/solvers/cplex_mip.py` — CPLEX MIP adapter
- `data/results/benchmark_sat_vs_nonsat.csv` — Primary benchmark results (960 runs)
- `data/results/full_v1_run_info.json` — Preliminary run metadata
- `data/results/full_v1_stop.json` — Early-stop metadata

## Puzzle Loading

Puzzles loaded exclusively from `data/manifest.csv` and `data/puzzles/*.jsonl` via `src/sudoku/dataset.py`. All solvers read the same stored dataset; no puzzle regeneration occurs during benchmarking.

## Solver Configurations Evaluated

| Label | Family | Encoding | Backend | Threads | Timeout |
|-------|--------|----------|---------|---------|---------|
| sat_pairwise_cadical153 | SAT | pairwise | cadical153 | 1 | 10.0 s |
| sat_sequential_cadical153 | SAT | sequential | cadical153 | 1 | 10.0 s |
| sat_binary_cadical153 | SAT | binary | cadical153 | 1 | 10.0 s |
| sat_commander_cadical153 | SAT | commander | cadical153 | 1 | 10.0 s |
| sat_product_cadical153 | SAT | product | cadical153 | 1 | 10.0 s |
| sat_sequential_glucose4 | SAT | sequential | glucose4 | 1 | 10.0 s |
| sat_sequential_minisat22_extra_backend | SAT | sequential | minisat22 | 1 | 10.0 s |
| cpsat | CP-SAT | N/A | ortools-cpsat | 1 | 10.0 s |

Note: 8 solver configurations total (7 SAT + 1 CP-SAT). Gurobi, CPLEX CP, CPLEX MIP, and backtracking were NOT included in the primary results (see exclusions below).

## Timeout Policy

- Wall-clock timeout: 10.0 seconds per run
- Enforcement: subprocess isolation + SIGKILL via `monitor_process()`
- Timeout status: `TIMEOUT`
- t_total for timed-out runs: measured elapsed wall-clock time (~10.0s+)

## Resource Guard Policy

- Guard fraction: 0.60 (60% of available RAM)
- Applied before execution: estimated CNF build memory vs available RAM
- Status when triggered: `BUILD_FAIL` with `stats.predeclared_exclusion: true`
- Not counted as an attempted run
- Affects N=81 SAT pairwise and binary encodings only

## Execution Model

- Each run executed in an isolated subprocess (`subprocess.Popen`, `start_new_session=True`)
- PYTHONPATH set to repository `src/` directory
- Peak RSS tracked via both `psutil` sampling (20 ms interval) and `resource.ru_maxrss`
- Baseline RSS measured before solver invocation
- Independent solution validation via `is_valid_solution_for_puzzle()` (`src/sudoku/validator.py`)
- A run counts as SOLVED_VALID only if solution passes independent validation

## Status-to-Outcome Mapping

| Raw Status | Outcome Category | Counted as Attempted? | Included in Valid Rate Denominator? |
|------------|-----------------|----------------------|--------------------------------------|
| SOLVED_VALID | Valid solution | Yes | Yes (numerator) |
| TIMEOUT | Timeout | Yes | Yes (denominator only) |
| BUILD_FAIL (predeclared_exclusion=true) | Predeclared exclusion | No | No |
| BUILD_FAIL (other) | Build failure | Yes | Yes (denominator only) |
| SOLVER_ERROR | Solver error | Yes | Yes (denominator only) |
| INVALID_SOLUTION | Invalid solution | Yes | Yes (denominator only) |
| RESOURCE_GUARD_LIVE | Live resource guard rejection | Yes | Yes (denominator only) |
| UNSAT_INVESTIGATE | UNSAT on SAT puzzle | Yes | Yes (denominator only) |

## Solve Rate Definition

Valid Solve Rate = Valid Solutions / Attempted Runs

Where:
- Valid Solutions = count of status == SOLVED_VALID
- Attempted Runs = Recorded Runs − Predeclared Exclusions (BUILD_FAIL with predeclared_exclusion=true)

## Time Metrics

| Metric | Definition | Source |
|--------|-----------|--------|
| t_build | CNF/model construction time | Solver adapter (time.perf_counter) |
| t_solve | Pure solver solve time | Solver adapter (time.perf_counter) |
| t_total | End-to-end total (build + solve + extract + validate) | Child process measurement |
| t_total (timeout) | Wall-clock elapsed until SIGKILL | Runner measurement |

For SAT solvers, t_total is the primary reported timing metric. Build time is tracked separately.

## Encoding Complexity Tracking (SAT only)

Recorded per run in `stats` field:
- primary_vars: N³
- aux_vars: AMO auxiliary variable count (encoding-dependent)
- total_vars: primary + aux
- clauses: ALO + AMO + clue unit clauses
- clues: number of clue unit clauses
- conflicts, decisions, propagations: PySAT backend stats (when available)

## CP-SAT Statistics Recorded

- cpsat_status: OR-Tools status name (OPTIMAL, FEASIBLE, UNKNOWN, etc.)
- branches: number of search branches
- conflicts: number of conflicts
- wall_time, user_time: solver-reported times
- num_workers: number of worker threads
- clues: number of clue constraints

## Excluded Solvers

| Solver | Reason for Exclusion | Evidence |
|--------|---------------------|----------|
| Gurobi MIP | License restriction / not available in environment | `gurobi.py` adapter exists but no Gurobi results in benchmark CSV |
| CPLEX CP | License restriction / not available | `cplex_cp.py` adapter exists but no results in benchmark CSV |
| CPLEX MIP | License restriction / not available | `cplex_mip.py` adapter exists but no results in benchmark CSV |
| Backtracking | Implementation error (TypeError: 'int' object is not iterable) | `full_v1.jsonl` shows 10 backtracking runs all with SOLVER_ERROR due to Board initialization failure |

## Preliminary Run (full_v1)

| Attribute | Value | Source |
|-----------|-------|--------|
| Suite name | primary | `full_v1_run_info.json` |
| Start time | 2026-10-18T06:41:07Z | `full_v1_run_info.json` |
| Planned cells | 66 | `full_v1_run_info.json` |
| Recorded cells | 62 | `full_v1_run_info.json` |
| Predeclared exclusions | 4 | `full_v1_run_info.json` |
| Puzzles per pair | 20 | `full_v1_run_info.json` |
| Ratios | [0.5, 0.9] | `full_v1_run_info.json` |
| Sizes | [9, 36, 81] | `full_v1_run_info.json` |
| Timeout | 10.0 s | `full_v1_run_info.json` |
| Sample rule | 1 deterministic puzzle per pair | `full_v1_run_info.json` |
| Stop reason | solver_error_rate_stage (1/10 > 2% at N=9) | `full_v1_stop.json` |
| Status | planned | `full_v1_run_info.json` |

The preliminary run was stopped early due to solver error rate exceeding threshold. It is NOT the primary results source.

## Primary Results Source

- `data/results/benchmark_sat_vs_nonsat.csv`: 960 data rows (120 puzzles × 8 solver configurations)
- All 6 strata represented
- All 8 solver configurations represented
- 10-second timeout applied uniformly

## Environment Information (partially available)

- Python version: 3.14.8 (from dataset_info.json)
- RSS sampling interval: 20 ms
- Resource guard fraction: 0.60
- Hardware specifics: NOT recorded (no environment lock file present per full_v1_run_info.json: "environment_lock_present": false)

## Confidence in Protocol Reconstruction

High confidence for: timeout policy, resource guard policy, status mapping, solve rate definition, solver configurations, exclusion rules.

Moderate confidence for: exact hardware/software environment (no environment lock), precise build-time vs solve-time attribution for CP-SAT.

Low confidence for: any undocumented preprocessing steps, solver parameter defaults beyond those visible in code.
