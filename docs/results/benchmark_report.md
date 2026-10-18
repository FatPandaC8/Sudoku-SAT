# Empirical Comparison of SAT vs. Non-SAT Sudoku Solvers

## 1. Executive Summary & Research Question

**Research Question:** *How do SAT-based and Non-SAT-based approaches compare in valid solve rate and solve time on identical sampled Sudoku instances?*

To isolate the algorithmic paradigms without commercial license artifacts, commercial solvers (Gurobi and CPLEX) were excluded from this evaluation. The benchmark compares:
- **SAT Solvers**: 7 configurations implemented via PySAT spanning five At-Most-One (AMO) constraint encodings (pairwise, sequential, binary, commander with $b=4$, and product) and three CDCL backends (CaDiCaL 1.5.3, Glucose 4, and MiniSat 2.2).
- **Non-SAT Solvers**: Google OR-Tools CP-SAT, a state-of-the-art constraint programming solver leveraging integer decision variables in $1..N$ and global `AllDifferent` constraints.

The experimental corpus uses the standardized 120-puzzle dataset across grid sizes $N \in \{9, 36, 81\}$ and clue removal ratios $r \in \{0.5, 0.9\}$. Evaluated here is the deterministic preliminary sample of one puzzle per $(N, r)$ pair ($k=1$, 6 instances total). Every solver invocation was executed with an isolated subprocess under a strict 10.0-second wall-clock timeout and a 5-minute total wall-clock budget. Every returned solution was independently verified by [`sudoku.validator.is_valid_solution_for_puzzle`](file:///home/guts/P2/SAT/Sudoku-SAT/src/sudoku/validator.py).

---

## 2. Experimental Execution Summary

- **Total Matrix Cells**: 48 cells (6 problem instances $\times$ 8 solver configurations).
- **Predeclared Exclusions**: 4 runs ($N=81$ pairwise and binary SAT encodings) excluded prior to execution due to memory calibration bounds predicting CNF sizes exceeding 60% of available RAM.
- **Attempted Invocations**: 44 runs (38 SAT, 6 CP-SAT).
- **Cumulative Elapsed Wall-Clock Solve Time**: 188.26 seconds (well within the 300 s / 5 min budget).
- **Unexecuted Budget Exhaustion**: 0 runs.
- **Per-Run Primary Data**: [`data/results/benchmark_sat_vs_nonsat.csv`](file:///home/guts/P2/SAT/Sudoku-SAT/data/results/benchmark_sat_vs_nonsat.csv).

---

## 3. Paper-Ready Tables

### Table 1. Primary Aggregate Comparison: SAT vs. Non-SAT Solvers

*Caption: Aggregate comparison of SAT-based and Non-SAT-based solvers across all 6 sampled Sudoku benchmark instances. Performance denominators are strictly declared: Attempted Runs exclude predeclared memory exclusions ($N=81$ pairwise and binary encodings); Valid Solve Rate is $\text{Valid Solutions} / \text{Attempted Runs}$. Commercial solvers (Gurobi, CPLEX) are excluded from the scope to eliminate licensing artifacts.*

| Metric | SAT Solvers (PySAT) | Non-SAT Solvers (OR-Tools CP-SAT) | Definition / Denominator |
| :--- | :---: | :---: | :--- |
| **Solver Configurations** | 7 | 1 | Distinct solver configurations evaluated |
| **Recorded Matrix Cells** | 42 | 6 | Total problem-configuration combinations ($6 \times \text{Configs}$) |
| **Predeclared Exclusions** | 4 | 0 | Excluded *a priori* due to memory guard; not executed |
| **Attempted Runs** | 38 | 6 | Invocations actually executed ($\text{Cells} - \text{Predeclared}$) |
| **Valid Solutions** | 23 | 4 | Solutions certified correct by independent validator |
| **Valid Solve Rate** | **60.53%** (23/38) | **66.67%** (4/6) | $\text{Valid Solutions} / \text{Attempted Runs}$ |
| **Timeouts ($>10.0\text{ s}$)** | 13 | 2 | Timeouts enforced by OS signal |
| **Timeout Rate (% of attempted)**| 34.21% (13/38) | 33.33% (2/6) | Timeouts / Attempted runs |
| **Resource Guard Live Rejections**| 1 | 0 | Estimated CNF memory exceeded 60% available RAM |
| **Invalid Solutions** | 1 | 0 | Solutions failing verification or missing payload |
| **Median Solve Time (Valid)** | **0.0083 s** | **1.3231 s** | Median wall-clock seconds for valid solutions |
| **25th Percentile ($Q_{25}$)** | 0.0064 s | 0.0236 s | First quartile of valid solve times |
| **75th Percentile ($Q_{75}$)** | 1.5931 s | 2.6471 s | Third quartile of valid solve times |
| **IQR (Variability)** | 1.5867 s | 2.6235 s | Interquartile range ($Q_{75} - Q_{25}$) |

*CSV Export: [`docs/results/table1_sat_vs_nonsat_primary.csv`](file:///home/guts/P2/SAT/Sudoku-SAT/docs/results/table1_sat_vs_nonsat_primary.csv)*

---

### Table 2. Per-Solver Breakdown

*Caption: Performance metrics for each individual solver configuration across the six sampled instances ($N \in \{9, 36, 81\} \times r \in \{0.5, 0.9\}$). Predeclared exclusions and live resource guard rejections are reported explicitly.*

| Solver Configuration | Family | Matrix Cells | Predeclared Excluded | Attempted Runs | Valid Solutions | Valid Solve Rate (%) | Timeouts | Resource Guard Live | Invalid Solutions | Median Valid Solve Time (s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `sat_pairwise_cadical153` | SAT | 6 | 2 | 4 | 3 | 75.00% | 1 | 0 | 0 | 0.007115 |
| `sat_sequential_cadical153`| SAT | 6 | 0 | 6 | 4 | 66.67% | 2 | 0 | 0 | 0.394002 |
| `sat_binary_cadical153` | SAT | 6 | 2 | 4 | 3 | 75.00% | 1 | 0 | 0 | 0.008097 |
| `sat_commander_cadical153` | SAT | 6 | 0 | 6 | 4 | 66.67% | 1 | 1 | 0 | 0.409618 |
| `sat_product_cadical153` | SAT | 6 | 0 | 6 | 4 | 66.67% | 2 | 0 | 0 | 0.635346 |
| `sat_sequential_glucose4` | SAT | 6 | 0 | 6 | 3 | 50.00% | 3 | 0 | 0 | 0.006083 |
| `sat_sequential_minisat22` | SAT | 6 | 0 | 6 | 2 | 33.33% | 3 | 0 | 1 | 0.424840 |
| `cpsat` (OR-Tools) | Non-SAT | 6 | 0 | 6 | 4 | 66.67% | 2 | 0 | 0 | 1.323146 |

*CSV Export: [`docs/results/table2_per_solver_breakdown.csv`](file:///home/guts/P2/SAT/Sudoku-SAT/docs/results/table2_per_solver_breakdown.csv)*

---

### Table 3. Difficulty Stratification ($N \times \text{removal\_ratio}$)

*Caption: Breakdown of solver performance across problem difficulty strata defined by grid size $N$ and clue removal ratio $r$. Solve rates are computed over attempted runs.*

| Grid Size $N$ | Removal Ratio $r$ | Solver Group | Attempted Runs | Valid Solutions | Valid Solve Rate (%) | Timeouts | Resource Guard Live | Invalid Solutions | Predecl. Excl. | Median Valid Solve Time (s) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **9** | **0.5** | SAT | 7 | 6 | 85.71% | 0 | 0 | 1 | 0 | 0.006051 |
| **9** | **0.5** | Non-SAT (CP-SAT) | 1 | 1 | 100.00% | 0 | 0 | 0 | 0 | 0.018030 |
| **9** | **0.9** | SAT | 7 | 7 | 100.00% | 0 | 0 | 0 | 0 | 0.006925 |
| **9** | **0.9** | Non-SAT (CP-SAT) | 1 | 1 | 100.00% | 0 | 0 | 0 | 0 | 0.025506 |
| **36** | **0.5** | SAT | 7 | 3 | 42.86% | 4 | 0 | 0 | 0 | 7.319755 |
| **36** | **0.5** | Non-SAT (CP-SAT) | 1 | 1 | 100.00% | 0 | 0 | 0 | 0 | 2.726046 |
| **36** | **0.9** | SAT | 7 | 7 | 100.00% | 0 | 0 | 0 | 0 | 1.264652 |
| **36** | **0.9** | Non-SAT (CP-SAT) | 1 | 1 | 100.00% | 0 | 0 | 0 | 0 | 2.620786 |
| **81** | **0.5** | SAT | 5 | 0 | 0.00% | 4 | 1 | 0 | 2 | — |
| **81** | **0.5** | Non-SAT (CP-SAT) | 1 | 0 | 0.00% | 1 | 0 | 0 | 0 | — |
| **81** | **0.9** | SAT | 5 | 0 | 0.00% | 5 | 0 | 0 | 2 | — |
| **81** | **0.9** | Non-SAT (CP-SAT) | 1 | 0 | 0.00% | 1 | 0 | 0 | 0 | — |

*CSV Export: [`docs/results/table3_difficulty_stratification.csv`](file:///home/guts/P2/SAT/Sudoku-SAT/docs/results/table3_difficulty_stratification.csv)*

---

## 4. Empirical Interpretation

### 4.1 Comparison of Solve Rates
- **Overall Solve Rate**: In the absence of commercial license caps, the overall solve rate between SAT solvers (**60.53%**, 23/38) and Non-SAT CP-SAT (**66.67%**, 4/6) is closely matched.
- **Top Solvers**: The leading SAT configurations (`sat_sequential_cadical153`, `sat_commander_cadical153`, and `sat_product_cadical153`) each achieved an identical solve count to CP-SAT (4 out of 6 instances solved, 66.67%).
- `sat_pairwise_cadical153` and `sat_binary_cadical153` solved 3 of 4 attempted instances (75.00%), but were excluded from attempting $N=81$ due to CNF memory scaling.

### 4.2 Solve Times and Latency Dynamics
- **$9 \times 9$ Grids**: SAT solvers demonstrate superior raw execution speed on standard instances, with median solve times of **~0.006–0.007 s**, compared to **0.018–0.026 s** for CP-SAT (approximately $3\times$ faster).
- **$36 \times 36$ Grids (Phase Transition & Robustness)**:
  - On the underconstrained / high-removal instance ($N=36, r=0.9$), SAT solvers solved all 7 configurations with a median solve time of **1.26 s** (and as fast as 0.78 s with Sequential CaDiCaL), outperforming CP-SAT (2.62 s).
  - On the more constrained / low-removal instance ($N=36, r=0.5$), CP-SAT demonstrated superior propagation stability, solving the puzzle in **2.73 s**, whereas 4 out of 7 SAT solvers timed out ($>10\text{ s}$), and the surviving SAT solvers required between 4.22 s and 8.54 s.
- **$81 \times 81$ Grids**: Neither SAT solvers nor CP-SAT produced a solution within the 10.0-second timeout. All executed runs timed out, indicating that $N=81$ represents a hard ceiling under a 10-second budget.

### 4.3 Anomalies, Memory Guards, and Verification
- Every valid solution was independently verified by the verification oracle.
- One historical run (`sudoku_N009_r0.5_i006` with `sat_sequential_minisat22`) was recorded as `INVALID_SOLUTION` due to an empty solution payload during an earlier interrupted execution.
- Live resource guarding successfully aborted `sat_commander_cadical153` at $N=81, r=0.5$ when estimated CNF memory (1.72 GB) exceeded 60% of available RAM (1.56 GB).

### 4.4 Limitations and Recommendation
- **Sample Size**: These empirical results reflect one deterministic puzzle per difficulty stratum ($k=1$, 6 instances). While effective for direct side-by-side comparison under budget constraints, findings cannot establish formal statistical significance.
- **Recommendation**: Run the full 20-puzzle-per-stratum experiment (120 puzzles total) across the top SAT configurations (`sat_sequential_cadical153`, `sat_commander_cadical153`, `sat_product_cadical153`) and CP-SAT to validate these observations with statistical confidence.
