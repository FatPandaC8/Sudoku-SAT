# Manuscript Evidence Audit

Claims-to-evidence mapping and unresolved discrepancies for the Sudoku SAT vs.
CP-SAT vs. classical backtracking manuscript (`paper/main.tex`).

## Source of Truth

- `data/results/benchmark_sat_vs_nonsat.csv` — primary SAT/CP-SAT results, 960 data rows
- `data/results/backtracking_results.csv` — backtracking results, 120 recorded rows
- `data/results/full_v1.jsonl` — preliminary sampled run (62 recorded + 4 predeclared; backtracking as SOLVER_ERROR)
- `data/results/full_v1_run_info.json` — preliminary run metadata
- `data/results/full_v1_stop.json` — early-stop metadata
- `data/dataset_info.json` — dataset metadata (seed 42, gen-v1, 20 per pair, sizes [9,36,81], ratios [0.5,0.9])
- `data/manifest.csv` — 120 puzzle manifest entries
- `docs/results/table1_sat_vs_nonsat_primary.csv` — generated Table 1
- `docs/results/table2_per_solver_breakdown.csv` — generated Table 2
- `docs/results/table3_difficulty_stratification.csv` — generated Table 3
- `docs/results/benchmark_report.md` — generated benchmark report
- `src/sudoku/bench/runner.py` — execution protocol (timeout, resource guard, status mapping)
- `src/sudoku/solvers/base.py` — status vocabulary and SolverResult schema
- `src/sudoku/solvers/sat.py` — SAT solver adapter, AMO encodings, CNF builder
- `src/sudoku/solvers/cpsat.py` — OR-Tools CP-SAT adapter
- `src/sudoku_solver/backtracking.py` — backtracking implementation (MRV + forward checking)
- `src/sudoku_solver/puzzle.py` — Board model, validate_solution
- `src/sudoku/validator.py` — is_valid_solution_for_puzzle (independent validator)
- `configs/full_matrix_v1.csv` — benchmark matrix definition
- `configs/selection_rule_v1.md` — SAT representative selection rule
- `tests/test_full_v1.py` — tests documenting matrix shape, resume, solution payload

## Verified Claims (traced to source)

| # | Claim | Value | Evidence Source | Strength | Caveats |
|---|-------|-------|-----------------|----------|---------|
| C1 | SAT valid solve rate | 56.71% (431/760) | Table 1, benchmark CSV, runner.py status mapping | STRONG | Denominator excludes 80 predeclared exclusions |
| C2 | CP-SAT valid solve rate | 53.33% (64/120) | Table 1, benchmark CSV | STRONG | Single CP-SAT configuration |
| C3 | Backtracking valid solve rate | 33.33% (40/120) | backtracking_results.csv (40 SOLVED_VALID, 80 TIMEOUT) | STRONG | From backtracking_results.csv; contradicted by full_v1.jsonl (see U1) |
| C4 | Total attempted runs | 1,000 (760 SAT + 120 CP-SAT + 120 backtracking) | Table 1, runner.py | STRONG | Backtracking: 120 recorded = 120 attempted (0 predeclared) |
| C5 | Total valid solutions | 535 (431 + 64 + 40) | Table 1, backtracking_results.csv | STRONG | Sum of three families |
| C6 | Zero invalid solutions | 0 across all families | Table 1, backtracking_results.csv validation_ok | STRONG | All valid solutions independently verified |
| C7 | N=9 solve rate | 100% SAT, CP-SAT, backtracking (both ratios) | Table 3, benchmark CSV, backtracking_results.csv | STRONG | 40 instances per family (20 per ratio) |
| C8 | N=36 r=0.5 hardness | SAT 9.29%, CP-SAT 20.0%, backtracking 0% | Table 3 | STRONG | 20 instances per solver per stratum |
| C9 | N=36 r=0.9 ease | SAT 98.57%, CP-SAT 100%, backtracking 0% | Table 3 | STRONG | Underconstrained regime |
| C10 | N=81 intractable at 10s | 0% valid for all families | Table 3 | STRONG | Timeout-bound conclusion only |
| C11 | SAT predeclared exclusions | 80 (pairwise 40 + binary 40 at N=81) | Table 2, runner.py resource guard, benchmark CSV | STRONG | 60% available-RAM guard |
| C12 | Live resource-guard rejection | 1 (commander at N=81 r=0.5) | Table 2, Table 3 | STRONG | Distinct from predeclared exclusions |
| C13 | Product encoding most SAT solves | 64 (ties CP-SAT) | Table 2 | MODERATE | Margin over commander (63) is 1 solve; no significance test |
| C14 | Backtracking MRV + forward checking | Confirmed in source | backtracking.py | STRONG | No LCV, no degree, AC-3 disabled |
| C15 | Python 3.14.8 | Confirmed | dataset_info.json | STRONG | Only confirmed environment detail |
| C16 | 10s timeout, SIGKILL | Confirmed | runner.py | STRONG | Subprocess isolation |
| C17 | Independent validation | is_valid_solution_for_puzzle | validator.py | STRONG | Checks complete grid + clue match; no uniqueness required |

