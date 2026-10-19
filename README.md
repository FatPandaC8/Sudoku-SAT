# Sudoku-SAT

Sudoku solving and benchmarking framework comparing multiple solver approaches:

- **Backtracking** with optional AC-3 preprocessing
- **OR-Tools CP-SAT** (constraint programming)
- **PySAT** with multiple AMO (At-Most-One) encodings and SAT backends

## Features

- Multiple solver families with configurable strategies
- Reproducible benchmark runner (resumable, subprocess-isolated)
- Automatic puzzle generation with difficulty control
- Results stored as CSV + JSONL for analysis
- Plotting utilities for runtime, cactus plots, solved rates, encoding size, memory, and search effort

## Installation

```bash
pip install -e ".[dev]"
```

Requires Python 3.11+. Dependencies:
- `python-sat` — SAT solvers (MiniSat, Glucose, CaDiCaL)
- `ortools` — CP-SAT solver
- `matplotlib` — plotting
- `psutil` — peak memory measurement

### Solve a Single Puzzle

```bash
# From a puzzle file (N=9, ratio 0.5, index 0)
python scripts/solve.py data/puzzles/N009_r0.5.jsonl \
    --line 1 --solver sat --encoding sequential --backend minisat22

# Inline puzzle text (9x9)
python scripts/solve.py --text "53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79" \
    --size 9 --solver backtracking

# JSON output for scripting
python scripts/solve.py data/puzzles/N009_r0.5.jsonl --line 1 --json
```

Solver options:
| Solver | `--solver` | Key Options |
|--------|------------|-------------|
| Backtracking | `backtracking` | (MRV + forward checking, AC-3 disabled) |
| CP-SAT | `cpsat` | (no extra options) |
| PySAT | `sat` | `--encoding` (pairwise, binary, commander, product, sequential), `--backend` (minisat22, glucose4, cadical153) |

### Run Benchmarks

The paper's primary benchmark compares 7 SAT configurations and OR-Tools CP-SAT on the fixed 120-puzzle dataset (`N ∈ {9, 36, 81}`, `r ∈ {0.5, 0.9}`, 20 puzzles per stratum, seed 42). Classical backtracking is benchmarked separately.

```bash
# SAT vs. CP-SAT benchmark on all 120 puzzles (10s timeout, resumable)
python scripts/run_benchmark_120.py

# Classical backtracking benchmark on all 120 puzzles (10s timeout)
python scripts/run_backtracking_benchmark.py

# Preliminary sampled run (1 puzzle per cell, ~5 min hard budget)
python scripts/run_full_v1.py
```

Results are stored incrementally in `data/results/`:
- `benchmark_sat_vs_nonsat.csv` — primary SAT + CP-SAT results (960 runs)
- `backtracking_results.csv` — backtracking results (120 runs)
- `full_v1.jsonl` — preliminary sampled run (stopped early; see `full_v1_stop.json`)
- `full_v1_run_info.json` — preliminary run metadata

Re-running skips existing records, so interrupted runs resume without duplicates.

### Generate Plots from Results

```bash
# All figures from a results directory
python scripts/plot_results.py --results data/results
```

## Project Structure

