"""SAT encoding of Sudoku with five interchangeable AMO encodings.

Variable mapping (primary): ``x[r, c, v]`` = "row r, column c has value v",
mapped to ``r*N^2 + c*N + v + 1`` (1-based, reversible).  Primary variables
occupy ``1..N^3``; auxiliary variables for AMO encodings are allocated above
that range and never collide.

Exactly-one constraints are an at-least-one clause plus one AMO encoding.
There are ``4*N^2`` exactly-one groups: one per cell, and one per
(row, value), (column, value), (subgrid, value) pair.  Givens are unit clauses.
"""

from __future__ import annotations

import math
import time
from typing import Callable

from .puzzle import EMPTY, Board, SolverResult, validate_solution


class AuxAllocator:
    """Hands out auxiliary variable IDs strictly above the primary range."""

    def __init__(self, primary_max: int) -> None:
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


# --- AMO encodings ---------------------------------------------------------
# Signature: (literals, allocator, options) -> clauses enforcing at-most-one.

def amo_pairwise(lits, aux: AuxAllocator, opts: dict) -> list[list[int]]:
    return [[-a, -b] for i, a in enumerate(lits) for b in lits[i + 1 :]]


def amo_binary(lits, aux: AuxAllocator, opts: dict) -> list[list[int]]:
    """Log encoding: each selected literal forces a distinct binary code.

    Unused codes (when len(lits) is not a power of two) are harmless for
    at-most-one: with no literal true they are never reached, and two
    distinct used codes always differ in some bit, contradiction included.
    """
    n = len(lits)
    if n <= 1:
        return []
    bits = math.ceil(math.log2(n))
    y = [aux.alloc(1) for _ in range(bits)]  # normalize: alloc(1) returns int
    clauses = []
    for idx, lit in enumerate(lits):
        for b in range(bits):
            if (idx >> b) & 1:
                clauses.append([-lit, y[b]])
            else:
                clauses.append([-lit, -y[b]])
    return clauses


def amo_commander(lits, aux: AuxAllocator, opts: dict) -> list[list[int]]:
    """Commander encoding: partition into groups with commander variables.

    ``opts['commander_group_size']`` (default 4) bounds subgroup size.
    Subgroups use pairwise AMO (small); commanders are AMO'd pairwise
    (there are only ceil(n/b) of them).
    """
    b = int(opts.get("commander_group_size", 4))
    n = len(lits)
    if n <= 1:
        return []
    if b < 2:
        raise ValueError("commander_group_size must be >= 2")
    groups = [lits[i : i + b] for i in range(0, n, b)]
    commanders = [aux.alloc(1) for _ in groups]
    clauses: list[list[int]] = []
    # At most one commander true (few of them: pairwise).
    clauses += [[-a, -c] for i, c in enumerate(commanders) for a in commanders[i + 1 :]]
    for c, g in zip(commanders, groups):
        # Member true => its commander true.
        clauses += [[-lit, c] for lit in g]
        # At most one member inside the subgroup.
        clauses += [[-a, -bb] for i, a in enumerate(g) for bb in g[i + 1 :]]
    return clauses


def amo_product(lits, aux: AuxAllocator, opts: dict) -> list[list[int]]:
    """Product encoding: 2-D arrangement with row and column indicators.

    Literal i sits at grid position (i // cols, i % cols).  Any two distinct
    positions differ in row or column, so AMO over row indicators plus AMO
    over column indicators forbids two true literals.  ``opts['product_rows']``
    fixes the row count when given (cols = ceil(n / rows)); otherwise a
    near-square split is used.  Non-divisible sizes leave trailing cells empty.
    """
    n = len(lits)
    if n <= 1:
        return []
    rows_opt = opts.get("product_rows")
    if rows_opt:
        rows = max(1, min(int(rows_opt), n))
    else:
        rows = max(1, math.ceil(math.sqrt(n)))
    cols = math.ceil(n / rows)
    row_var = [aux.alloc(1) for _ in range(rows)]
    col_var = [aux.alloc(1) for _ in range(cols)]
    clauses: list[list[int]] = []
    for idx, lit in enumerate(lits):
        r, c = divmod(idx, cols)
        clauses.append([-lit, row_var[r]])
        clauses.append([-lit, col_var[c]])
    clauses += [[-a, -b] for i, a in enumerate(row_var) for b in row_var[i + 1 :]]
    clauses += [[-a, -b] for i, a in enumerate(col_var) for b in col_var[i + 1 :]]
    return clauses


