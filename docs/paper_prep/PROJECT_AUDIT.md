# Project Audit: Sudoku-SAT Benchmark Repository

## Repository Structure

Root: `/home/guts/P2/SAT/Sudoku-SAT`

| Path | Type | Purpose |
|------|------|---------|
| `pyproject.toml` | Config | Project metadata: name="sudoku-solver", version="0.1.0", Python >=3.11 |
| `configs/` | Directory | Configuration files |
| `data/` | Directory | Dataset, puzzles, results, archives |
| `docs/` | Directory | Documentation, results tables, benchmark plan |
| `scripts/` | Directory | Scripts |
| `src/` | Directory | Source code (package: `sudoku_solver`) |
| `tests/` | Directory | Test suite |
| `README.md` | File | Project README |

## Source Code Files

### Core modules (`src/sudoku/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `validator.py` | Sudoku grid/puzzle/solution validation (O(N²)) |
| `generator.py` | Deterministic seeded puzzle generation (gen-v1) |
| `dataset.py` | Dataset persistence, manifest management, puzzle loading |
| `bench/runner.py` | Benchmark runner: subprocess isolation, RSS tracking, timeout enforcement |
| `bench/__init__.py` | Bench package init |

### Solver adapters (`src/sudoku/solvers/`)

| File | Solver Family | Status |
|------|--------------|--------|
| `base.py` | Status vocabulary and `SolverResult` dataclass | Core |
| `sat.py` | SAT via PySAT (5 AMO encodings, multiple backends) | Implemented |
| `cpsat.py` | OR-Tools CP-SAT | Implemented |
| `gurobi.py` | Gurobi MIP | Implemented (license-gated) |
| `cplex_cp.py` | CPLEX CP Optimizer | Implemented (license-gated) |
| `cplex_mip.py` | CPLEX MIP | Implemented (license-gated) |

## SAT Encoding Details (`src/sudoku/solvers/sat.py`)

Five At-Most-One (AMO) encodings implemented:

| Encoding | Aux Vars per Group | Clauses per Group | Description |
|----------|-------------------|-------------------|-------------|
| pairwise | 0 | N(N-1)/2 | All pairs (-a,-b), O(N²) clauses |
| sequential | N-1 | max(0, 3N-4) | Sinz (2005) sequential counter |
| binary | ceil(log2(N)) | N*ceil(log2(N)) | Bitwise indicator (Frisch et al.) |
| commander | ceil(N/b) | N + sum(size*(size-1)/2) + commanders*(commanders-1)/2 | Klieber & Kwon (2007), default b=4 |
| product | ceil(sqrt(N)) + ceil(N/rows) | 2N + rows*(rows-1)/2 + cols*(cols-1)/2 | Chen (2010) 2D grid |

SAT model: N³ primary one-hot Boolean variables x[r,c,v], 4N² exactly-one groups (cell, row-value, col-value, box-value), clue unit clauses.

SAT backends available via PySAT: CaDiCaL 1.5.3, Glucose 4, MiniSat 2.2 (from `generate_paper_tables.py` configs).

## CP-SAT Implementation (`src/sudoku/solvers/cpsat.py`)

OR-Tools CP-SAT model:
- N² integer decision variables x[r,c] in domain 1..N
- AllDifferent constraints per row, column, box
- Clue constraints as unit equalities
- Solver parameters: max_time_in_seconds, num_workers

## Result Statuses (`src/sudoku/solvers/base.py`)

| Status | Meaning |
|--------|---------|
| SOLVED_VALID | Valid solution found and independently verified |
| TIMEOUT | Wall-clock timeout expired |
| UNSAT_INVESTIGATE | Solver reported UNSAT on SAT-generated puzzle |
| INVALID_SOLUTION | Solution returned but failed validation |
| BUILD_FAIL | Model construction failed |
| SOLVER_ERROR | Solver crashed or returned unexpected status |
| BLOCKED_LICENSE | Commercial solver license limit exceeded |
| RESOURCE_GUARD_LIVE | Live resource guard rejection |

## Benchmark Runner (`src/sudoku/bench/runner.py`)

Key parameters:
- Timeout: 10.0 seconds wall-clock
- Resource guard fraction: 0.60 (60% of available RAM)
- RSS sampling interval: 20 ms
- Subprocess isolation for each run
- Hard timeout via SIGKILL
- Independent validation via `is_valid_solution_for_puzzle`

## Data Files

| Path | Description |
|------|-------------|
| `data/manifest.csv` | 120 puzzle manifest entries |
| `data/dataset_info.json` | Dataset metadata (seed=42, 20 puzzles per pair, sizes [9,36,81], ratios [0.5,0.9]) |
| `data/puzzles/N009_r0.5.jsonl` | 20 puzzles, N=9, r=0.5 |
| `data/puzzles/N009_r0.9.jsonl` | 20 puzzles, N=9, r=0.9 |
| `data/puzzles/N036_r0.5.jsonl` | 20 puzzles, N=36, r=0.5 |
| `data/puzzles/N036_r0.9.jsonl` | 20 puzzles, N=36, r=0.9 |
| `data/puzzles/N081_r0.5.jsonl` | 20 puzzles, N=81, r=0.5 |
| `data/puzzles/N081_r0.9.jsonl` | 20 puzzles, N=81, r=0.9 |
| `data/results/benchmark_sat_vs_nonsat.csv` | Primary benchmark results: 960 data rows |
| `data/results/full_v1.csv` | Preliminary run: 62 recorded + 4 predeclared excluded |
| `data/results/full_v1.jsonl` | Preliminary run JSONL |
| `data/results/full_v1_run_info.json` | Run metadata |
| `data/results/full_v1_stop.json` | Stop reason: solver_error_rate_stage |

## Configs

| Path | Description |
|------|-------------|
| `configs/full_matrix_v1.csv` | Benchmark matrix definition (referenced in run info) |

## Existing Documentation

| Path | Description |
|------|-------------|
| `docs/sudoku_benchmark_plan.md` | Detailed benchmark plan (Vietnamese) |
| `docs/SETUP.md` | Dataset construction and correctness criteria |
| `docs/results/benchmark_report.md` | Generated benchmark report |
| `docs/results/table1_sat_vs_nonsat_primary.csv` | Generated Table 1 |
| `docs/results/table2_per_solver_breakdown.csv` | Generated Table 2 |
| `docs/results/table3_difficulty_stratification.csv` | Generated Table 3 |

## Archives (stale/older data)

| Path | Description |
|------|-------------|
| `data/archive_before_120/` | Pre-120 dataset archive |
| `data/archive_k1_scoped/` | K1-scoped archive |
| `data/archive_v1/` | Archive v1 with manifest |
| `data/archive_v2_pair50/` | Archive v2 pair50 with manifest |
| `data/historical_archive/` | Historical archive |
| `data/results_smoke/` | Smoke test results |

## Tooling

| Path | Description |
|------|-------------|
| `scripts/generate_paper_tables.py` | Table generation script (already executed) |
| `tests/` | Test directory (not inspected in detail) |
