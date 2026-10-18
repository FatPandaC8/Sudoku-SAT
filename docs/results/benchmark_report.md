# Empirical Comparison of SAT vs. Non-SAT Sudoku Solvers

## 1. Executive Summary & Research Question

**Research Question:** *How do SAT-based and Non-SAT-based approaches compare in valid solve rate and solve time on identical sampled Sudoku instances?*

To isolate algorithmic paradigms without commercial license artifacts or vendor caps, commercial solvers (Gurobi and CPLEX) were completely excluded from the benchmark matrix, execution, and results. This study compares:
- **SAT Solvers**: 7 configurations implemented via PySAT spanning five At-Most-One (AMO) constraint encodings (pairwise, sequential, binary, commander with $b=4$, and product) and three CDCL backends (CaDiCaL 1.5.3, Glucose 4, and MiniSat 2.2).
- **Non-SAT Solvers**: Google OR-Tools CP-SAT, a state-of-the-art constraint programming solver leveraging integer decision variables in $1..N$ and global `AllDifferent` constraints with conflict-driven clause learning.

The experiment was conducted on the full standardized **120-puzzle dataset** spanning three grid dimensions $N \in \{9, 36, 81\}$ and two clue removal ratios $r \in \{0.5, 0.9\}$ (20 deterministic puzzle instances per stratum). Every solver run was executed in an isolated child subprocess under a strict 10.0-second wall-clock timeout. Every returned solution was independently verified by [`sudoku.validator.is_valid_solution_for_puzzle`](file:///home/guts/P2/SAT/Sudoku-SAT/src/sudoku/validator.py).

---

## 2. Experimental Execution Summary

- **Total Corpus Size**: 120 puzzles across 6 difficulty strata.
- **Evaluated Solver Configurations**: 8 configurations (7 SAT, 1 CP-SAT).
- **Total Recorded Matrix Cells**: 960 cells ($120 \times 8$).
- **Predeclared Exclusions**: 80 runs ($N=81$ pairwise and binary SAT encodings, 40 each) excluded prior to execution due to memory calibration bounds predicting CNF sizes exceeding 60% of available RAM.
- **Attempted Invocations**: 880 runs (760 SAT, 120 CP-SAT).
- **Solution Verification**: 495 valid solutions produced, **100% independently certified correct** by the Sudoku validator.
- **Invalid Solutions**: 0.
- **Solver Errors / Crashes**: 0.
- **Execution Completion**: 100% of all 960 matrix cells executed or accounted for without data loss or duplicate records.
- **Primary Data**: [`data/results/benchmark_sat_vs_nonsat.csv`](file:///home/guts/P2/SAT/Sudoku-SAT/data/results/benchmark_sat_vs_nonsat.csv) and [`data/results/full_v1.jsonl`](file:///home/guts/P2/SAT/Sudoku-SAT/data/results/full_v1.jsonl).

---

## 3. Paper-Ready Tables

### Table 1. Primary Aggregate Comparison: SAT vs. Non-SAT Solvers

*Caption: Aggregate performance comparison of SAT-based solvers (PySAT) and Non-SAT solver (Google OR-Tools CP-SAT) across the complete 120-puzzle Sudoku benchmark. Denominators are strictly declared: Attempted Runs exclude predeclared memory guard exclusions ($N=81$ pairwise and binary encodings); Valid Solve Rate is $\text{Valid Solutions} / \text{Attempted Runs}$. Commercial solvers (Gurobi, CPLEX) are completely excluded.*

| Metric | SAT Solvers (PySAT) | Non-SAT Solvers (OR-Tools CP-SAT) | Definition / Denominator |
| :--- | :---: | :---: | :--- |
| **Solver Configurations** | 7 | 1 | Distinct solver configurations evaluated |
| **Recorded Matrix Cells** | 840 | 120 | Total problem-configuration combinations ($120 \times \text{Configs}$) |
| **Predeclared Exclusions** | 80 | 0 | Excluded *a priori* due to memory guard; not executed |
| **Attempted Runs** | 760 | 120 | Invocations actually executed ($\text{Cells} - \text{Predeclared}$) |
| **Valid Solutions** | 431 | 64 | Solutions certified correct by independent validator |
| **Valid Solve Rate** | **56.71%** (431/760) | **53.33%** (64/120) | $\text{Valid Solutions} / \text{Attempted Runs}$ |
| **Timeouts ($>10.0\text{ s}$)** | 328 | 56 | Timeouts enforced by OS signal |
| **Timeout Rate (% of attempted)**| 43.16% (328/760) | 46.67% (56/120) | Timeouts / Attempted runs |
| **Resource Guard Live Rejections**| 1 | 0 | Estimated CNF memory exceeded 60% available RAM |
| **Invalid Solutions** | 0 | 0 | Solutions failing verification or missing payload |
| **Median Solve Time (Valid)** | **0.009367 s** | **0.033353 s** | Median wall-clock seconds for valid solutions |
| **25th Percentile ($Q_{25}$)** | 0.007619 s | 0.004202 s | First quartile of valid solve times |
| **75th Percentile ($Q_{75}$)** | 1.012088 s | 2.227055 s | Third quartile of valid solve times |
| **IQR (Variability)** | 1.004469 s | 2.222852 s | Interquartile range ($Q_{75} - Q_{25}$) |

*CSV Export: [`docs/results/table1_sat_vs_nonsat_primary.csv`](file:///home/guts/P2/SAT/Sudoku-SAT/docs/results/table1_sat_vs_nonsat_primary.csv)*

---

### Table 2. Per-Solver Breakdown

*Caption: Performance metrics for each individual solver configuration across all 120 benchmark instances ($N \in \{9, 36, 81\} \times r \in \{0.5, 0.9\}$, 20 instances per stratum). Predeclared exclusions and live resource guard rejections are explicitly reported.*

| Solver Configuration | Family | Matrix Cells | Predeclared Excluded | Attempted Runs | Valid Solutions | Valid Solve Rate (%) | Timeouts | Resource Guard Live | Invalid Solutions | Median Valid Solve Time (s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `sat_pairwise_cadical153` | SAT | 120 | 40 | 80 | 62 | 77.50% | 18 | 0 | 0 | 0.009861 |
| `sat_sequential_cadical153`| SAT | 120 | 0 | 120 | 62 | 51.67% | 58 | 0 | 0 | 0.007760 |
| `sat_binary_cadical153` | SAT | 120 | 40 | 80 | 60 | 75.00% | 20 | 0 | 0 | 0.011180 |
| `sat_commander_cadical153` | SAT | 120 | 0 | 120 | 63 | 52.50% | 56 | 1 | 0 | 0.008905 |
| `sat_product_cadical153` | SAT | 120 | 0 | 120 | 64 | 53.33% | 56 | 0 | 0 | 0.009016 |
| `sat_sequential_glucose4` | SAT | 120 | 0 | 120 | 60 | 50.00% | 60 | 0 | 0 | 0.007728 |
| `sat_sequential_minisat22` | SAT | 120 | 0 | 120 | 60 | 50.00% | 60 | 0 | 0 | 0.006915 |
| `cpsat` (OR-Tools) | Non-SAT | 120 | 0 | 120 | 64 | 53.33% | 56 | 0 | 0 | 0.033353 |

*CSV Export: [`docs/results/table2_per_solver_breakdown.csv`](file:///home/guts/P2/SAT/Sudoku-SAT/docs/results/table2_per_solver_breakdown.csv)*

---

### Table 3. Difficulty Stratification ($N \times \text{removal\_ratio}$)

*Caption: Breakdown of solver performance across the six problem difficulty strata. Each stratum comprises 20 distinct Sudoku instances. Solve rates and timeout rates are computed over attempted runs.*

| Grid Size $N$ | Removal Ratio $r$ | Solver Group | Attempted Runs | Valid Solutions | Valid Solve Rate (%) | Timeouts | Resource Guard Live | Invalid Solutions | Predecl. Excl. | Median Valid Solve Time (s) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **9** | **0.5** | SAT | 140 | 140 | 100.00% | 0 | 0 | 0 | 0 | 0.008018 |
| **9** | **0.5** | Non-SAT (CP-SAT) | 20 | 20 | 100.00% | 0 | 0 | 0 | 0 | 0.003896 |
| **9** | **0.9** | SAT | 140 | 140 | 100.00% | 0 | 0 | 0 | 0 | 0.008288 |
| **9** | **0.9** | Non-SAT (CP-SAT) | 20 | 20 | 100.00% | 0 | 0 | 0 | 0 | 0.033160 |
| **36** | **0.5** | SAT | 140 | 13 | 9.29% | 127 | 0 | 0 | 0 | 6.981681 |
| **36** | **0.5** | Non-SAT (CP-SAT) | 20 | 4 | 20.00% | 16 | 0 | 0 | 0 | 7.008288 |
| **36** | **0.9** | SAT | 140 | 138 | 98.57% | 2 | 0 | 0 | 0 | 1.508942 |
| **36** | **0.9** | Non-SAT (CP-SAT) | 20 | 20 | 100.00% | 0 | 0 | 0 | 0 | 2.270578 |
| **81** | **0.5** | SAT | 100 | 0 | 0.00% | 99 | 1 | 0 | 40 | — |
| **81** | **0.5** | Non-SAT (CP-SAT) | 20 | 0 | 0.00% | 20 | 0 | 0 | 0 | — |
| **81** | **0.9** | SAT | 100 | 0 | 0.00% | 100 | 0 | 0 | 40 | — |
| **81** | **0.9** | Non-SAT (CP-SAT) | 20 | 0 | 0.00% | 20 | 0 | 0 | 0 | — |

*CSV Export: [`docs/results/table3_difficulty_stratification.csv`](file:///home/guts/P2/SAT/Sudoku-SAT/docs/results/table3_difficulty_stratification.csv)*

---

## 4. Empirical Findings & Analysis

### 4.1 Overall Solve Rates
- Over the full 120-puzzle dataset, the overall valid solve rates between SAT solvers (**56.71%**, 431/760) and Non-SAT CP-SAT (**53.33%**, 64/120) are remarkably comparable.
- When evaluating across all 120 puzzles without memory exclusions, `sat_product_cadical153` solved exactly **64 puzzles** (53.33%), matching Google OR-Tools CP-SAT's **64 puzzles** (53.33%). `sat_commander_cadical153` solved 63 puzzles (52.50%), and `sat_sequential_cadical153` solved 62 puzzles (51.67%).
- Solvers with quadratic memory overhead (`pairwise` and `binary`) achieved higher percentages on attempted runs (77.50% and 75.00%) only because they were prevented from attempting the unsolvable $N=81$ stratum by the memory guard.

### 4.2 Stratum Dynamics and Phase Transitions
1. **Standard $9 \times 9$ Instances ($N=9$)**:
   - Both SAT and CP-SAT achieved a **100.0% solve rate** on all 40 puzzles (160/160 runs for each removal ratio).
   - For $r=0.5$, CP-SAT had a slightly lower median solve time (0.0039 s) than SAT (0.0080 s), but for $r=0.9$, SAT solved significantly faster (median 0.0083 s vs. 0.0332 s for CP-SAT, a $\approx 4\times$ speed advantage).
2. **Medium $36 \times 36$ Instances ($N=36$)**:
   - **High Clue Removal ($r=0.9$, underconstrained)**: Both paradigms excelled. CP-SAT solved 100.0% (20/20) with median solve time 2.27 s. SAT solvers solved 98.57% (138/140), with 5 out of 7 SAT configurations solving 20/20 and an overall median solve time of **1.51 s** (faster than CP-SAT).
   - **Low Clue Removal ($r=0.5$, constrained)**: Represents a severe difficulty spike. CP-SAT solved 20.0% (4/20), while SAT solvers solved 9.29% (13/140). Most runs timed out (>10.0 s), with median valid solve times clustering tightly around 7.0 s for both paradigms.
3. **Large $81 \times 81$ Instances ($N=81$)**:
   - Neither SAT nor CP-SAT solved any instance within the 10.0-second limit (0.0% solve rate across 120 attempted SAT runs and 40 attempted CP-SAT runs).
   - This empirically confirms that $N=81$ Sudoku requires significantly greater runtime budgets or domain-specific decomposition techniques regardless of whether SAT or CP-SAT is utilized.

### 4.3 Constraint Encoding Impact on SAT Performance
- **Product Encoding** (`sat_product_cadical153`): Demonstrates the best overall balance between clause count ($O(N\sqrt{N})$) and propagation efficiency, achieving the highest total valid solves (64) among SAT solvers.
- **Commander Encoding** (`sat_commander_cadical153`): Close second with 63 valid solves, with 1 run safely aborted by live RAM guard at $N=81$.
- **Sequential Counter** (`sat_sequential_cadical153`): Consistent $O(N)$ auxiliary variable scaling, achieving 62 valid solves with CaDiCaL, and 60 valid solves each with Glucose 4 and MiniSat 2.2.
- **Pairwise & Binary**: While effective at $N \le 36$, they cannot scale to $N=81$ due to $O(N^4)$ clause explosion or large auxiliary trees.

### 4.4 Verification and Correctness
- All 495 returned solutions were strictly and independently verified by [`is_valid_solution_for_puzzle`](file:///home/guts/P2/SAT/Sudoku-SAT/src/sudoku/validator.py).
- Zero false positives, zero invalid solutions, and zero solver crashes occurred across all 960 evaluations.
