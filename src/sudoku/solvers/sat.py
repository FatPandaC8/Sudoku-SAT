"""SAT solver adapter and CNF generator with five At-Most-One (AMO) encodings.

Model:
- Primary Boolean variables: x[r, c, v] = true iff cell (r, c) contains digit v (1..N).
  Mapped to 1-based index: r * N^2 + c * N + v. Range: 1..N^3.
- Auxiliary variables for AMO allocated strictly above N^3 without collision.
- Exactly-one constraints: 4*N^2 groups (cell, row-value, col-value, box-value).
  Each group contains one At-Least-One (ALO) clause and one AMO encoding.
- Clues encoded as positive unit clauses.

Five AMO Encodings:
1. pairwise: all pairs (-a, -b). 0 aux, O(N^2) clauses.
2. sequential: Sinz (2005) sequential counter. O(N) aux, O(N) clauses.
3. binary: bitwise indicator encoding. O(log N) aux, O(N log N) clauses.
4. commander: Klieber & Kwon (2007) hierarchical group encoding.
5. product: Chen (2010) 2D row/column grid indicator encoding.
"""

from __future__ import annotations

import math
import time
from typing import Any, Callable, Sequence

from pysat.solvers import Solver

from ..validator import is_valid_solution_for_puzzle
from .base import (
    STATUS_BUILD_FAIL,
    STATUS_INVALID_SOLUTION,
    STATUS_SOLVED_VALID,
    STATUS_SOLVER_ERROR,
    STATUS_UNSAT_INVESTIGATE,
    SolverResult,
)


class AuxAllocator:
    """Hands out unique auxiliary variable IDs strictly above the primary variable range."""

    def __init__(self, primary_max: int) -> None:
        self.primary_max = primary_max
        self._next = primary_max + 1

    def alloc(self, count: int = 1) -> int | list[int]:
        if count == 1:
            vid = self._next
            self._next += 1
            return vid
        vids = list(range(self._next, self._next + count))
        self._next += count
        return vids

    @property
    def next_id(self) -> int:
        return self._next

    @property
    def aux_count(self) -> int:
        return self._next - self.primary_max - 1


# --- AMO Encodings ------------------------------------------------------------

def amo_pairwise(lits: Sequence[int], aux: AuxAllocator, opts: dict | None = None) -> list[list[int]]:
    """Pairwise (naive) AMO: forbids every pair of distinct literals."""
    return [[-a, -b] for i, a in enumerate(lits) for b in lits[i + 1 :]]


def amo_sequential(lits: Sequence[int], aux: AuxAllocator, opts: dict | None = None) -> list[list[int]]:
    """Sequential counter AMO (Sinz 2005).

    Prefix variables s[1..n-1] record whether a literal in the prefix is true.
    """
    n = len(lits)
    if n <= 1:
        return []
    allocated = aux.alloc(n - 1)
    s = [allocated] if isinstance(allocated, int) else allocated
    clauses = [[-lits[0], s[0]]]
    for i in range(1, n - 1):
        clauses.append([-lits[i], s[i]])
        clauses.append([-s[i - 1], s[i]])
    for i in range(1, n):
        clauses.append([-lits[i], -s[i - 1]])
    return clauses


def amo_binary(lits: Sequence[int], aux: AuxAllocator, opts: dict | None = None) -> list[list[int]]:
    """Binary/bitwise AMO (Frisch et al.).

    Each literal forces a distinct binary bit pattern on log2(n) auxiliary variables.
    """
    n = len(lits)
    if n <= 1:
        return []
    bits = math.ceil(math.log2(n))
    y = [aux.alloc(1) for _ in range(bits)]
    clauses: list[list[int]] = []
    for idx, lit in enumerate(lits):
        for b in range(bits):
            if (idx >> b) & 1:
                clauses.append([-lit, y[b]])
            else:
                clauses.append([-lit, -y[b]])
    return clauses