## Accounting Reconciliation

| Check | Expected | Observed | Match? |
|-------|----------|----------|--------|
| SAT recorded cells | 7 × 120 = 840 | 840 | Yes |
| CP-SAT recorded cells | 1 × 120 = 120 | 120 | Yes |
| Backtracking recorded rows | 1 × 120 = 120 | 120 | Yes |
| Total recorded | 960 + 120 = 1,080 cells; 120 × 8 = 960 SAT/CP-SAT + 120 backtracking | 960 (SAT+CP-SAT) + 120 (backtracking) | Yes |
| SAT predeclared exclusions | 80 (pairwise 40 + binary 40) | 80 | Yes |
| SAT attempted | 840 − 80 = 760 | 760 | Yes |
| SAT timeouts + valid + guard | 328 + 431 + 1 = 760 | 760 | Yes |
| CP-SAT timeouts + valid | 56 + 64 = 120 | 120 | Yes |
| Backtracking timeouts + valid | 80 + 40 = 120 | 120 | Yes |
| Total attempted | 760 + 120 + 120 = 1,000 | 1,000 | Yes |
| Total valid | 431 + 64 + 40 = 535 | 535 | Yes |

Stratum accounting (SAT): N=9 each 140 attempted (0 predeclared); N=36 each 140 attempted (0 predeclared); N=81 each 140 recorded − 40 predeclared = 100 attempted. CP-SAT and backtracking: 20 attempted per stratum (0 predeclared).

## Unresolved Discrepancies

### U1: Backtracking results contradiction

- `data/results/backtracking_results.csv`: 120 rows, 40 SOLVED_VALID (all N=9), 80 TIMEOUT (all N=36 and N=81), validation_ok=True for solved, no invalid solutions.
- `data/results/full_v1.jsonl` (preliminary run): 6 backtracking runs recorded as SOLVER_ERROR due to `TypeError: 'int' object is not iterable` in `Board.__post_init__` (puzzle.py:64); preliminary run stopped early (`solver_error_rate_stage`, full_v1_stop.json).

Status: The manuscript reports backtracking from backtracking_results.csv (40 valid, 80 timeouts), consistent with the task-stated totals. The contradiction with full_v1.jsonl is NOT adjudicated. Authors must determine which source reflects the final backtracking benchmark before submission. Do not re-run code to resolve.

### U2: Backtracking median solve times not verified

- Exact median solve times for backtracking's 40 SOLVED_VALID runs were not computed (no code execution permitted). The manuscript uses "---" for backtracking medians in tables.
- Status: Unresolved. Either compute medians from backtracking_results.csv or omit backtracking medians entirely.

### U3: Selective memory-guard exclusion

- Only SAT pairwise and binary encodings are predeclared excluded at N=81 (40 each). Other encodings at N=81 were attempted and all timed out.
- Status: Documented, not a conflict. The selective exclusion needs explanation in the paper (Section 5.1 / 7). The guard threshold (60% RAM) was apparently calibrated such that pairwise/binary exceed it at N=81 but sequential/commander/product do not.

### U4: full_v1.jsonl is a preliminary sampled run, not the primary source

- full_v1_run_info.json: 66 planned cells, 62 recorded, 4 predeclared, sample_per_pair=1, status "planned", stopped early.
- The primary benchmark source is `benchmark_sat_vs_nonsat.csv` (960 rows).
- Status: Resolved — manuscript uses benchmark_sat_vs_nonsat.csv as primary; full_v1.jsonl cited only for the backtracking discrepancy (U1).

### U5: "Extra backend" label for minisat22

- Runner label property appends "_extra_backend" when backend == "minisat22". CSV shows `sat_sequential_minisat22_extra_backend`.
- Status: Naming artifact; does not affect results. Manuscript uses label `sat_sequential_minisat22`.

## Verification Notes

- All 535 valid solutions (431 SAT + 64 CP-SAT + 40 backtracking) passed independent validation via `is_valid_solution_for_puzzle`.
- Zero solver errors/crashes recorded in primary SAT/CP-SAT results.
- Zero UNSAT results on SAT-generated puzzles.
- Runtime statistics (medians, percentiles) use successful (SOLVED_VALID) runs only; timeouts are censored.
- Median solve times for backtracking are NOT reported (unverified).