def amo_sequential(lits, aux: AuxAllocator, opts: dict) -> list[list[int]]:
    """Sequential counter AMO (linear size).

    ``s_i`` := "some literal among lits[0..i] is true" for i = 1..n-1
    (``s_1`` is the literal ``lits[0]`` itself, so no variable is needed).
    Two true literals are forbidden by (not lits[i] or not s_{i-1}).
    """
    n = len(lits)
    if n <= 1:
        return []
    # s[0] is lits[0] itself (no variable needed); s[i] for i in 1..n-2 are
    # auxiliary prefix variables.  Forbid clauses use s[0..n-2] only.
    s: list[int] = [lits[0]]
    clauses: list[list[int]] = []
    for i in range(1, n - 1):
        si = aux.alloc(1)
        clauses.append([-s[i - 1], si])          # prefix true => s_i
        clauses.append([-lits[i], si])           # lits[i] true => s_i
        clauses.append([-si, s[i - 1], lits[i]]) # s_i => prefix or current
        s.append(si)
    # Forbid every literal together with a true prefix before it.
    for i in range(1, n):
        clauses.append([-lits[i], -s[i - 1]])
    return clauses


AMO_ENCODINGS: dict[str, Callable[[list, AuxAllocator, dict], list[list[int]]]] = {
    "pairwise": amo_pairwise,
    "binary": amo_binary,
    "commander": amo_commander,
    "product": amo_product,
    "sequential": amo_sequential,
}


def available_encodings() -> list[str]:
    return sorted(AMO_ENCODINGS)


def var_id(r: int, c: int, v: int, n: int) -> int:
    """Primary variable x[r, c, v]; v is 1-based, ids start at 1."""
    return r * n * n + c * n + v


def build_cnf(
    board: Board,
    encoding: str = "pairwise",
    encoding_opts: dict | None = None,
) -> tuple[list[list[int]], dict]:
    """Build the Sudoku CNF formula.

    Returns ``(clauses, info)`` where ``info`` records primary/auxiliary
    variable counts, clause count, and the number of exactly-one groups.
    """
    if encoding not in AMO_ENCODINGS:
        raise ValueError(
            f"unknown AMO encoding {encoding!r}; choose from {available_encodings()}"
        )
    opts = encoding_opts or {}
    n = board.size
    k = board.k
    t0 = time.perf_counter()

    primary = n ** 3
    aux = AuxAllocator(primary)
    amo = AMO_ENCODINGS[encoding]
    clauses: list[list[int]] = []
    groups = 0

    def exactly_one(lits: list[int]) -> None:
        nonlocal groups
        groups += 1
        clauses.append(list(lits))            # at least one
        clauses.extend(amo(lits, aux, opts))  # at most one

    # 1. Every cell contains exactly one value.
    for r in range(n):
        for c in range(n):
            exactly_one([var_id(r, c, v, n) for v in range(1, n + 1)])

    # 2. Every value occurs exactly once in each row.
    for r in range(n):
        for v in range(1, n + 1):
            exactly_one([var_id(r, c, v, n) for c in range(n)])

    # 3. Every value occurs exactly once in each column.
    for c in range(n):
        for v in range(1, n + 1):
            exactly_one([var_id(r, c, v, n) for r in range(n)])

    # 4. Every value occurs exactly once in each subgrid.
    for br in range(0, n, k):
        for bc in range(0, n, k):
            for v in range(1, n + 1):
                exactly_one(
                    [
                        var_id(r, c, v, n)
                        for r in range(br, br + k)
                        for c in range(bc, bc + k)
                    ]
                )

    # 5. Givens as unit clauses.
    givens = 0
    for r in range(n):
        for c in range(n):
            v = board.at(r, c)
            if v != EMPTY:
                clauses.append([var_id(r, c, v, n)])
                givens += 1

    total_vars = aux.next_id - 1
    info = {
        "encoding": encoding,
        "primary_vars": primary,
        "aux_vars": total_vars - primary,
        "total_vars": total_vars,
        "clauses": len(clauses),
        "groups": groups,
        "givens": givens,
        "build_time": time.perf_counter() - t0,
    }
    for key, val in opts.items():
        info[f"opt_{key}"] = val
    return clauses, info


