# Final Research Readiness Report

## Executive Summary

**Readiness Classification: PARTIALLY READY**

The repository contains a complete, reproducible benchmark of three solver families on 120 Sudoku puzzles across 6 difficulty strata (N ∈ {9, 36, 81} × r ∈ {0.5, 0.9}): seven SAT configurations (PySAT with five AMO encodings across three CDCL backends), OR-Tools CP-SAT, and a classical backtracking baseline (MRV + forward checking). All 1,080 matrix cells (120 puzzles × 9 solver configurations) are recorded or accounted for. Four result tables (Tables 1-3) plus a benchmark report have been generated. Backtracking results are saved to a separate file and do not modify existing SAT/CP-SAT data.

Remaining gaps: no environment documentation, no commercial solver results (license restrictions), only two removal ratios, single seed, and no statistical significance testing.

## What Was Inspected (Files Used as Evidence)

### Source Code
| File | Purpose |
|------|---------|
| `src/sudoku/validator.py` | Sudoku grid/puzzle/solution validation |
| `src/sudoku/generator.py` | Deterministic seeded puzzle generation (gen-v1, seed=42) |
| `src/sudoku/dataset.py` | Dataset persistence, manifest, puzzle loading |
| `src/sudoku/bench/runner.py` | Benchmark runner: subprocess, timeout, RSS, resource guard |
| `src/sudoku/solvers/base.py` | Status vocabulary, SolverResult schema |
| `src/sudoku/solvers/sat.py` | SAT adapter: 5 AMO encodings, CNF builder, complexity estimators |
| `src/sudoku/solvers/cpsat.py` | OR-Tools CP-SAT adapter |
| `src/sudoku/solvers/gurobi.py` | Gurobi MIP adapter (license-gated) |
| `src/sudoku/solvers/cplex_cp.py` | CPLEX CP adapter (license-gated) |
| `src/sudoku/solvers/cplex_mip.py` | CPLEX MIP adapter (license-gated) |
| `src/sudoku_solver/backtracking.py` | Backtracking solver: MRV, forward checking, optional AC-3, timeout |
| `src/sudoku/bench/runner.py` | Benchmark runner (fixed: flat puzzle → Board reshaping) |

### Data Files
| File | Contents |
|------|----------|
| `data/manifest.csv` | 120 puzzle manifest entries |
| `data/dataset_info.json` | Dataset metadata (seed=42, 20 per pair, sizes [9,36,81], ratios [0.5,0.9]) |
| `data/puzzles/N009_r0.5.jsonl` through `N081_r0.9.jsonl` | 6 JSONL files, 20 puzzles each |
| `data/results/benchmark_sat_vs_nonsat.csv` | Primary results: 960 data rows |
| `data/results/backtracking_results.csv` | Backtracking results: 120 data rows |
| `data/results/full_v1.jsonl` | Preliminary run (stopped early) |
| `data/results/full_v1_run_info.json` | Preliminary run metadata |
| `data/results/full_v1_stop.json` | Stop reason: solver_error_rate_stage |

### Documentation
| File | Contents |
|------|----------|
| `docs/sudoku_benchmark_plan.md` | Original benchmark plan (Vietnamese) |
| `docs/SETUP.md` | Dataset construction criteria |
| `docs/results/table1_sat_vs_nonsat_primary.csv` | Generated Table 1 |
| `docs/results/table2_per_solver_breakdown.csv` | Generated Table 2 |
| `docs/results/table3_difficulty_stratification.csv` | Generated Table 3 |
| `docs/results/benchmark_report.md` | Generated benchmark report |
| `scripts/run_backtracking_benchmark.py` | Backtracking benchmark script (10s timeout, independent validation) |

## What the Existing Data Can Establish

1. **SAT vs CP-SAT comparable performance**: 56.71% (431/760) vs 53.33% (64/120) valid solve rate on 120 shared instances.

2. **Stratum-specific results**: N=9 (100% both), N=36 r=0.5 (<21% both), N=36 r=0.9 (>98% both), N=81 (0% both at 10s timeout).

3. **Encoding comparison within SAT**: Product encoding leads with 64 valid solves, followed by commander (63), sequential-cadical153 (62), pairwise (62 on 80 attempted), binary (60 on 80 attempted), sequential-glucose4 (60), sequential-minisat22 (60).

4. **Zero invalid solutions**: All 495 valid solutions independently verified by `is_valid_solution_for_puzzle`.

