# Result Audit: Raw Benchmark Data Accounting

## Source of Truth

- `data/results/benchmark_sat_vs_nonsat.csv` — Primary results: 960 data rows
- `docs/results/table1_sat_vs_nonsat_primary.csv` — Generated Table 1
- `docs/results/table2_per_solver_breakdown.csv` — Generated Table 2
- `docs/results/table3_difficulty_stratification.csv` — Generated Table 3
- `docs/results/benchmark_report.md` — Generated benchmark report

## Overall Accounting

| Metric | Value | Basis |
|--------|-------|-------|
| Total matrix cells (recorded) | 960 | 120 puzzles × 8 solver configurations |
| Puzzles | 120 | 6 strata × 20 puzzles |
| Solver configurations | 8 | 7 SAT + 1 CP-SAT |
| Predeclared exclusions | 80 | N=81 SAT pairwise + binary (40 each) |
| Attempted runs | 880 | 960 − 80 predeclared exclusions |
| SAT attempted runs | 760 | 840 − 80 predeclared |
| CP-SAT attempted runs | 120 | 120 − 0 |
| Valid solutions (SAT) | 431 | 56.71% of 760 |
| Valid solutions (CP-SAT) | 64 | 53.33% of 120 |
| Total valid solutions | 495 | 431 + 64 |
| Invalid solutions | 0 | All valid solutions passed independent validation |
| Solver errors/crashes | 0 | None recorded in primary results |

## Accounting Reconciliation Check

| Check | Expected | Observed | Match? |
|-------|----------|----------|--------|
| SAT recorded cells | 7 configurations × 120 puzzles = 840 | 840 (Table 1) | Yes |
| CP-SAT recorded cells | 1 configuration × 120 puzzles = 120 | 120 (Table 1) | Yes |
| Total recorded | 840 + 120 = 960 | 960 | Yes |
| SAT predeclared exclusions | 80 (pairwise 40 + binary 40 at N=81) | 80 | Yes |
| SAT attempted runs | 840 − 80 = 760 | 760 | Yes |
| SAT timeouts + valid + errors + invalid + guard | 328 + 431 + 0 + 0 + 1 = 760 | 760 | Yes |
| CP-SAT attempted runs | 120 − 0 = 120 | 120 | Yes |
| CP-SAT timeouts + valid | 56 + 64 = 120 | 120 | Yes |
| Total attempted | 760 + 120 = 880 | 880 | Yes |

## Results by Solver Configuration (Table 2)

| Configuration | Family | Recorded | Predeclared | Attempted | Valid | Rate | Timeouts | Guard | Invalid | Median (s) |
|---------------|--------|----------|-------------|-----------|-------|------|----------|-------|---------|------------|
| sat_pairwise_cadical153 | SAT | 120 | 40 | 80 | 62 | 77.5% | 18 | 0 | 0 | 0.009861 |
| sat_sequential_cadical153 | SAT | 120 | 0 | 120 | 62 | 51.7% | 58 | 0 | 0 | 0.007760 |
| sat_binary_cadical153 | SAT | 120 | 40 | 80 | 60 | 75.0% | 20 | 0 | 0 | 0.011180 |
| sat_commander_cadical153 | SAT | 120 | 0 | 120 | 63 | 52.5% | 56 | 1 | 0 | 0.008905 |
| sat_product_cadical153 | SAT | 120 | 0 | 120 | 64 | 53.3% | 56 | 0 | 0 | 0.009016 |
| sat_sequential_glucose4 | SAT | 120 | 0 | 120 | 60 | 50.0% | 60 | 0 | 0 | 0.007728 |
| sat_sequential_minisat22 | SAT | 120 | 0 | 120 | 60 | 50.0% | 60 | 0 | 0 | 0.006915 |
| cpsat | CP-SAT | 120 | 0 | 120 | 64 | 53.3% | 56 | 0 | 0 | 0.033353 |

Note: sat_pairwise_cadical153 and sat_binary_cadical153 each have 40 predeclared exclusions (N=81 memory guard). Their higher rates on attempted runs (77.5%, 75.0%) reflect exclusion of the N=81 stratum where all runs would fail.

## Results by Difficulty Stratum (Table 3)

