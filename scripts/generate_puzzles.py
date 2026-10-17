#!/usr/bin/env python3
"""Generate puzzle datasets (idempotent: skips puzzles that already exist).

Usage:
    python scripts/generate_puzzles.py --sizes 9 16 --difficulties easy hard \\
        --count 3 --out data/puzzles --seed 42 --timeout 120
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sudoku_solver.generator import (  # noqa: E402
    GenerationError,
    generate,
    load_dataset,
    save_puzzle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[9, 16, 25])
    parser.add_argument(
        "--difficulties", nargs="+", default=["easy", "medium", "hard"]
    )
    parser.add_argument("--count", type=int, default=3,
                        help="puzzles per (size, difficulty) category")
    parser.add_argument("--out", default="data/puzzles")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout", type=float, default=120.0,
                        help="generation budget per puzzle (seconds)")
    args = parser.parse_args()

    saved = failures = skipped = 0
    for size in args.sizes:
        for difficulty in args.difficulties:
            existing = len(list(load_dataset(args.out, size=size,
                                             difficulty=difficulty)))
            for idx in range(existing, args.count):
                seed = args.seed + size * 1000 + idx * 7 + {"easy": 0,
                                                            "medium": 31,
                                                            "hard": 62}.get(difficulty, 99)
                try:
                    gen = generate(
                        size=size, difficulty=difficulty, seed=seed,
                        timeout=args.timeout,
                    )
                except GenerationError as exc:
                    failures += 1
                    print(f"FAIL {size}x{size} {difficulty} seed={seed}: {exc}")
                    continue
                path = save_puzzle(args.out, size, difficulty, idx, gen)
                meta = gen.metadata
                print(
                    f"saved {Path(path).name}: clues={meta['clue_count']}"
                    f"/target={meta['target_clues']}"
                    f" reached={meta['target_reached']}"
                    f" score={meta['difficulty_score']}"
                    f" time={meta['generation_time']:.1f}s"
                )
                saved += 1
            skipped += min(existing, args.count)

    print(
        f"done: {saved} generated, {failures} failed, "
        f"{skipped} already present"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
