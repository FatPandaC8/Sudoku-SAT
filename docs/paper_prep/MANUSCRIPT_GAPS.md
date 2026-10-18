# Manuscript Gaps

Author decisions, missing metadata, unresolved analysis, and limitations for
the Sudoku SAT vs. CP-SAT vs. classical backtracking manuscript
(`paper/main.tex`). Intended to guide work needed before submission.

## Author Decisions Needed (placeholders in manuscript)

| # | Item | Location | Status |
|---|------|----------|--------|
| D1 | Author name, email, affiliation, address | main.tex title block | PLACEHOLDER |
| D2 | Funding sources | main.tex Declarations > Funding | PLACEHOLDER — author confirmation required |
| D3 | Competing interests | main.tex Declarations > Competing interests | PLACEHOLDER — author confirmation required |
| D4 | Author contributions | main.tex Declarations > Author contributions | PLACEHOLDER — author confirmation required |

## Missing Metadata

| # | Item | Expected Source | Status |
|---|------|-----------------|--------|
| M1 | Hardware specifications (CPU, RAM, OS) | environment lock file | ABSENT — `environment_lock_present=false` (full_v1_run_info.json); no lock file in repository |
| M2 | Exact solver version pins | PySAT/OR-Tools versions | NOT RECORDED — backend names only (cadical153, glucose4, minisat22, ortools-cpsat) |
| M3 | Package versions (psutil, etc.) | environment lock | NOT RECORDED |
| M4 | Backtracking median solve times | backtracking_results.csv | NOT COMPUTED — code execution not permitted under this task |
| M5 | Gurobi/CPLEX license status | — | NOT AVAILABLE — adapters exist but not executed |

## Unresolved Analysis

| # | Item | Status |
|---|------|--------|
| A1 | Encoding size vs. runtime correlation | PER-RUN stats exist (primary_vars, aux_vars, total_vars, clauses) in benchmark CSV but NOT aggregated or correlated. Stated as unanalyzed in Section 5.4. |
| A2 | Confidence intervals / hypothesis tests | NOT COMPUTED — single run per instance, single seed; no variance data. |
| A3 | Backtracking with AC-3 / LCV / degree heuristics | NOT EVALUATED — implementation has these options but benchmark used use_ac3=False, randomize=False. |
| A4 | N=81 pairwise/binary SAT performance | UNKNOWN — predeclared excluded by memory guard; not measured. |
| A5 | Replication across seeds / runs | NOT PERFORMED — single seed (42), one run per instance. |

## Limitations (to retain in manuscript)

| # | Limitation | Impact |
|---|------------|--------|
| L1 | Single seed (42) and single automorphism orbit | Results may not generalize to other seeds or grid distributions |
| L2 | 20 puzzles per stratum, 120 total | Limited precision of solve-rate estimates; no confidence intervals |
| L3 | No replication (one run per instance per configuration) | No variance or reproducibility estimates |
| L4 | No confidence intervals or hypothesis tests | All statistics descriptive; no inferential claims |
| L5 | Missing environment-lock information | Reproducibility limited; hardware unknown |
| L6 | Predeclared memory exclusions (80 SAT runs at N=81) | Aggregation asymmetry; pairwise/binary N=81 performance unknown |
| L7 | Timeout censoring (10s) and survivor bias | Medians over successful runs only; censored timeouts excluded |
| L8 | Backtracking results implementation-specific | MRV + forward checking, no AC-3/LCV/degree; not generalizable to backtracking generally |
| L9 | Three pre-existing failing tests in test_full_v1.py | Impact on result validity not established; not assumed irrelevant |
| L10 | Two removal ratios only (0.5, 0.9) | No data for intermediate ratios |
| L11 | No commercial solvers (Gurobi, CPLEX) | Excluded by license; performance unknown |
| L12 | Non-unique solutions | Correctness = any valid completion matching clues |
| L13 | Backtracking source discrepancy (U1) | backtracking_results.csv vs. full_v1.jsonl contradiction unresolved |

## Backtracking Discrepancy Detail (U1)

- `backtracking_results.csv`: 120 rows, 40 SOLVED_VALID (all N=9), 80 TIMEOUT (N=36: 40, N=81: 40), validation_ok=True for solved, no errors/invalid.
- `full_v1.jsonl`: 6 backtracking runs, all SOLVER_ERROR (TypeError in Board.__post_init__), spanning N=9, 36, 81 at sampled indices; preliminary run stopped early.
- Resolution required: determine whether backtracking_results.csv represents a completed, separate backtracking benchmark run (consistent with task-stated totals of 120/40/80) or whether full_v1.jsonl's SOLVER_ERROR indicates backtracking was never successfully benchmarked. Do not re-run code.

## Figures Status

| # | Figure | Status |
|---|--------|--------|
| F1 | Valid solve rate by stratum (grouped bar) | Specification only (paper/figures/figure_specifications.tex) |
| F2 | Timeout rate by stratum (grouped bar) | Specification only |
| F3 | Median valid solve time by stratum (bar) | Specification only; backtracking medians TBD |
| F4 | Per-SAT-configuration valid solve rate (bar) | Specification only |
| F5 | Encoding size vs. runtime | NOT PLOTTED — unanalyzed; stated as future work |

## Tables Status

| # | Table | File | Status |
|---|-------|------|--------|
| T1 | Aggregate solver-family comparison | paper/tables/table1_aggregate_comparison.csv | Complete (backtracking median marked ---) |
| T2 | Per-SAT-configuration breakdown | paper/tables/table2_per_solver_breakdown.csv | Complete |
| T3 | Difficulty stratification (N x r) | paper/tables/table3_difficulty_stratification.csv | Complete (backtracking medians marked ---) |
| T4 | Backtracking by stratum | paper/tables/table4_backtracking_by_stratum.csv | Complete |

## Work Still Needed Before Submission

1. Resolve backtracking discrepancy (U1): confirm backtracking_results.csv as the authoritative backtracking source or document why full_v1.jsonl takes precedence.
2. Fill author placeholders (D1–D4): name, affiliation, funding, competing interests, contributions.
3. Optionally compute backtracking median solve times from backtracking_results.csv (M4) or retain "---".
4. Verify all plotted figure values against CSV sources before compiling figures.
5. Consider adding confidence intervals / hypothesis tests (A2) if statistical rigor is desired — currently explicitly out of scope.
6. Document exact solver versions (M2) if available from package metadata.
7. Re-read manuscript for internal consistency after any data/source changes.