def available_backends() -> list[str]:
    """Return installed-and-working PySAT solver backends (probed at runtime)."""
    from pysat.solvers import Solver

    candidates = [
        "minisat22", "m22", "glucose3", "g3", "glucose4", "g4", "glucose42",
        "cadical103", "cadical153", "cadical195", "maplesat", "lingeling",
        "maplechrono", "maplecm", "mergesat3", "minicadical1",
    ]
    found: list[str] = []
    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        try:
            s = Solver(name=name, bootstrap_with=[[1], [-1, 2]])
            s.delete()
            found.append(name)
        except Exception:
            continue
    return found


def extract_board(model: list[int], n: int) -> Board | None:
    """Recover a board from a satisfying assignment; None if incomplete."""
    true_set = {l for l in model if l > 0}
    cells = [[EMPTY] * n for _ in range(n)]
    for r in range(n):
        for c in range(n):
            chosen = [v for v in range(1, n + 1) if var_id(r, c, v, n) in true_set]
            if len(chosen) != 1:
                return None
            cells[r][c] = chosen[0]
    return Board(cells)


def _givens_assumptions(board: Board) -> list[int]:
    """Assumption literals encoding the current givens of ``board``.

    A given ``v`` at (r,c) becomes the unit assumption ``x[r,c,v]``.  Removing
    a clue means omitting its assumption; the base CNF (exactly-one groups)
    stays fixed, so the counter can be reused across clue removals without
    rebuilding the formula.
    """
    n = board.size
    out: list[int] = []
    for r in range(n):
        for c in range(n):
            v = board.at(r, c)
            if v != EMPTY:
                out.append(var_id(r, c, v, n))
    return out


def _blocking_clause(board: Board, solution: Board) -> list[int]:
    """Clause forbidding ``solution``: at least one non-given cell differs.

    A solution is ruled out iff it agrees with ``solution`` on every non-given
    cell (givens are fixed by assumptions).  The clause
    ``OR_{non-given (r,c)} NOT x[r,c,solution_value]`` is satisfied exactly when
    some non-given cell takes a value other than ``solution``'s, so adding it
    permanently blocks ``solution``.  Given cells are skipped: their value is
    forced by the given assumptions, so including ``NOT x[r,c,v]`` there would
    contradict the assumptions and make the clause useless.
    """
    n = board.size
    clause: list[int] = []
    for r in range(n):
        for c in range(n):
            if board.at(r, c) != EMPTY:
                continue  # given: forced by assumptions, skip
            v = solution.at(r, c)
            if v == EMPTY:
                continue
            clause.append(-var_id(r, c, v, n))
    return clause