```
.
├── configs/
│   ├── dataset.yaml        # Fixed dataset config (sizes [9,36,81], ratios [0.5,0.9], 20/pair)
│   ├── benchmark.toml      # Legacy full benchmark config (9×9/16×16, 30s timeout — not used for paper)
│   ├── quick.toml          # Legacy smoke test config
│   ├── pilot_v2.toml       # Pilot v2 settings (timeout 10s, 1 worker, 1 thread)
│   ├── matrix_sat_vs_nonsat.csv  # Benchmark matrix: 7 SAT + CP-SAT configs × 120 puzzles
│   └── full_matrix_v1.csv  # Backtracking matrix (6 cells × 20 puzzles)
├── data/
│   ├── puzzles/            # 6 JSONL files, 120 puzzles (N009_r0.5, N009_r0.9, N036_r0.5, N036_r0.9, N081_r0.5, N081_r0.9)
│   ├── manifest.csv        # 120 puzzle manifest with IDs, seeds, ratios, content hashes
│   ├── dataset_info.json   # Dataset metadata (seed 42, gen-v1, 20/pair, 6 pairs, 120 total)
│   ├── results/            # Benchmark output
│   │   ├── benchmark_sat_vs_nonsat.csv   # Primary SAT + CP-SAT results (960 runs)
│   │   ├── backtracking_results.csv      # Backtracking results (120 runs)
│   │   ├── full_v1.jsonl                 # Preliminary sampled run (stopped early)
│   │   ├── full_v1.csv                   # Preliminary run CSV copy
│   │   ├── full_v1_run_info.json         # Preliminary run metadata
│   │   ├── full_v1_stop.json             # Early-stop metadata
│   │   └── archive_v1/                   # Archived 1,200-puzzle dataset and pilot results
│   └── archive_v2_pair50/    # Archived 20-puzzle dataset (pre-reduce to 1 per cell)
├── scripts/
│   ├── run_benchmark_120.py    # SAT vs. CP-SAT benchmark on all 120 puzzles
│   ├── run_backtracking_benchmark.py  # Backtracking benchmark on all 120 puzzles
│   ├── run_full_v1.py          # Preliminary sampled full_v1 runner
│   ├── solve.py                # Single puzzle solver
│   ├── generate_dataset.py     # Dataset generator (deterministic, seed 42)
│   ├── validate_dataset.py     # Dataset validator
│   ├── calibrate_memory.py     # Memory calibration for resource guard
│   ├── generate_puzzles.py     # Puzzle generation (legacy)
│   ├── generate_paper_tables.py  # Paper table generation from raw results
│   ├── plot_results.py         # Plot generation from saved results
│   ├── run_pilot.py            # Pilot runner
│   └── summarize_pilot.py      # Pilot summary
├── src/sudoku/
│   ├── bench/runner.py     # Benchmark runner (subprocess, timeout, resource guard, validation)
│   ├── dataset.py          # Dataset loading and filtering
│   ├── generator.py        # Puzzle generation (gen-v1)
│   ├── solver...           # (see solvers/)
│   ├── solver...           # (see solvers/)
│   ├── solver...           # (see solvers/)
│   ├── solver...           # (see solvers/)
│   ├── validator.py        # Independent solution validator
│   └── ...
├── src/sudoku_solver/
│   ├── backtracking.py     # Classical backtracking (MRV + forward checking, AC-3 disabled)
│   └── puzzle.py           # Board model and validation
├── tests/
│   └── test_*.py           # Test suite (pytest)
├── docs/
│   ├── SETUP.md            # Dataset construction and correctness criteria
│   ├── sudoku_benchmark_plan.md  # Historical planning document (Vietnamese; superseded by paper)
│   ├── results/benchmark_report.md  # Generated benchmark report matching the paper
│   └── paper_prep/         # Manuscript evidence audit, gaps, table audits
└── paper/main.tex          # Authoritative research paper (cas-sc)
```

## Configuration

Dataset configuration (`configs/dataset.yaml`) defines the fixed benchmark scope:

```yaml
sizes: [9, 36, 81]
ratios: [0.5, 0.9]
puzzles_per_pair: 20
base_seed: 42
generator_version: "gen-v1"
```

This produces 6 strata × 20 puzzles = 120 puzzles total. Removal ratio is an experimental factor, not a difficulty label. Puzzle seeds are derived deterministically from SHA-256 of `"42|N|ratio|index"`.

The legacy `configs/benchmark.toml` (9×9/16×16, 30s timeout) and `configs/quick.toml` are retained for reference but were not used for the paper's results.

## Benchmark Results

The paper's results are derived from two raw result files:

