# Dataset Audit: Sudoku Benchmark Puzzle Corpus

## Source of Truth

- `data/manifest.csv` — 120 puzzle entries
- `data/dataset_info.json` — Dataset metadata
- `data/puzzles/` — 6 JSONL files (20 puzzles each)
- `src/sudoku/generator.py` — Generator implementation (gen-v1)
- `src/sudoku/validator.py` — Validator implementation
- `docs/sudoku_benchmark_plan.md` — Original benchmark plan (Vietnamese)
- `docs/SETUP.md` — Dataset construction and correctness criteria

## Dataset Composition

| Attribute | Value | Source |
|-----------|-------|--------|
| Base seed | 42 | `data/dataset_info.json` |
| Generator version | gen-v1 | `data/dataset_info.json` |
| Total puzzles | 120 | manifest.csv (121 lines incl. header) |
| Puzzles per (N, ratio) pair | 20 | manifest.csv |
| Grid sizes N | {9, 36, 81} | manifest.csv |
| Box sizes | {3, 6, 9} | manifest.csv |
| Removal ratios | {0.5, 0.9} | manifest.csv |
| Total strata (N × r pairs) | 6 | manifest.csv |
| Puzzle IDs | `sudoku_N{N:03d}_r{ratio:.1f}_i{index:03d}` | generator.py:puzzle_id_for |

## Stratum Breakdown

| Stratum | N | Removal Ratio r | Puzzle IDs | Puzzles |
|---------|---|-----------------|------------|---------|
| 1 | 9 | 0.5 | sudoku_N009_r0.5_i000..i019 | 20 |
| 2 | 9 | 0.9 | sudoku_N009_r0.9_i000..i019 | 20 |
| 3 | 36 | 0.5 | sudoku_N036_r0.5_i000..i019 | 20 |
| 4 | 36 | 0.9 | sudoku_N036_r0.9_i000..i019 | 20 |
| 5 | 81 | 0.5 | sudoku_N081_r0.5_i000..i019 | 20 |
| 6 | 81 | 0.9 | sudoku_N081_r0.9_i000..i019 | 20 |

## Realized vs Requested Removal Ratios

| N | Requested r | Realized r | Clues | Empty Cells |
|---|-------------|------------|-------|-------------|
| 9 | 0.5 | 0.50617 | 40 | 41 |
| 9 | 0.9 | 0.90123 | 8 | 73 |
| 36 | 0.5 | 0.50000 | 648 | 648 |
| 36 | 0.9 | 0.89969 | 130 | 1166 |
| 81 | 0.5 | 0.50008 | 3280 | 3281 |
| 81 | 0.9 | 0.90002 | 656 | 5905 |

Note: Realized ratios deviate slightly from requested due to `round_half_up` and cell-count quantization.

## Puzzle Generation Algorithm

1. Construct base grid pattern: `(box * (r % box) + r // box + c) % N + 1`
2. Apply seeded validity-preserving transformations (row perm within band, col perm within stack, band/stack perm, optional transpose, digit relabeling)
3. Validate complete grid with `is_valid_complete_grid`
4. Remove cells: `n_remove = round_half_up(ratio * N²)`
5. Validate puzzle against reference solution with `is_valid_puzzle`

## Generator Limitations (from generator.py docstring)

- Does NOT sample uniformly from all valid Sudoku grids
- Samples from the automorphism equivalence orbit of the standard base pattern
- Generated puzzles are NOT guaranteed to possess unique solutions
- Any valid completion matching clues counts as correct
- Removal ratio is an experimental condition, not a difficulty label

## Dataset Provenance

- Puzzle files: `data/puzzles/N009_r0.5.jsonl` (20 lines), `data/puzzles/N009_r0.9.jsonl` (20 lines), etc.
- Each puzzle record contains: id, N, box, requested_ratio, realized_ratio, n_clues, n_empty, base_seed, seed, generator_version, puzzle, solution, content_sha256
- SHA-256 content hash computed via canonical JSON serialization
- Manifest SHA-256: `c6312d76c8c61c23a78f92e166a018c3a897e2476825e6d4db8280b459dc045a` (dataset_info.json)

## Known Limitations

1. **Small sample size**: Only 20 puzzles per stratum (120 total). Results may not generalize.
2. **Non-uniform grid sampling**: All grids come from the same automorphism orbit of the base pattern.
3. **Non-unique solutions**: Puzzles may admit multiple valid solutions; correctness is defined as any valid completion matching clues.
4. **Ratio ≠ difficulty**: Removal ratio is an experimental factor, not a difficulty label. The plan explicitly warns against interpreting r as difficulty.
5. **Only two ratios**: r ∈ {0.5, 0.9}; the plan originally proposed {0.3, 0.5, 0.7, 0.9} but actual data uses only {0.5, 0.9}.
6. **Single seed**: Base seed = 42 only. No replication across seeds.

## Evidence Files

- `data/manifest.csv` — Complete manifest with all 120 puzzle entries
- `data/dataset_info.json` — Dataset metadata summary
- `data/puzzles/N009_r0.5.jsonl` through `data/puzzles/N081_r0.9.jsonl` — Puzzle JSONL files
- `src/sudoku/generator.py` — Generator source code
- `src/sudoku/validator.py` — Validator source code
- `docs/sudoku_benchmark_plan.md` — Original benchmark plan (Section 1: Dataset)
