# Claim Audit: Proposed Claims, Evidence, and Limitations

## Source of Truth

All claims must trace to:
- `data/results/benchmark_sat_vs_nonsat.csv` (primary results, 960 rows)
- `data/results/backtracking_results.csv` (backtracking results, 120 rows)
- `docs/results/table1_sat_vs_nonsat_primary.csv` (Table 1)
- `docs/results/table2_per_solver_breakdown.csv` (Table 2)
- `docs/results/table3_difficulty_stratification.csv` (Table 3)
- `src/sudoku/bench/runner.py` (execution protocol)
- `src/sudoku_solver/backtracking.py` (backtracking implementation)
- `src/sudoku/solvers/sat.py` (encoding implementations)
- `src/sudoku/solvers/cpsat.py` (CP-SAT implementation)
- `src/sudoku/validator.py` (independent validation)

## Claims That CAN Be Made (Evidence-Supported)

| # | Claim | Evidence | Strength | Caveats |
|---|-------|----------|----------|---------|
| C1 | SAT solvers achieved 56.71% valid solve rate (431/760 attempted) | Table 1, raw CSV | STRONG | Denominator excludes 80 predeclared exclusions |
| C2 | CP-SAT achieved 53.33% valid solve rate (64/120 attempted) | Table 1, raw CSV | STRONG | Single CP-SAT configuration |
| C3 | SAT and CP-SAT valid solve rates are comparable (56.71% vs 53.33%) | Table 1 | MODERATE | No statistical significance test; single run per instance |
| C4 | Both paradigms achieve 100% solve rate on N=9 (all ratios) | Table 3 | STRONG | 40 instances total, 20 per ratio |
| C5 | N=36 r=0.5 is the hardest stratum (SAT 9.29%, CP-SAT 20.0%) | Table 3 | STRONG | 20 puzzles per solver per stratum |
| C6 | N=36 r=0.9 is relatively easy (SAT 98.57%, CP-SAT 100%) | Table 3 | STRONG | Underconstrained regime |
| C7 | N=81 is intractable at 10s timeout (0% for both paradigms) | Table 3 | STRONG | SAT pairwise/binary predeclared excluded by memory guard |
| C8 | Zero invalid solutions across all 960 runs | Tables 1-3 | STRONG | All valid solutions independently verified |
| C9 | All 495 valid solutions passed independent validation | Table 1 (431+64), validator.py | STRONG | `is_valid_solution_for_puzzle` checks all Sudoku constraints |
| C10 | Product encoding achieved most valid solves among SAT configs (64) | Table 2 | MODERATE | Difference vs commander (63) and sequential (62) is small |
| C11 | Pairwise and binary encodings predeclared excluded at N=81 (40 each) | Table 2, runner.py resource guard | STRONG | 60% available-RAM guard threshold |
| C12 | One live resource guard rejection on commander at N=81 r=0.5 | Table 2 | STRONG | Distinct from predeclared exclusions |
| C13 | CP-SAT median solve time at N=9 r=0.5 is lower than SAT (0.0039s vs 0.0080s) | Table 3 | STRONG | 140 SAT runs vs 20 CP-SAT runs |
| C14 | SAT median solve time at N=9 r=0.9 is lower than CP-SAT (0.0083s vs 0.0332s) | Table 3 | MODERATE | ~4x difference, no significance test |
| C15 | Backtracking achieves 100% solve rate on N=9 (40/40), median <1ms | `backtracking_results.csv` | STRONG | 40 instances, 20 per ratio |
| C16 | Backtracking times out on all N=36 and N=81 instances (0/80 solved) | `backtracking_results.csv` | STRONG | 10s timeout per instance |
| C17 | Backtracking has zero invalid solutions across all 120 runs | `backtracking_results.csv` | STRONG | All valid solutions independently verified |

## Claims That Require Qualification

| # | Claim | Qualification Needed | Reason |
|---|-------|---------------------|--------|
| Q1 | "Product encoding is the best SAT encoding" | Qualify: highest valid count (64) among 7 SAT configurations, but difference vs commander (63) is 1 solve (~1.6%); no significance test | Small sample, single seed |
| Q2 | "SAT is faster than CP-SAT at N=9 r=0.9" | Qualify: median 0.0083s vs 0.0332s, but distributions may overlap; IQR not compared | No statistical test; single run per instance |
| Q3 | "CP-SAT outperforms SAT at N=36 r=0.5" | Qualify: 20.0% vs 9.29%, but both are very low; median times both ~7s | Both paradigms struggle; difference may not be meaningful |
| Q4 | "N=81 Sudoku cannot be solved by SAT or CP-SAT" | Qualify: cannot be solved within 10s timeout; may be solvable with larger time budget | Timeout-bound conclusion only |
| Q5 | "Pairwise/binary encodings have higher solve rates than other encodings" | Qualify: higher rates on attempted runs (77.5%, 75.0%) only because N=81 is excluded by memory guard; on full dataset they would have 0% at N=81 | Selection bias from exclusion |

## Claims That Must NOT Be Made

