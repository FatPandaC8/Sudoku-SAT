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

## Quick Start

### Solve a Single Puzzle

```bash
# From a puzzle file
python scripts/solve.py data/puzzles/9x9/9x9_easy_000_seed9042.json \
    --solver sat --encoding pairwise --backend minisat22

# Inline puzzle text (9x9)
python scripts/solve.py --text "53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79" \
    --size 9 --solver backtracking

# JSON output for scripting
python scripts/solve.py data/puzzles/9x9/9x9_hard_000_seed9104.json --json
```

Solver options:
| Solver | `--solver` | Key Options |
|--------|------------|-------------|
| Backtracking | `backtracking` | `--ac3` for AC-3 preprocessing |
| CP-SAT | `cpsat` | (no extra options) |
| PySAT | `sat` | `--encoding` (pairwise, binary, commander, product, sequential), `--backend` (minisat22, glucose4, cadical153) |

### Run Benchmarks

```bash
# Full benchmark (configured in configs/benchmark.toml)
python scripts/run_benchmark.py --config configs/benchmark.toml

# Quick smoke test (1 puzzle per category, 10s timeout)
python scripts/run_benchmark.py --config configs/quick.toml
```

The benchmark:
1. Generates missing puzzle datasets (deterministic seeds)
2. Runs each solver configuration on each puzzle (with repetitions)
3. Stores results incrementally in `data/results/` (or `data/results_smoke/`)
4. Resumes automatically if interrupted — completed runs are skipped

### Generate Plots from Results

```bash
# All figures from a results directory
python scripts/plot_results.py --results data/results

# Filtered plots
python scripts/plot_results.py --results data/results --size 9 --difficulty hard --solver sat
```

Outputs to `<results>/figures/`:
- `runtime.png` — median runtime by config (log scale, failures annotated)
- `cactus.png` — cactus plot (instances solved vs. time)
- `solved_rate.png` — fraction solved within timeout
- `encoding_size.png` — CNF variables/clauses per AMO encoding
- `memory.png` — peak RSS by solver
- `search_effort.png` — SAT conflicts, backtracking nodes, CP-SAT branches

## Project Structure

```
.
├── configs/
│   ├── benchmark.toml    # Full benchmark configuration
│   └── quick.toml        # Smoke test configuration
├── data/
│   ├── puzzles/          # Generated puzzle datasets (9x9, 16x16)
│   └── results/          # Benchmark output (CSV + JSONL + figures)
├── scripts/
│   ├── run_benchmark.py  # Benchmark runner
│   ├── solve.py          # Single puzzle solver
│   ├── plot_results.py   # Plot generation from saved results
│   └── generate_puzzles.py
├── src/sudoku_solver/
│   ├── benchmark.py      # Core benchmark logic (run, store, plot)
│   ├── sat_solver.py     # PySAT wrapper with AMO encodings
│   ├── cpsat_solver.py   # OR-Tools CP-SAT wrapper
│   ├── backtracking.py   # Backtracking + AC-3 solver
│   ├── generator.py      # Puzzle generation
│   └── puzzle.py         # Board representation, validation
└── tests/
```

## Configuration

Edit `configs/benchmark.toml` to customize:

```toml
[benchmark]
sizes = [9, 16]                    # Board sizes (N = k^2)
difficulties = ["easy", "medium", "hard"]
puzzles_per_category = 3
timeout = 30.0                     # Per-run wall-clock limit (seconds)
repetitions = 1
puzzle_dir = "data/puzzles"
output_dir = "data/results"

solver_configs = [
    { solver = "backtracking" },
    { solver = "backtracking", use_ac3 = true },
    { solver = "cpsat" },
    { solver = "sat", encoding = "pairwise", backend = "minisat22" },
    { solver = "sat", encoding = "sequential", backend = "glucose4" },
    # ...
]
```

## Benchmark Results

### Smoke Test Results (Quick Config)

Run: `python scripts/run_benchmark.py --config configs/quick.toml`