def amo_commander(lits: Sequence[int], aux: AuxAllocator, opts: dict | None = None) -> list[list[int]]:
    """Commander AMO (Klieber & Kwon 2007).

    Partitions literals into subgroups with commander variables.
    """
    opts = opts or {}
    b = int(opts.get("commander_group_size", 4))
    n = len(lits)
    if n <= 1:
        return []
    if b < 2:
        raise ValueError("commander_group_size must be >= 2")

    groups = [lits[i : i + b] for i in range(0, n, b)]
    commanders = [aux.alloc(1) for _ in groups]
    clauses: list[list[int]] = []

    # At most one commander true
    clauses += [[-a, -c] for i, c in enumerate(commanders) for a in commanders[i + 1 :]]

    for c, g in zip(commanders, groups):
        # Member true => its commander true
        clauses += [[-lit, c] for lit in g]
        # At most one member inside subgroup
        clauses += [[-a, -bb] for i, a in enumerate(g) for bb in g[i + 1 :]]

    return clauses


def amo_product(lits: Sequence[int], aux: AuxAllocator, opts: dict | None = None) -> list[list[int]]:
    """Product AMO (Chen 2010).

    Arranges literals in a 2D grid with row and column indicators.
    """
    opts = opts or {}
    n = len(lits)
    if n <= 1:
        return []
    rows_opt = opts.get("product_rows")
    if rows_opt:
        rows = max(1, min(int(rows_opt), n))
    else:
        rows = max(1, math.ceil(math.sqrt(n)))
    cols = math.ceil(n / rows)

    row_vars = [aux.alloc(1) for _ in range(rows)]
    col_vars = [aux.alloc(1) for _ in range(cols)]
    clauses: list[list[int]] = []

    for idx, lit in enumerate(lits):
        r, c = divmod(idx, cols)
        clauses.append([-lit, row_vars[r]])
        clauses.append([-lit, col_vars[c]])

    # AMO on row and column indicator variables
    clauses += [[-a, -b] for i, a in enumerate(row_vars) for b in row_vars[i + 1 :]]
    clauses += [[-a, -b] for i, a in enumerate(col_vars) for b in col_vars[i + 1 :]]

    return clauses


AMO_ENCODINGS: dict[str, Callable[[Sequence[int], AuxAllocator, dict | None], list[list[int]]]] = {
    "pairwise": amo_pairwise,
    "sequential": amo_sequential,
    "binary": amo_binary,
    "commander": amo_commander,
    "product": amo_product,
}


def var_id(r: int, c: int, v: int, n: int) -> int:
    """Map cell (r, c) having digit v (1..n) to 1-based variable index."""
    return r * n * n + c * n + v


def estimate_encoding_aux_vars(N: int, encoding: str, opts: dict | None = None) -> int:
    """Calculate the exact AMO auxiliary variable count for a Sudoku CNF."""
    groups = 4 * N * N
    if encoding == "pairwise":
        aux_per_group = 0
    elif encoding == "sequential":
        aux_per_group = max(0, N - 1)
    elif encoding == "binary":
        aux_per_group = math.ceil(math.log2(N)) if N > 1 else 0
    elif encoding == "commander":
        b = int((opts or {}).get("commander_group_size", 4))
        if b < 2:
            raise ValueError("commander_group_size must be >= 2")
        aux_per_group = math.ceil(N / b) if N > 1 else 0
    elif encoding == "product":
        rows = max(1, math.ceil(math.sqrt(N))) if N > 1 else 0
        cols = math.ceil(N / rows) if rows else 0
        aux_per_group = rows + cols
    else:
        raise ValueError(f"Unknown AMO encoding {encoding!r}; choose from {sorted(AMO_ENCODINGS)}")
    return groups * aux_per_group