| N | r | Solver | Attempted | Valid | Rate | Timeouts | Guard | Invalid | Predecl | Median (s) |
|---|---|--------|-----------|-------|------|----------|-------|---------|---------|------------|
| 9 | 0.5 | SAT | 140 | 140 | 100.0% | 0 | 0 | 0 | 0 | 0.008018 |
| 9 | 0.5 | CP-SAT | 20 | 20 | 100.0% | 0 | 0 | 0 | 0 | 0.003896 |
| 9 | 0.9 | SAT | 140 | 140 | 100.0% | 0 | 0 | 0 | 0 | 0.008288 |
| 9 | 0.9 | CP-SAT | 20 | 20 | 100.0% | 0 | 0 | 0 | 0 | 0.033160 |
| 36 | 0.5 | SAT | 140 | 13 | 9.29% | 127 | 0 | 0 | 0 | 6.981681 |
| 36 | 0.5 | CP-SAT | 20 | 4 | 20.0% | 16 | 0 | 0 | 0 | 7.008288 |
| 36 | 0.9 | SAT | 140 | 138 | 98.57% | 2 | 0 | 0 | 0 | 1.508942 |
| 36 | 0.9 | CP-SAT | 20 | 20 | 100.0% | 0 | 0 | 0 | 0 | 2.270578 |
| 81 | 0.5 | SAT | 100 | 0 | 0.00% | 99 | 1 | 0 | 40 | — |
| 81 | 0.5 | CP-SAT | 20 | 0 | 0.00% | 20 | 0 | 0 | 0 | — |
| 81 | 0.9 | SAT | 100 | 0 | 0.00% | 100 | 0 | 0 | 40 | — |
| 81 | 0.9 | CP-SAT | 20 | 0 | 0.00% | 20 | 0 | 0 | 0 | — |

Stratum accounting check (SAT):
- N=9, r=0.5: 7 configs × 20 = 140 attempted ✓ (0 predeclared)
- N=9, r=0.9: 7 configs × 20 = 140 attempted ✓ (0 predeclared)
- N=36, r=0.5: 7 configs × 20 = 140 attempted ✓ (0 predeclared)
- N=36, r=0.9: 7 configs × 20 = 140 attempted ✓ (0 predeclared)
- N=81, r=0.5: 7 configs × 20 = 140 recorded − 40 predeclared = 100 attempted ✓
- N=81, r=0.9: 7 configs × 20 = 140 recorded − 40 predeclared = 100 attempted ✓

Stratum accounting check (CP-SAT):
- All 6 strata: 1 config × 20 = 20 attempted ✓ (0 predeclared)

## Key Findings

### N=9 (Standard Sudoku)
- Both SAT and CP-SAT achieve 100% solve rate on all 20 puzzles per ratio
- CP-SAT median solve time slightly lower at r=0.5 (0.0039s vs 0.0080s)
- SAT median solve time significantly lower at r=0.9 (0.0083s vs 0.0332s, ~4x faster)

### N=36 (Medium Sudoku)
- **r=0.9 (underconstrained)**: CP-SAT 100% (20/20), SAT 98.57% (138/140). SAT median 1.51s faster than CP-SAT 2.27s.
- **r=0.5 (constrained)**: Severe difficulty spike. SAT 9.29% (13/140), CP-SAT 20.0% (4/20). Median valid solve times cluster around 7.0s for both.

### N=81 (Large Sudoku)
- Zero valid solutions for both SAT and CP-SAT across all 6 strata
- SAT: 99-100% timeouts at r=0.5/r=0.9 respectively; 40 predeclared exclusions per stratum (memory guard)
- CP-SAT: 100% timeouts (20/20 per stratum)
- Median solve time: N/A (no valid solutions)

### Encoding Comparison (SAT, all sizes)
- sat_product_cadical153: highest valid solves (64), matches CP-SAT total (64)
- sat_commander_cadical153: second highest (63)
- sat_pairwise_cadical153: 62 valid on 80 attempted (77.5% rate, but excludes N=81)
- sat_binary_cadical153: 60 valid on 80 attempted (75.0% rate, but excludes N=81)
- sat_sequential_cadical153: 62 valid on 120 attempted (51.67%)
- sat_sequential_glucose4: 60 valid (50.0%)
- sat_sequential_minisat22: 60 valid (50.0%)

## Inconsistencies and Unresolved Issues

### Issue 1: N=81 SAT Predeclared Exclusions Count