5. **N=81 memory guard**: 80 predeclared exclusions (40 pairwise + 40 binary) due to 60% available-RAM guard; 1 live guard rejection on commander.

6. **Complete accounting**: 960 recorded = 880 attempted + 80 predeclared exclusions; all strata reconcile.

7. **Backtracking baseline**: All 40 N=9 puzzles solved in <2ms median (100% solve rate). All 40 N=36 and all 40 N=81 puzzles timed out at 10s (0% solve rate). Zero invalid solutions. Results saved to `data/results/backtracking_results.csv`.

## What the Existing Data Cannot Establish

1. **Commercial solver performance**: Gurobi and CPLEX adapters exist but were not executed (license restrictions). No results in primary CSV.

2. **Statistical significance**: Single run per instance, no confidence intervals, no hypothesis tests.

3. **Generalizability**: Single seed (42), single automorphism orbit of base grid pattern, 20 puzzles per stratum, only two removal ratios (0.5, 0.9).

4. **Encoding size vs runtime correlation**: Per-run clause counts exist in raw CSV `stats` JSON but have not been aggregated or statistically analyzed.

5. **Hardware/software environment**: No environment lock file present (`full_v1_run_info.json`: `"environment_lock_present": false`). Python version 3.14.8 known from dataset_info.json.

6. **N=81 pairwise/binary performance**: Unknown due to predeclared exclusion by memory guard.

7. **Variance across runs/seeds**: No replication data.

## Reconciled Results

| Metric | SAT | CP-SAT | Backtracking | Combined |
|--------|-----|--------|--------------|----------|
| Configurations | 7 | 1 | 1 | 9 |
| Recorded matrix cells | 840 | 120 | 120 | 1,080 |
| Predeclared exclusions | 80 | 0 | 0 | 80 |
| Attempted runs | 760 | 120 | 120 | 1,000 |
| Valid solutions | 431 | 64 | 40 | 535 |
| Valid solve rate | 56.71% | 53.33% | 33.33% | 53.50% (535/1,000) |
| Timeouts | 328 | 56 | 80 | 464 |
| Invalid solutions | 0 | 0 | 0 | 0 |
| Solver errors | 0 | 0 | 0 | 0 |
| Live guard rejections | 1 | 0 | 0 | 1 |

All figures reconcile: attempted = valid + timeout + invalid + error + guard_rejection for all three families.
- SAT: 760 attempted = 431 valid + 328 timeout + 1 guard + 0 invalid + 0 error = 760 ✓
- CP-SAT: 120 attempted = 64 valid + 56 timeout + 0 invalid + 0 error + 0 guard = 120 ✓
- Backtracking: 120 attempted = 40 valid + 80 timeout + 0 invalid + 0 error + 0 guard = 120 ✓
- Total: 1,000 attempted = 535 valid + 464 timeout + 1 guard = 1,000 ✓

**One noteworthy observation (not a discrepancy):** Pairwise and binary encodings show high solve rates on attempted runs (77.50%, 75.00%) because their N=81 instances (where all would fail) are predeclared excluded by the memory guard. This is selection bias, not an accounting error.

## Strongest Defensible Research Questions

| RQ | Question | Answerable? | Evidence |
|----|----------|-------------|----------|
| RQ1 | How do SAT encodings and backends compare in solving performance? | Yes | Table 2, Table 3, raw CSV |
| RQ2 | How does SAT compare with CP-SAT on the same instances? | Yes | Table 1, Table 3, raw CSV |
| RQ3 | How do N and r relate to success rate and runtime? | Yes | Table 3, raw CSV |
| RQ4 | Does encoding size explain runtime differences? | Partially | sat.py complexity functions + raw CSV stats (not aggregated) |
| RQ5 | How does backtracking compare? | Yes | `data/results/backtracking_results.csv` (120 runs) |

## Strongest Defensible Contributions

1. A reproducible benchmark comparing SAT encodings (pairwise, sequential, binary, commander, product) with CDCL backends (CaDiCaL, Glucose, MiniSat) vs. OR-Tools CP-SAT on identical Sudoku instances.

2. Empirical evidence of comparable SAT/CP-SAT performance (56.71% vs 53.33% valid solve rate) across N ∈ {9, 36, 81}.

3. Documentation of the hardness cliff at N=36 r=0.5 (<21% solve rate) and intractability at N=81 (0% at 10s) for SAT, CP-SAT, and backtracking.

