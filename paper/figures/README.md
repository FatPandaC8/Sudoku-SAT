# Figure Specifications (specification-only; no code executed)

This directory contains specifications for figures referenced in the manuscript.
No figures are rendered here because generating them would require executing code
against the raw data, which is outside the scope of this manuscript-writing task.
Each specification describes the data source, axes, and intended content so the
figures can be reproduced from `data/results/benchmark_sat_vs_nonsat.csv` and
`data/results/backtracking_results.csv`.

## Figure 1. Valid solve rate by solver family (bar chart)

- **Data source**: `paper/tables/table1_aggregate_comparison.csv`
- **X-axis**: Solver family (SAT 7 configs, CP-SAT 1 config, Backtracking 1 config)
- **Y-axis**: Valid solve rate (% of attempted runs)
- **Bars**: SAT 56.71%, CP-SAT 53.33%, Backtracking 33.33%
- **Annotation**: Attempted runs below each bar (760, 120, 120)
- **Caveat**: SAT pools seven configurations; not directly comparable per-configuration

## Figure 2. Valid solve rate by stratum and solver family (grouped bar chart)

- **Data source**: `paper/tables/table3_difficulty_stratification.csv`
- **X-axis**: Stratum (N=9 r=0.5, N=9 r=0.9, N=36 r=0.5, N=36 r=0.9, N=81 r=0.5, N=81 r=0.9)
- **Y-axis**: Valid solve rate (%)
- **Groups**: SAT, CP-SAT, Backtracking
- **Expected pattern**: 100% for all at N=9; drop at N=36 r=0.5; 0% at N=81 for all; backtracking 0% at N=36 and N=81

## Figure 3. Per-SAT-configuration valid solves (bar chart)

- **Data source**: `paper/tables/table2_per_solver_breakdown.csv`
- **X-axis**: SAT configuration (7 configurations)
- **Y-axis**: Valid solutions (count out of attempted)
- **Bars**: pairwise 62/80, sequential-cadical 62/120, binary 60/80, commander 63/120, product 64/120, glucose4 60/120, minisat22 60/120
- **Annotation**: Attempted runs and predeclared exclusions noted

## Figure 4. Solve-time distribution by stratum (box plot specification)

- **Data source**: `data/results/benchmark_sat_vs_nonsat.csv` (t_total for SOLVED_VALID rows)
- **Note**: Cannot be constructed from existing aggregate tables; requires per-run t_total values grouped by stratum and solver. Provide a plotting script that reads the CSV, filters SOLVED_VALID, and plots box plots of t_total by (N, r, solver family).
- **Caveat**: Median solve times in tables are over successful runs only; timeouts are censored and excluded.

## Figure 5. Encoding size vs. runtime (scatter plot specification)

- **Data source**: `data/results/benchmark_sat_vs_nonsat.csv` (stats.clauses, stats.aux_vars, t_total)
- **Note**: Per-run clause counts exist in the raw CSV stats field but have not been aggregated or correlated with runtime. A scatter plot of clauses vs. t_total for SOLVED_VALID SAT runs would address RQ1's encoding-size question, but no such analysis has been performed. This figure is specified but not generated.
- **Caveat**: Relationship between encoding size and runtime is unanalyzed (Section 5.4 of manuscript).

## Reproduction

All figures can be regenerated from the CSV sources above using matplotlib or ggplot2. No code was executed to produce figures in this task.
