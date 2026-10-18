# Paper Narrative: Sudoku SAT vs CP-SAT vs Backtracking Benchmark

## Core Argument

This paper presents an empirical comparison of three solver families on Sudoku puzzles across three grid sizes (N ∈ {9, 36, 81}) and two clue-removal ratios (r ∈ {0.5, 0.9}): seven SAT configurations (PySAT with five AMO encodings across three CDCL backends), OR-Tools CP-SAT, and a classical backtracking baseline (MRV + forward checking). The central finding is that SAT solvers and OR-Tools CP-SAT achieve broadly comparable valid solve rates (56.71% vs 53.33%) on a shared 120-puzzle benchmark, while classical backtracking solves only N=9 instances (33.33% overall). All three paradigms exhibit dramatic performance cliffs at larger grid sizes, with none solving any N=81 instance within a 10-second timeout.

## What the Benchmark Measures

- Valid solve rate: fraction of attempted runs producing an independently verified valid solution
- Solve time: end-to-end wall-clock time for valid solutions (build + solve + extract + validate)
- Timeout rate: fraction of attempted runs exceeding 10.0 seconds
- Encoding complexity: auxiliary variables and clause counts per SAT encoding (analytically computable)
- Robustness: all 535 valid solutions passed independent validation; zero invalid solutions recorded across all 1,080 runs

## What the Benchmark Does NOT Measure

- Solution uniqueness (puzzles may have multiple valid solutions; any valid completion counts)
- Generalization to other puzzle distributions (grids sampled from a single automorphism orbit)
- Commercial MIP/CP solvers (Gurobi, CPLEX unavailable due to licensing)
- Runtime variance across multiple runs (single run per instance)
- Solver performance beyond 10-second timeout
- Memory-constrained behavior beyond the resource guard (N=81 pairwise/binary excluded)

## Main Findings (Supported by Data)

1. **Comparable overall performance**: SAT (56.71%, 431/760) and CP-SAT (53.33%, 64/120) achieve similar valid solve rates on the full 120-puzzle benchmark.

2. **N=9 is trivial**: Both paradigms achieve 100% solve rate on all 40 instances (20 per ratio), with sub-10ms median solve times.

3. **N=36 r=0.5 is a hardness cliff**: Valid solve rates drop to 9.29% (SAT) and 20.0% (CP-SAT). Most runs timeout at ~7 seconds.

4. **N=36 r=0.9 is easy**: Both paradigms solve nearly all instances (SAT 98.57%, CP-SAT 100%).

5. **N=81 is intractable at 10s**: Zero valid solutions for both paradigms. SAT pairwise and binary encodings are predeclared excluded by memory guard; all other configurations timeout.

6. **Product encoding leads SAT**: sat_product_cadical153 achieves 64 valid solves (53.33%), matching CP-SAT's total. sat_commander_cadical153 is close second with 63.

7. **Encoding exclusion affects apparent rates**: pairwise (77.50%) and binary (75.00%) show high rates on attempted runs because N=81 instances (where all would fail) are excluded by the memory guard.

8. **Backtracking is effective only at N=9**: Classical backtracking (MRV + forward checking) solves all 40 N=9 instances in sub-millisecond median time but times out on all 40 N=36 and all 40 N=81 instances at the 10-second limit (33.33% overall valid solve rate).

## Potential Explanations (Separated from Evidence)

**Demonstrated:** The observed solve rates and times are measured facts.

**Plausible but not demonstrated:**
- The N=36 r=0.5 hardness spike may reflect the constrained-search regime where few clues leave many possibilities but the puzzle remains tightly constrained.
- The N=36 r=0.9 ease may reflect underconstrained problems where solutions are abundant and easy to find.
- CP-SAT's AllDifferent propagation may be more effective than SAT's AMO encodings at N=36 r=0.9 (100% vs 98.57%).
- SAT's faster median times at N=9 r=0.9 (0.0083s vs 0.0332s) may reflect CDCL clause learning advantages on small, highly constrained instances.
- The memory guard exclusion of pairwise/binary at N=81 reflects O(N⁴) clause growth for pairwise encoding.