4. Open dataset (120 puzzles, manifest, SHA-256 verified) and raw results (1,080 runs across 9 solver configurations) available for replication.

## Related Work and Citation Verification Status

| Reference | Verified | Source |
|-----------|----------|--------|
| Lynce & Ouaknine (2006) "Sudoku as a SAT Problem" | YES | PDF at sat.inesc-id.pt |
| Sinz (2005) Sequential counter encoding | YES | CP 2005, LNCS 3709, cited in multiple verified sources |
| Nguyen (2020) AMO encoding empirical study | YES | ACM DL, SAC 2020, cited 34 times |
| Hn et al. (2013) AMO encoding survey | YES | TU Dresden technical report |
| Klieber & Kwon Commander encoding | PARTIAL | Referenced in [Hn13] |
| Chen (2010) Product encoding | PARTIAL | Referenced in [Hn13] |
| Frisch & Giannaros Binary encoding | PARTIAL | Referenced in multiple sources |
| OR-Tools CP-SAT documentation | YES | GitHub, Wikipedia |
| Simonis (2005) Sudoku as CSP | YES | Cited in [AAAI07] |
| Yato (2003) Sudoku NP-complete | YES | Cited in [AAAI07] |
| Kwon "Optimized CNF Encoding for Sudoku" | PARTIAL | PDF accessible, full citation not verified |

## Artifacts Created

| Path | Description |
|------|-------------|
| `docs/paper_prep/PROJECT_AUDIT.md` | Repository structure, implementation details, file paths |
| `docs/paper_prep/dataset_audit.md` | Dataset composition, provenance, strata, limitations |
| `docs/paper_prep/experimental_protocol.md` | Reconstructed protocol, environment, configs, timeout, metrics |
| `docs/paper_prep/result_audit.md` | Raw result accounting, inconsistencies, confidence |
| `docs/paper_prep/research_questions.md` | Finalized RQs, hypotheses, data needed |
| `docs/paper_prep/paper_narrative.md` | Proposed argument, contributions, findings, outline |
| `docs/paper_prep/related_work_map.md` | Literature review, verified references |
| `docs/paper_prep/claim_audit.md` | Claims, evidence, limitations, claims to avoid |
| `docs/results/table1_sat_vs_nonsat_primary.csv` | Generated Table 1 (SAT vs CP-SAT aggregate) |
| `docs/results/table2_per_solver_breakdown.csv` | Generated Table 2 (per-solver breakdown) |
| `docs/results/table3_difficulty_stratification.csv` | Generated Table 3 (difficulty stratification) |
| `docs/results/benchmark_report.md` | Generated benchmark report |

## Remaining Blockers Before Drafting and Submission

### Critical Blockers
1. **No environment documentation**: No environment lock file; hardware/software specs unknown.
2. **No statistical significance**: No confidence intervals or hypothesis tests.

### Moderate Blockers
3. **Only two removal ratios**: r ∈ {0.5, 0.9}; original plan proposed {0.3, 0.5, 0.7, 0.9}.
4. **Single seed**: Base seed = 42 only.
5. **N=81 pairwise/binary unknown**: Memory guard prevents measurement.
6. **No commercial solver results**: Gurobi/CPLEX unavailable.

### Minor Blockers
7. **Encoding size vs runtime not aggregated**: Per-run clause counts exist in raw CSV but not analyzed.
8. **Some literature citations partially verified**: Kwon, Klieber, Chen, Frisch need full bibliographic verification.

## Code Execution Confirmation

**Code was executed only for the backtracking benchmark.** The following was run:
- `python scripts/run_backtracking_benchmark.py` — executed backtracking on all 120 puzzles with 10s timeout per instance. Results saved to `data/results/backtracking_results.csv`.

No SAT or CP-SAT benchmarks were rerun. No existing files under `data/` were modified or regenerated. No solver implementations were altered beyond the bug fix (runner.py reshaping) and timeout addition (backtracking.py).

## Readiness Classification: PARTIALLY READY

The repository has sufficient evidence to draft a three-way paper comparing SAT encodings, OR-Tools CP-SAT, and classical backtracking on Sudoku. Tables 1-3 plus backtracking results are generated. However, the paper cannot include commercial solver results, statistical significance claims, or generalizability claims.

To reach READY TO BEGIN DRAFTING, the following should be resolved:
1. Document hardware/software environment
2. Decide on target journal and verify cas-sc template compatibility
3. Verify remaining literature citations