class SatCounter:
    """Reusable solution counter over a *mutating* puzzle board.

    The base CNF (all exactly-one groups over an empty board) is built once.
    The current givens are supplied as assumptions on every ``count`` call, so
    removing/restoring clues never requires rebuilding the formula.  Found
    solutions are blocked with permanent clauses (a disjunction "some
    non-given cell differs"), which is safe across clue removals: a solution
    blocked while a cell was a given stays blocked after that clue is removed,
    because the blocked solution still agrees with itself on every cell the
    clause constrains.

    The caller must call :meth:`delete` when finished to release the solver.
    """

    def __init__(
        self,
        size: int,
        *,
        encoding: str = "pairwise",
        backend: str = "minisat22",
        encoding_opts: dict | None = None,
    ) -> None:
        from pysat.solvers import Solver

        self.size = size
        self.backend = backend
        empty = Board([[EMPTY] * size for _ in range(size)])
        self.clauses, self.info = build_cnf(empty, encoding, encoding_opts)
        self._solver = Solver(name=backend, bootstrap_with=self.clauses)
        self._deleted = False

    def count(self, board: Board, max_solutions: int = 2) -> int:
        """Count solutions of the *current* ``board`` up to ``max_solutions``.

        ``board`` may be mutated between calls; only its givens matter.
        """
        if self._deleted:
            raise RuntimeError("counter was deleted")
        if max_solutions < 1:
            raise ValueError("max_solutions must be >= 1")
        if board.size != self.size:
            raise ValueError("board size does not match counter size")
        assumptions = _givens_assumptions(board)
        found = 0
        while found < max_solutions:
            if not self._solver.solve(assumptions=assumptions):
                break
            model = self._solver.get_model()
            sol_board = extract_board(model, self.size)
            if sol_board is None:
                break
            found += 1
            if found >= max_solutions:
                break
            self._solver.add_clause(_blocking_clause(board, sol_board))
        return found

    def delete(self) -> None:
        if not self._deleted:
            self._solver.delete()
            self._deleted = True


def count_solutions_sat(
    board: Board,
    max_solutions: int = 2,
    *,
    encoding: str = "pairwise",
    backend: str = "minisat22",
    encoding_opts: dict | None = None,
) -> int:
    """Count solutions of ``board`` up to ``max_solutions`` via PySAT.

    Convenience wrapper around :class:`SatCounter` for a single call.
    """
    counter = SatCounter(board.size, encoding=encoding, backend=backend,
                         encoding_opts=encoding_opts)
    try:
        return counter.count(board, max_solutions)
    finally:
        counter.delete()


def extract_model_board(model: list[int], n: int) -> Board | None:
    """Recover a board from a raw PySAT model (alias of extract_board)."""
    return extract_board(model, n)


def solve_sat(
    board: Board,
    encoding: str = "pairwise",
    backend: str = "minisat22",
    encoding_opts: dict | None = None,
) -> SolverResult:
    """Solve ``board`` with PySAT.

    Formula construction time and solving time are recorded separately so
    encoding overhead stays visible in benchmark results.  The returned
    solution is validated against the original givens before being reported
    as ``solved``.
    """
    from pysat.solvers import Solver

    t_total = time.perf_counter()
    try:
        clauses, info = build_cnf(board, encoding, encoding_opts)
    except Exception as exc:
        return SolverResult(status="error", error=f"CNF build failed: {exc}")

    t_load0 = time.perf_counter()
    try:
        with Solver(name=backend, bootstrap_with=clauses) as sat:
            load_time = time.perf_counter() - t_load0
            t_solve = time.perf_counter()
            sat_status = sat.solve()
            solve_time = time.perf_counter() - t_solve
            acc = sat.accum_stats() or {}
            stats = {
                **info,
                "backend": backend,
                "load_time": load_time,
                "solve_time": solve_time,
                "conflicts": acc.get("conflicts", 0),
                "propagations": acc.get("propagations", 0),
                "sat_decisions": acc.get("decisions", 0),
                "restarts": acc.get("restarts", 0),
            }
            stats["runtime"] = time.perf_counter() - t_total
            if not sat_status:
                return SolverResult(
                    status="unsatisfiable",
                    runtime=stats["runtime"],
                    stats=stats,
                )
            result_board = extract_board(sat.get_model(), board.size)
            if result_board is None:
                return SolverResult(
                    status="error",
                    runtime=stats["runtime"],
                    stats=stats,
                    error="model does not determine a complete board",
                )
            problems = validate_solution(result_board, board)
            if problems:
                return SolverResult(
                    status="error",
                    runtime=stats["runtime"],
                    stats=stats,
                    error=f"solver returned an invalid solution: {problems}",
                )
            return SolverResult(
                status="solved",
                board=result_board,
                runtime=stats["runtime"],
                stats=stats,
            )
    except Exception as exc:
        return SolverResult(
            status="error",
            runtime=time.perf_counter() - t_total,
            stats={**info, "backend": backend},
            error=f"solver execution failed: {exc}",
        )


