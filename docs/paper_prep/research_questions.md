# Research Questions

## Scope Constraint

All research questions must be answerable from the existing data in `data/results/benchmark_sat_vs_nonsat.csv` (960 runs, 120 puzzles, 8 solver configurations). No additional experiments will be run.

## RQ1: SAT Encoding and Backend Comparison

**Question:** How do the five SAT AMO encodings (pairwise, sequential, binary, commander, product) and three backends (CaDiCaL 1.5.3, Glucose 4, MiniSat 2.2) compare in valid solve rate and solve time on the same Sudoku instances?

**Data needed:** Per-configuration results from Table 2 (docs/results/table2_per_solver_breakdown.csv), stratified by N and r from Table 3.

**Answerable from existing data?** Yes.

**Supporting evidence:**
- Table 2: sat_product_cadical153 = 64 valid (53.33%), sat_commander_cadical153 = 63 valid (52.50%), sat_sequential_cadical153 = 62 valid (51.67%), sat_pairwise_cadical153 = 62 valid on 80 attempted (77.50% but N=81 excluded), sat_binary_cadical153 = 60 valid on 80 attempted (75.00% but N=81 excluded), sat_sequential_glucose4 = 60 valid (50.00%), sat_sequential_minisat22 = 60 valid (50.00%)
- Encoding complexity data available from `src/sudoku/solvers/sat.py` (estimate_encoding_clauses, estimate_encoding_aux_vars functions) but NOT recorded per-run in the CSV beyond stats field
- Median solve times per configuration in Table 2

**Limitations:**
- pairwise and binary encodings at N=81 are predeclared excluded (memory guard), so their performance at N=81 is unknown
- Only cadical153 backend tested for pairwise, binary, commander, product; glucose4 and minisat22 only tested with sequential encoding
- Full factorial (all 5 encodings × 3 backends) was NOT executed

## RQ2: SAT vs CP-SAT Comparison

**Question:** How do SAT-based solvers (PySAT with CDCL backends) compare with OR-Tools CP-SAT in valid solve rate and solve time on identical Sudoku instances?

**Data needed:** Table 1 aggregate comparison + per-stratum breakdown from Table 3.

**Answerable from existing data?** Yes.

**Supporting evidence:**
- Table 1: SAT 56.71% (431/760) vs CP-SAT 53.33% (64/120) — comparable overall
- N=9: both 100% (SAT median 0.0080-0.0083s vs CP-SAT 0.0039-0.0332s)
- N=36 r=0.9: SAT 98.57% vs CP-SAT 100%; SAT median 1.51s vs CP-SAT 2.27s
- N=36 r=0.5: SAT 9.29% vs CP-SAT 20.0%; both ~7s median valid solve time
- N=81: both 0.00% (all timeouts)

**Limitations:**
- CP-SAT tested with only 1 configuration (default parameters)
- SAT has 7 configurations; comparing "best SAT" vs CP-SAT may favor SAT due to multiple attempts
- pairwise/binary SAT excluded at N=81, making SAT appear stronger than it might be at that size

## RQ3: Puzzle Size and Removal Ratio Effects

**Question:** How do grid size (N ∈ {9, 36, 81}) and clue-removal ratio (r ∈ {0.5, 0.9}) relate to success rate and solve time?

**Data needed:** Table 3 (docs/results/table3_difficulty_stratification.csv).

**Answerable from existing data?** Yes.

**Supporting evidence:**
- N=9, r=0.5: 100% / 100%; N=9, r=0.9: 100% / 100% — trivial for both solvers
- N=36, r=0.5: 9.29% SAT / 20.0% CP-SAT — severe difficulty spike
- N=36, r=0.9: 98.57% SAT / 100% CP-SAT — easy for both
- N=81, r=0.5: 0.00% / 0.00%; N=81, r=0.9: 0.00% / 0.00% — unsolvable within 10s for both
- Non-monotonic relationship: N=36 r=0.9 easier than N=36 r=0.5 (underconstrained easier than constrained)

**Limitations:**
- Only two ratios tested (0.5, 0.9); the plan originally proposed {0.3, 0.5, 0.7, 0.9}
- 20 puzzles per stratum may not capture variance
- Removal ratio is not a difficulty label (per generator documentation)

## RQ4: Encoding Size vs Runtime (Partial)

**Question:** Does SAT encoding size (aux variables, clause count) help explain observed runtime differences among SAT encodings?

**Data needed:** Encoding complexity formulas from `src/sudoku/solvers/sat.py` (estimate_encoding_clauses, estimate_encoding_aux_vars) combined with per-configuration solve times from Table 2.

**Answerable from existing data?** Partially.

**Supporting evidence:**
- Encoding complexity can be computed analytically from N and encoding type (functions exist in sat.py)
- Per-configuration median solve times are recorded in Table 2
- But: per-run clause counts and aux variable counts are in the `stats` JSON field of the raw CSV, not aggregated in Table 2 or Table 3
- No statistical test of correlation between encoding size and runtime has been performed

**Limitations:**
- Encoding size data exists per-run in raw CSV stats but has not been aggregated or correlated with runtime
- Build time (t_build) is recorded but not aggregated in any table
- Would require additional analysis beyond what Table 1-3 provide

## RQ5 (Answerable): Backtracking Baseline

**Question:** How does classical backtracking compare with SAT and CP-SAT on the same Sudoku instances?

**Answerable from existing data?** Yes — results saved to `data/results/backtracking_results.csv`.

**Supporting evidence:**
- Backtracking achieves 100% solve rate on N=9 (40/40), median <1ms
- Backtracking times out on all N=36 (40/40) and N=81 (40/40) instances at 10s
- Zero invalid solutions across all 120 runs
- Backtracking valid solve rate: 33.33% (40/120), compared to SAT 56.71% and CP-SAT 53.33%

**Limitations:**
- Single run per instance, no variance data
- Same dataset limitations as SAT/CP-SAT (single seed, 20 puzzles per stratum)

## Summary of Answerable vs Unanswerable Questions

| Question | Answerable? | Evidence Source |
|----------|------------|-----------------|
| RQ1: SAT encoding/backend comparison | Yes | Table 2, Table 3, raw CSV |
| RQ2: SAT vs CP-SAT | Yes | Table 1, Table 3, raw CSV |
| RQ3: Size × ratio effects | Yes | Table 3, raw CSV |
| RQ4: Encoding size ↔ runtime | Partially | sat.py complexity functions + raw CSV stats |
| RQ5: Backtracking baseline | Yes | `data/results/backtracking_results.csv` |

## Hypotheses (Where Supported)

None formally tested. Observations from data:

1. **N=9 is trivial**: Both paradigms solve all instances in <10ms median.
2. **N=36 r=0.5 is the hardest stratum**: <21% solve rate for both paradigms.
3. **N=36 r=0.9 is easy**: >98% solve rate for both paradigms.
4. **N=81 is intractable at 10s timeout**: 0% solve rate for both paradigms.
5. **SAT and CP-SAT are comparable overall**: 56.71% vs 53.33% valid solve rate.
6. **Encoding choice matters within SAT**: Product encoding achieves highest valid count (64) among SAT configs.

## Data Gaps

1. No hardware/software environment documentation (no environment lock file)
2. No per-run clause/aux variable aggregation in summary tables
3. No build-time breakdown by encoding
4. No replication across seeds (single seed = 42)
5. Only two removal ratios (0.5, 0.9)
6. Backtracking results unavailable (implementation bug)
7. Gurobi/CPLEX unavailable (license restrictions)