| Puzzle | Solver | Status | Runtime (s) | Peak RSS (MB) |
|--------|--------|--------|-------------|---------------|
| 9x9_easy | backtracking | solved | 0.0009 | 20.9 |
| 9x9_easy | cpsat | solved | 0.0223 | 101.0 |
| 9x9_easy | sat/pairwise/minisat22 | solved | 0.0175 | 25.5 |
| 9x9_easy | sat/sequential/glucose4 | solved | 0.0147 | 25.7 |
| 9x9_hard | backtracking | solved | 0.0038 | 20.9 |
| 9x9_hard | cpsat | solved | 0.0173 | 101.2 |
| 9x9_hard | sat/pairwise/minisat22 | solved | 0.0159 | 25.6 |
| 9x9_hard | sat/sequential/glucose4 | solved | 0.0207 | 25.8 |

**Summary**: All 8 runs solved successfully. Backtracking is fastest on these small instances; CP-SAT uses more memory but solves instantly; SAT solvers show encoding-dependent performance.

### Full Benchmark

Run with `configs/benchmark.toml` for comprehensive comparison across:
- 9×9 and 16×16 boards
- Easy, medium, hard difficulties
- 3 puzzles per category
- 13 solver configurations (backtracking ±AC3, CP-SAT, 11 SAT variants)

Results are stored in `data/results/` with:
- `runs.csv` — flat summary for spreadsheets
- `runs.jsonl` — detailed records with solver stats
- `environment.json` — Python version, packages, hardware
- `config_used.json` — effective benchmark configuration
- `figures/` — generated plots

## Reproducibility

Each benchmark run records:
- Exact solver configuration (encoding, backend, options)
- Puzzle identity (size, difficulty, seed, clue count)
- Wall-clock runtime, peak RSS, solver-specific stats
- Software environment (Python, package versions, CPU, RAM)

Re-run with the same config to reproduce or extend results.

## Testing

```bash
pytest
```

## Phase 1 Fixed Benchmark Dataset

For the empirical comparison of SAT solving and exact methods, a fixed dataset of 1,200 instances is generated deterministically.

### Dataset Specifications
- **Sizes**: 9×9 (box 3×3), 36×36 (box 6×6), 81×81 (box 9×9)
- **Removal Ratios**: 0.3, 0.5, 0.7, 0.9 (experimental factors, NOT difficulty labels)
- **Instances**: 100 puzzles per (size, ratio) pair, 12 pairs, 1,200 total puzzles
- **Base Seed**: 42

### Derivation Formulas
- **Per-Puzzle Seed**:
  ```python
  seed_bytes = hashlib.sha256(f"{base_seed}|{N}|{ratio:.1f}|{index}".encode("utf-8")).digest()[:8]
  seed = int.from_bytes(seed_bytes, byteorder="big", signed=False)
  ```
- **Clue Removal Count**:
  ```python
  n_remove = math.floor(ratio * N**2 + 0.5)  # Round half-up
  ```
- **Content Hash (`content_sha256`)**:
  SHA-256 of canonical JSON serialization (sorted keys, no whitespace) of `{id, N, puzzle, solution}`.

### CLI Usage

```bash
# Generate complete dataset into data/puzzles/ and data/manifest.csv
python scripts/generate_dataset.py

# Force overwrite existing dataset
python scripts/generate_dataset.py --force

# Verify and validate stored dataset against specification
python scripts/validate_dataset.py
```

### Known Limitations
1. **Non-Uniform Grid Sampling**: Base completed grids are constructed using the diagonal permutation pattern `(box * (r % box) + r // box + c) % N + 1` followed by validity-preserving automorphism shuffles (row/column permutations within bands/stacks, band/stack permutations, transposition, and digit relabeling). This ensures fast, strictly valid grids for arbitrary $N=k^2$ up to $81\times 81$, but does not sample uniformly from the space of all valid Sudoku grids.
2. **Non-Unique Solutions**: Puzzles are not guaranteed to admit a unique solution. Any valid completion matching the puzzle's clues is accepted as a correct solver solution.
3. **Removal Ratio as Factor**: The removal ratio is an experimental condition factor, not a difficulty label.