| File | Runs | Description |
|------|------|-------------|
| `data/results/benchmark_sat_vs_nonsat.csv` | 960 | SAT (7 configs) + CP-SAT on all 120 puzzles |
| `data/results/backtracking_results.csv` | 120 | Classical backtracking on all 120 puzzles |

### Aggregate results (from the paper, `paper/main.tex`)

| Metric | SAT (7 configs) | CP-SAT (1 config) | Backtracking (1 config) |
|--------|-----------------|-------------------|-------------------------|
| Recorded matrix cells | 840 | 120 | 120 |
| Predeclared exclusions | 80 | 0 | 0 |
| Attempted runs | 760 | 120 | 120 |
| Valid solutions | 431 | 64 | 40 |
| Valid solve rate (%) | 56.71 | 53.33 | 33.33 |
| Timeouts | 328 | 56 | 80 |
| Timeout rate (%) | 43.16 | 46.67 | 66.67 |
| Live resource-guard rejections | 1 | 0 | 0 |
| Invalid solutions | 0 | 0 | 0 |

Predeclared exclusions: SAT pairwise and binary encodings at N=81 (40 each, 80 total) are excluded by the 60% available-RAM memory guard and not executed. One live resource-guard rejection occurred (commander at N=81, r=0.5).

All 535 valid solutions (431 + 64 + 40) passed independent verification via `is_valid_solution_for_puzzle`; zero invalid solutions were recorded. Both SAT and CP-SAT achieve 100% solve rates on N=9 instances; all families fall below 21% at N=36, r=0.5; no family solves any N=81 instance within the 10-second timeout.

See `paper/main.tex` for the full results, stratified tables, and discussion.

## Dataset

The fixed benchmark dataset comprises 120 puzzles generated deterministically from base seed 42:

| Property | Value |
|----------|-------|
| Grid sizes | 9×9 (box 3×3), 36×36 (box 6×6), 81×81 (box 9×9) |
| Removal ratios | 0.5, 0.9 (experimental factors, not difficulty labels) |
| Puzzles per stratum | 20 |
| Total puzzles | 120 (6 strata × 20) |
| Base seed | 42 |
| Generator version | gen-v1 |

Files:
- `data/manifest.csv` — 120-row manifest (ID, N, box, ratios, clues, seed, content hash, file, line)
- `data/puzzles/N0{9,36,81}_r{0.5,0.9}.jsonl` — 6 JSONL files, 20 puzzles each
- `data/dataset_info.json` — dataset metadata

### Generation

```bash
# Generate the complete dataset
python scripts/generate_dataset.py

# Force overwrite existing dataset
python scripts/generate_dataset.py --force

# Verify dataset integrity
python scripts/validate_dataset.py
```

### Known Limitations

1. **Non-uniform grid sampling**: Base grids are constructed from a diagonal permutation pattern followed by validity-preserving automorphisms. This does not sample uniformly from all valid Sudoku grids.
2. **Non-unique solutions**: Puzzles are not guaranteed to admit a unique solution; any valid completion matching the clues counts as correct.
3. **Removal ratio as factor**: The removal ratio is an experimental condition, not a difficulty label.
4. **Single seed**: All puzzles derive from base seed 42; results may not generalize to other seeds.

## Reproducibility

The paper (`paper/main.tex`) is the authoritative description of the completed experiment. Each benchmark run records:
- Exact solver configuration (encoding, backend, options)
- Puzzle identity (size, ratio, index)
- Wall-clock runtime, peak RSS, solver-specific stats
- Software environment (Python version)

Known reproducibility gaps:
- No environment lock file (`environment_lock_present=false`); hardware specs (CPU, RAM, OS) not recorded
- Exact solver version pins not recorded beyond backend names
- Single run per instance per configuration; no confidence intervals or hypothesis tests

## Testing

```bash
pytest
```

## Archive

Previous dataset versions and pilot results are preserved under `data/archive_v1/` (1,200-puzzle dataset) and `data/archive_v2_pair50/` (20-puzzle dataset). These are historical and not part of the paper's results.