These are hypotheses requiring further analysis; they are not claims made in this paper.

## Legitimate Contributions

1. A reproducible benchmark suite for Sudoku solving comparing SAT encodings, CP-SAT, and classical backtracking on identical instances
2. Empirical evidence that SAT and CP-SAT are comparable on Sudoku across sizes N ∈ {9, 36, 81} (56.71% vs 53.33%)
3. Documentation that classical backtracking is effective only at N=9, timing out on all N=36 and N=81 instances
4. Documentation of the performance cliff at N=36 r=0.5 and N=81 for all three paradigms
5. Open dataset (120 puzzles) and raw results (1,080 runs across 9 solver configurations) available for replication

## Limitations and Threats to Validity

1. **Single seed**: All puzzles generated with base seed 42; results may not generalize across seeds.
2. **Small sample**: 20 puzzles per stratum; confidence intervals not computed.
3. **Non-uniform grid distribution**: Puzzles sampled from a single automorphism orbit of the base pattern.
4. **Non-unique solutions**: Puzzles may have multiple valid solutions; correctness = any valid completion.
5. **Two ratios only**: r ∈ {0.5, 0.9}; no data for r ∈ {0.3, 0.7}.
6. **Single timeout**: 10.0s; results may differ with larger time budgets.
7. **No commercial solvers**: Gurobi/CPLEX unavailable due to licensing.
8. **N=81 memory guard**: pairwise and binary SAT encodings predeclared excluded at N=81; their N=81 performance unknown.
9. **No variance data**: Single run per instance; no replication.

## Claims to Avoid

- "SAT is better than CP-SAT for Sudoku" — rates are comparable (56.71% vs 53.33%)
- "Product encoding is the best SAT encoding" — it has the highest count (64) but differences vs commander (63) and sequential (62) are small and untested for significance
- "Backtracking is slower than SAT/CP-SAT" — backtracking times out at N=36/N=81 but is faster at N=9 (sub-ms median); no blanket comparison is supported
- "N=81 Sudoku is unsolvable by SAT/CP-SAT" — unsolvable within 10s only; may be solvable with larger timeouts
- Statistical significance claims — no confidence intervals or hypothesis tests computed
- Generalization to other puzzle distributions — single automorphism orbit, single seed

## Section-by-Section Outline

1. **Abstract** — Placeholder
2. **Keywords** — Placeholder
3. **Introduction** — Motivation, problem definition, research questions, contributions
4. **Related Work** — SAT encodings for Sudoku, CP-SAT, backtracking, encoding-size/runtime trade-offs
5. **Problem Formulation** — Sudoku as CSP, SAT encoding (one-hot + AMO), CP-SAT model
6. **Experimental Setup** — Dataset generation, solver configurations, timeout policy, validation, metrics
7. **Results** — Tables 1-3, stratum analysis, encoding comparison, N=81 exclusion analysis
8. **Threats to Validity** — All limitations listed above
9. **Conclusion** — Summary, implications, future work
10. **Declarations** — Data availability, code availability, conflicts, funding (placeholders)
11. **References** — Verified bibliography

## Evidence-to-Claim Mapping

| Claim | Evidence | Confidence |
|-------|----------|------------|
| SAT 56.71% vs CP-SAT 53.33% valid solve rate | Table 1, raw CSV | HIGH |
| N=9: both 100% solve rate | Table 3, raw CSV | HIGH |
| N=36 r=0.5: SAT 9.29%, CP-SAT 20.0% | Table 3, raw CSV | HIGH |
| N=36 r=0.9: SAT 98.57%, CP-SAT 100% | Table 3, raw CSV | HIGH |
| N=81: both 0.00% solve rate | Table 3, raw CSV | HIGH |
| Product encoding: 64 valid solves (highest SAT) | Table 2, raw CSV | HIGH |
| Pairwise/binary excluded at N=81 | Table 2, raw CSV, runner.py resource guard | HIGH |
| Zero invalid solutions | Table 1, Table 2, Table 3 | HIGH |
| All 495 solutions independently validated | Table 1 (431+64=495), validator.py | HIGH |