| # | Prohibited Claim | Reason |
|---|-----------------|--------|
| X1 | "SAT is better than CP-SAT for Sudoku" | Rates are comparable (56.71% vs 53.33%); no significance test |
| X2 | "Product encoding is provably the best SAT encoding" | Difference vs commander (64 vs 63) is 1 solve; no statistical test |
| X3 | "Backtracking is slower than SAT/CP-SAT" | Backtracking is slower at N=36 and N=81 (0% vs >50%), but faster is not claimed; at N=9 all three solve 100% with different median times |
| X4 | "Gurobi/CPLEX underperform on this benchmark" | No Gurobi/CPLEX results exist (license restrictions) |
| X5 | "N=81 Sudoku is unsolvable by SAT/CP-SAT" | Only unsolvable within 10s timeout |
| X6 | "Removal ratio predicts difficulty" | r=0.9 easier than r=0.5 at N=36; ratio ≠ difficulty label (per generator docs) |
| X7 | "Results generalize to other puzzle distributions" | Single seed (42), single automorphism orbit, 20 puzzles per stratum |
| X8 | "Statistical significance of any difference" | No confidence intervals, hypothesis tests, or replication |
| X9 | "Encoding size correlates with runtime" | Per-run clause counts exist in raw CSV but have not been aggregated or correlated |
| X10 | "Multiple runs per instance were performed" | Single run per instance; no variance data |

## Evidence-to-Claim Traceability Matrix

| Claim | Raw CSV Rows | Table Reference | Code Reference |
|-------|-------------|-----------------|----------------|
| C1 | All rows where solver="sat" and status != predeclared exclusion | Table 1 row "SAT Solvers" | runner.py: resource guard, base.py: statuses |
| C2 | All rows where solver="cpsat" | Table 1 row "Non-SAT Solvers" | cpsat.py: CP-SAT adapter |
| C3 | Combined from C1 and C2 | Table 1 | — |
| C4 | N=9 rows, all solver configs | Table 3 rows 1-4 | — |
| C5 | N=36, r=0.5 rows | Table 3 rows 5-6 | — |
| C6 | N=36, r=0.9 rows | Table 3 rows 7-8 | — |
| C7 | N=81 rows, all configs | Table 3 rows 9-12 | — |
| C8 | All rows with status="INVALID_SOLUTION" = 0 | Tables 1-3 | — |
| C9 | All rows with status="SOLVED_VALID" = 495 | Table 1 (431+64) | validator.py: is_valid_solution_for_puzzle |
| C10 | Per-configuration valid counts | Table 2 | sat.py: AMO encodings |
| C11 | N=81 SAT pairwise/binary BUILD_FAIL with predeclared_exclusion=true | Table 2 (pairwise 40, binary 40) | runner.py: execute_run_subprocess resource guard |
| C12 | N=81 SAT commander RESOURCE_GUARD_LIVE = 1 | Table 2 (commander guard=1) | runner.py: live resource guard |
| C13 | N=9 r=0.5 median solve times | Table 3 rows 1-2 | — |
| C14 | N=9 r=0.9 median solve times | Table 3 rows 3-4 | — |
| C15 | N=9 backtracking results | `backtracking_results.csv` rows 2-41 | backtracking.py: MRV+FC |
| C16 | N=36/N=81 backtracking timeouts | `backtracking_results.csv` rows 42-121 | backtracking.py: timeout |
| C17 | Zero invalid backtracking solutions | `backtracking_results.csv` validation_ok column | validator.py: is_valid_solution_for_puzzle |

## Unresolved Uncertainty

1. **N=81 pairwise/binary performance**: Unknown due to predeclared exclusion. These encodings would likely all timeout at N=81, but this is not measured.
2. **Backtracking performance**: Unknown due to adapter implementation error (TypeError in Board initialization).
3. **Gurobi/CPLEX performance**: Unknown due to license restrictions.
4. **Encoding size vs runtime correlation**: Per-run clause counts exist in raw CSV `stats` JSON but have not been aggregated or statistically analyzed.
5. **Variance across runs**: Single run per instance; no replication data.
6. **Variance across seeds**: Single seed (42); no replication data.

## Validation Status

- **Valid solutions**: 495 (431 SAT + 64 CP-SAT), 100% independently certified by `is_valid_solution_for_puzzle`
- **Invalid solutions**: 0
- **Solver crashes**: 0 in primary results
- **UNSAT on SAT-generated puzzles**: 0 (all puzzles generated from valid solutions are SAT)
- **Predeclared exclusions**: 80 (all documented with `stats.predeclared_exclusion: true`)
- **Live resource guard rejections**: 1 (commander at N=81 r=0.5)
- **Accounting reconciliation**: 960 recorded = 880 attempted + 80 predeclared; all strata reconcile

## Claims Summary for Paper

**Safe to state (with caveats):**
- SAT and CP-SAT achieve comparable valid solve rates (56.71% vs 53.33%)
- N=9 is solved at 100% by both paradigms
- N=36 r=0.5 is a hardness cliff (<21% solve rate)
- N=36 r=0.9 is easy (>98% solve rate)
- N=81 is unsolvable within 10s by both paradigms
- Zero invalid solutions; all valid solutions independently verified

**Avoid:**
- Any superiority claim (SAT > CP-SAT or vice versa)
- Any "best encoding" claim without significance testing
- Any backtracking or commercial solver comparison
- Any generalization beyond the tested dataset