**Raw data**: 80 predeclared exclusions at N=81 (40 pairwise + 40 binary across both ratios).
**Interpretation**: The resource guard excludes pairwise and binary encodings at N=81 because estimated CNF memory exceeds 60% of available RAM.
**Question**: Why only pairwise and binary? Other encodings (sequential, commander, product) at N=81 were NOT predeclared excluded — they were attempted and all timed out. This suggests the guard threshold was calibrated specifically for pairwise/binary memory footprints.
**Status**: Documented in raw data. No conflict, but the selective exclusion needs explanation in the paper.

### Issue 2: "Extra Backend" Label for minisat22

**Raw data**: The solver label `sat_sequential_minisat22_extra_backend` includes "_extra_backend" suffix (from runner.py label property: `extra_tag = "_extra_backend" if self.backend == "minisat22"`).
**Implication**: This suggests minisat22 was treated as a secondary/extra backend in the experimental design, not part of the primary comparison.
**Status**: Naming artifact from code; does not affect results validity.

### Issue 3: One Live Resource Guard Rejection

**Raw data**: `sat_commander_cadical153` at N=81 has 1 RESOURCE_GUARD_LIVE rejection (Table 2).
**Location**: Table 2 shows `sat_commander_cadical153` with 1 Resource Guard Live rejection.
**Table 3**: N=81 SAT r=0.5 shows 1 Resource Guard Live; N=81 SAT r=0.9 shows 0.
**Interpretation**: One commander encoding run at N=81 r=0.5 was rejected by the live resource guard during execution (not predeclared). This is distinct from the 40 predeclared exclusions.
**Status**: Documented. Not double-counted: predeclared exclusions and live rejections are separate categories.

### Issue 4: N=81 Median Solve Time Marked as "—"

**Raw data**: N=81 SAT and CP-SAT have zero valid solutions.
**Table 3**: Median Valid Solve Time shown as "—" (N/A) for all N=81 entries.
**Correctness**: Correct per the rule "Use N/A when no valid solve time exists."
**Status**: No inconsistency.

### Issue 5: Preliminary Run (full_v1) Stopped Early

**Raw data**: `full_v1_stop.json` shows stop reason "solver_error_rate_stage: 1/10 > 2% at N=9".
**Implication**: The preliminary run was stopped due to backtracking solver errors (TypeError in Board initialization). Backtracking results are not included in the primary benchmark.
**Status**: Backtracking cannot be reported as a benchmark result. Its adapter exists in code but produces SOLVER_ERROR on all attempts due to implementation bug.

### Issue 6: Gurobi/CPLEX Exclusion

**Raw data**: No Gurobi or CPLEX results in `benchmark_sat_vs_nonsat.csv`.
**Reason**: These solvers require commercial licenses not available in the environment.
**Status**: Explicitly excluded per task requirements. Adapters exist in code but were not executed.

## Confidence Assessment

| Aspect | Confidence | Basis |
|--------|-----------|-------|
| Total run count (960) | HIGH | Direct CSV count |
| Predeclared exclusions (80) | HIGH | Direct CSV status field + stats.predeclared_exclusion |
| Valid solve counts | HIGH | Direct CSV status field |
| Timeout counts | HIGH | Direct CSV status field |
| Median solve times | HIGH | Computed from t_total for SOLVED_VALID rows |
| Gurobi/CPLEX exclusion | HIGH | No records in CSV; adapters exist but license-gated |
| Backtracking exclusion | HIGH | full_v1.jsonl shows all backtracking runs as SOLVER_ERROR |
| Hardware/environment specs | LOW | No environment lock file; python version only from dataset_info.json |
| Exact solver versions | MODERATE | Backend names in CSV (cadical153, glucose4, minisat22) but no version pins |

## Evidence Mapping

Every figure in this audit traces directly to:
- `data/results/benchmark_sat_vs_nonsat.csv` (primary CSV, 960 rows)
- `docs/results/table1_sat_vs_nonsat_primary.csv` (generated Table 1)
- `docs/results/table2_per_solver_breakdown.csv` (generated Table 2)
- `docs/results/table3_difficulty_stratification.csv` (generated Table 3)
- `src/sudoku/solvers/base.py` (status vocabulary)
- `src/sudoku/bench/runner.py` (resource guard, timeout, execution logic)
- `data/results/full_v1_stop.json` (preliminary run stop reason)