def estimate_encoding_clauses(
    N: int,
    encoding: str,
    opts: dict | None = None,
    clues: int = 0,
) -> int:
    """Calculate exact total clause count (ALO + AMO + clue units)."""
    groups = 4 * N * N
    if encoding == "pairwise":
        amo_per_group = N * (N - 1) // 2
    elif encoding == "sequential":
        amo_per_group = max(0, 3 * N - 4)
    elif encoding == "binary":
        amo_per_group = N * math.ceil(math.log2(N)) if N > 1 else 0
    elif encoding == "commander":
        b = int((opts or {}).get("commander_group_size", 4))
        if b < 2:
            raise ValueError("commander_group_size must be >= 2")
        group_sizes = [min(b, N - i) for i in range(0, N, b)]
        commanders = len(group_sizes)
        amo_per_group = (
            N + sum(size * (size - 1) // 2 for size in group_sizes)
            + commanders * (commanders - 1) // 2
        ) if N > 1 else 0
    elif encoding == "product":
        rows = max(1, math.ceil(math.sqrt(N)))
        cols = math.ceil(N / rows)
        amo_per_group = (
            2 * N + rows * (rows - 1) // 2 + cols * (cols - 1) // 2
        ) if N > 1 else 0
    else:
        raise ValueError(f"Unknown AMO encoding {encoding!r}; choose from {sorted(AMO_ENCODINGS)}")
    return groups * (1 + amo_per_group) + clues


def count_sudoku_cnf(
    N: int,
    encoding: str,
    opts: dict | None = None,
    clues: int = 0,
) -> tuple[int, int]:
    """Count variables and clauses from one generated constraint group without retaining a CNF."""
    if encoding not in AMO_ENCODINGS:
        raise ValueError(f"Unknown AMO encoding {encoding!r}; choose from {sorted(AMO_ENCODINGS)}")
    aux = AuxAllocator(0)
    group_clauses = AMO_ENCODINGS[encoding](list(range(1, N + 1)), aux, opts)
    groups = 4 * N * N
    return (
        aux.aux_count * groups,
        groups * (1 + len(group_clauses)) + clues,
    )


def build_sudoku_cnf(
    puzzle: Sequence[int],
    N: int,
    encoding: str = "pairwise",
    opts: dict | None = None,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Build CNF clauses and model information for flat-list puzzle representation."""
    if encoding not in AMO_ENCODINGS:
        raise ValueError(f"Unknown AMO encoding {encoding!r}; choose from {sorted(AMO_ENCODINGS)}")

    t0 = time.perf_counter()
    box = math.isqrt(N)
    primary = N ** 3
    aux = AuxAllocator(primary)
    amo_fn = AMO_ENCODINGS[encoding]

    clauses: list[list[int]] = []
    groups = 0

    def add_exactly_one(lits: list[int]) -> None:
        nonlocal groups
        groups += 1
        clauses.append(lits)
        clauses.extend(amo_fn(lits, aux, opts))

    # 1. Cell groups: each cell has exactly one value
    for r in range(N):
        for c in range(N):
            add_exactly_one([var_id(r, c, v, N) for v in range(1, N + 1)])

    # 2. Row groups: each digit occurs once per row
    for r in range(N):
        for v in range(1, N + 1):
            add_exactly_one([var_id(r, c, v, N) for c in range(N)])

    # 3. Col groups: each digit occurs once per column
    for c in range(N):
        for v in range(1, N + 1):
            add_exactly_one([var_id(r, c, v, N) for r in range(N)])

    # 4. Box groups: each digit occurs once per box
    for br in range(box):
        for bc in range(box):
            for v in range(1, N + 1):
                add_exactly_one(
                    [
                        var_id(br * box + r, bc * box + c, v, N)
                        for r in range(box)
                        for c in range(box)
                    ]
                )

    # 5. Clues as unit clauses
    n_clues = 0
    for i, val in enumerate(puzzle):
        if val != 0:
            r = i // N
            c = i % N
            clauses.append([var_id(r, c, val, N)])
            n_clues += 1

    build_time = time.perf_counter() - t0
    info = {
        "encoding": encoding,
        "primary_vars": primary,
        "aux_vars": aux.aux_count,
        "total_vars": primary + aux.aux_count,
        "clauses": len(clauses),
        "groups": groups,
        "clues": n_clues,
        "t_build": build_time,
    }
    return clauses, info


def solve_sat(
    puzzle: Sequence[int],
    N: int,
    encoding: str = "pairwise",
    backend: str = "minisat22",
    timeout: float | None = None,
    opts: dict | None = None,
) -> SolverResult:
    """Solve puzzle using PySAT with the chosen AMO encoding and solver backend."""
    t_start = time.perf_counter()

    # Step 1: Model Build
    try:
        clauses, info = build_sudoku_cnf(puzzle, N, encoding=encoding, opts=opts)
    except Exception as e:
        return SolverResult(
            status=STATUS_BUILD_FAIL,
            t_build=0.0,
            t_solve=0.0,
            t_total=time.perf_counter() - t_start,
            error=f"Model build failed: {e}",
            stats={"encoding": encoding, "backend": backend},
        )

    t_build = info["t_build"]

    # Step 2: Solve
    t_solve_start = time.perf_counter()
    try:
        with Solver(name=backend, bootstrap_with=clauses) as solver:
            # Note: PySAT solve() does not directly take a wall-clock timeout in seconds
            # without asynchronous timer interruptions. Subprocess runner enforces hard timeout.
            is_sat = solver.solve()
            t_solve = time.perf_counter() - t_solve_start

            stats: dict[str, Any] = {
                "backend": backend,
                "encoding": encoding,
                "primary_vars": info["primary_vars"],
                "aux_vars": info["aux_vars"],
                "total_vars": info["total_vars"],
                "clauses": info["clauses"],
                "clues": info["clues"],
            }
            # PySAT stats inspection where available
            try:
                raw_stats = solver.accum_stats()
                if raw_stats:
                    stats["conflicts"] = getattr(raw_stats, "conflicts", None)
                    stats["decisions"] = getattr(raw_stats, "decisions", None)
                    stats["propagations"] = getattr(raw_stats, "propagations", None)
            except Exception:
                pass

            if not is_sat:
                # Sudoku puzzles from valid reference solutions must always be SAT!
                return SolverResult(
                    status=STATUS_UNSAT_INVESTIGATE,
                    solution=None,
                    t_build=t_build,
                    t_solve=t_solve,
                    t_total=time.perf_counter() - t_start,
                    stats=stats,
                    error="Solver reported UNSAT on a puzzle generated from a valid solution",
                )

            model = solver.get_model()
            if not model:
                return SolverResult(
                    status=STATUS_SOLVER_ERROR,
                    t_build=t_build,
                    t_solve=t_solve,
                    t_total=time.perf_counter() - t_start,
                    stats=stats,
                    error="Solver returned SAT but empty model",
                )

    except Exception as e:
        return SolverResult(
            status=STATUS_SOLVER_ERROR,
            t_build=t_build,
            t_solve=time.perf_counter() - t_solve_start,
            t_total=time.perf_counter() - t_start,
            error=f"Solver backend '{backend}' error: {e}",
            stats={"encoding": encoding, "backend": backend},
        )

    # Step 3: Extract Solution
    true_lits = {l for l in model if l > 0}
    candidate = [0] * (N * N)
    for r in range(N):
        for c in range(N):
            vals = [v for v in range(1, N + 1) if var_id(r, c, v, N) in true_lits]
            if len(vals) == 1:
                candidate[r * N + c] = vals[0]
            else:
                return SolverResult(
                    status=STATUS_INVALID_SOLUTION,
                    solution=None,
                    t_build=t_build,
                    t_solve=t_solve,
                    t_total=time.perf_counter() - t_start,
                    stats=stats,
                    error=f"Cell ({r},{c}) decoded {len(vals)} values: {vals}",
                )

    # Step 4: Independent Validation
    val_res = is_valid_solution_for_puzzle(puzzle, candidate, N)
    t_total = time.perf_counter() - t_start
    if not val_res.ok:
        return SolverResult(
            status=STATUS_INVALID_SOLUTION,
            solution=candidate,
            t_build=t_build,
            t_solve=t_solve,
            t_total=t_total,
            stats=stats,
            error=f"Validation failed: {val_res.reason} ({val_res.message})",
        )

    return SolverResult(
        status=STATUS_SOLVED_VALID,
        solution=candidate,
        t_build=t_build,
        t_solve=t_solve,
        t_total=t_total,
        stats=stats,
    )
