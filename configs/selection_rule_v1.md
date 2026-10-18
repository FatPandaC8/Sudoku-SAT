# Selection Rule v1 (pre-declared, pre-run)

## Purpose

Choose the single representative SAT configuration for the SAT vs non-SAT
comparison. This rule is frozen before the full_v1 run and uses ONLY the
`selection` split (puzzle indices 0-9). The `evaluation` split (indices 10-19)
is reported for all SAT configurations; the representative configuration is only
highlighted there.

## Inputs

- Results file: `data/results/full_v1.jsonl` (and `full_v1.csv`).
- Scope for selection: solver family `sat`, `experiment == "primary"`,
  `split == "selection"`, sizes N=36 and N=81, all five CaDiCaL153 AMO
  encodings (pairwise, sequential, binary, commander with b=4, product) plus the
  Sequential backends Glucose4 and MiniSat22 (extra backend).
- Non-SAT configurations (CP-SAT, Gurobi, CPLEX MIP, CPLEX CP) are NOT part of
  the SAT representative selection; they form the non-SAT side of the comparison
  and are all reported on both splits.

## Selection rule (computed after the run, never before)

1. Consider only `selection` runs (indices 0-9) at N=36 and N=81.
2. For each SAT configuration, count solved runs (`status == SOLVED_VALID`) over
   those N=36 and N=81 selection instances (max 20 instances per configuration:
   10 at N=36 + 10 at N=81).
3. The representative configuration is the one with the HIGHEST solved count.
4. Tie-break: among configurations tied on solved count, pick the one with the
   LOWER median `t_total` over the instances commonly solved by all tied
   configurations at those sizes (intersection of their solved instance sets).
5. Fallback: if NO SAT configuration solves anything at N=81 in the selection
   split, restrict the comparison to N=36 selection runs only (highest solved
   count, same tie-break) and state this fallback explicitly in the selection
   record.
6. If still tied after the tie-break, pick the configuration that is first in
   matrix order (configs/full_matrix_v1.csv row order) and state the tie in the
   record.

## Output

A selection record is written to `data/results/full_v1_selection.json`
containing: representative configuration, solved count at N=36/N=81,
tie-break applied (yes/no + metric), fallback used (yes/no), per-configuration
selection solved counts and medians, and a pointer to `full_v1.jsonl`.

All SAT configurations remain fully reported on the `evaluation` split; the
representative configuration receives no special treatment there beyond being
highlighted as the chosen SAT counterpart in the SAT vs non-SAT comparison.
