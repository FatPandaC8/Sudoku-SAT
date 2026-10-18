"""Custom backtracking solver: MRV, forward checking, optional AC-3.

Also provides a bounded solution counter (``count_solutions``) used by the
generator for uniqueness verification.  Boards are never assumed to be 9x9;
all structures are derived from ``board.size``.

AC-3 note: Sudoku's ``AllDifferent`` constraints are strictly stronger than
the conjunction of the binary inequality constraints between peers.  Enabling
AC-3 only enforces arc consistency on those binary inequalities; it is *not*
equivalent to generalized arc consistency on the ``AllDifferent`` constraints.
"""

from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass

from .puzzle import EMPTY, Board, SolverResult, validate_solution


@dataclass
class BacktrackStats:
    nodes: int = 0                # search nodes visited
    decisions: int = 0            # value assignments made in search
    backtracks: int = 0           # failed branches undone
    eliminations: int = 0         # candidate values removed
    propagation_steps: int = 0    # FC scans / AC-3 revise calls
    runtime: float = 0.0

    def as_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "decisions": self.decisions,
            "backtracks": self.backtracks,
            "eliminations": self.eliminations,
            "propagation_steps": self.propagation_steps,
            "runtime": self.runtime,
        }


class BacktrackingSolver:
    """MRV + forward checking solver with optional AC-3 propagation.

    Deterministic by default: candidates are tried in ascending order and MRV
    ties break on the lowest cell index (row-major).  ``randomize=True``
    shuffles both, which is used by the generator for varied solutions.
    """

    def __init__(
        self,
        board: Board,
        *,
        use_ac3: bool = False,
        randomize: bool = False,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> None:
        self.board = board
        self.n = board.size
        self.k = board.k
        self.use_ac3 = use_ac3
        self.rng = random.Random(seed) if randomize else None
        self.stats = BacktrackStats()
        self.timeout = timeout
        self._deadline: float | None = None
        n, k = self.n, self.k
        # Peer sets: cells sharing a row, column, or subgrid (excluding self).
        self.peers: list[set[int]] = [set() for _ in range(n * n)]
        for r in range(n):
            for c in range(n):
                i = r * n + c
                for j in range(n):
                    if j != c:
                        self.peers[i].add(r * n + j)
                    if j != r:
                        self.peers[i].add(j * n + c)
                br, bc = (r // k) * k, (c // k) * k
                for rr in range(br, br + k):
                    for cc in range(bc, bc + k):
                        if rr != r or cc != c:
                            self.peers[i].add(rr * n + cc)
        self._init_domains()
        self._found: list[list[int]] = []

    def _init_domains(self) -> None:
        n = self.n
        all_vals = set(range(1, n + 1))
        self.domains: list[set[int]] = [set(all_vals) for _ in range(n * n)]
        self.assigned: list[bool] = [False] * (n * n)
        for r in range(n):
            for c in range(n):
                v = self.board.at(r, c)
                if v != EMPTY:
                    i = r * n + c
                    self.domains[i] = {v}
                    self.assigned[i] = True

    # --- propagation -----------------------------------------------------

    def _remove(self, i: int, v: int, undo: list[tuple[int, int]]) -> bool:
        """Remove value ``v`` from domain of cell ``i``; False if it emptied."""
        dom = self.domains[i]
        if v in dom:
            dom.discard(v)
            undo.append((i, v))
            self.stats.eliminations += 1
            if not dom:
                return False
        return True

    def _forward_check(self, i: int, v: int, undo: list[tuple[int, int]]) -> bool:
        """Remove assigned value ``v`` from all peers of cell ``i``."""
        for p in self.peers[i]:
            self.stats.propagation_steps += 1
            if not self._remove(p, v, undo):
                return False
        return True

    def _ac3(self, seeds: list[tuple[int, int]], undo: list[tuple[int, int]]) -> bool:
        """Run AC-3 over the binary inequality constraints between peers.

        ``seeds`` are arcs (xi, xj) that may require revision.  A value ``a``
        of ``xi`` is removed iff ``xj``'s domain is the singleton ``{a}``.
        Returns False as soon as a domain becomes empty.
        """
        queue = deque(seeds)
        while queue:
            xi, xj = queue.popleft()
            self.stats.propagation_steps += 1
            dom_j = self.domains[xj]
            if len(dom_j) == 1:
                a = next(iter(dom_j))
                if a in self.domains[xi]:
                    if not self._remove(xi, a, undo):
                        return False
                    for xk in self.peers[xi]:
                        if xk != xj:
                            queue.append((xk, xi))
        return True

    def _propagate(self, i: int, v: int, undo: list[tuple[int, int]]) -> bool:
        """Forward checking after assigning ``v`` to cell ``i`` (+ optional AC-3)."""
        if not self._forward_check(i, v, undo):
            return False
        if self.use_ac3:
            # Every cell whose domain changed during this step: revise peers
            # with respect to it.  undo holds (cell, removed_value) pairs plus
            # the decision-cell entries; cell i itself changed to {v}.
            changed = {i}
            for cell, _val in undo:
                changed.add(cell)
            seeds = [(q, p) for p in changed for q in self.peers[p]]
            return self._ac3(seeds, undo)
        return True

    def _restore(self, undo: list[tuple[int, int]]) -> None:
        """Undo every recorded domain removal (reverse order is irrelevant
        because re-adding a value is order independent)."""
        for cell, val in undo:
            self.domains[cell].add(val)

    # --- search ----------------------------------------------------------

    def _select_cell(self) -> int:
        """MRV: unassigned cell with the fewest candidates (-1 if none).

        Ties break on the lowest cell index (row-major) unless randomized.
        A cell with an empty domain is returned immediately (contradiction).
        """
        best = -1
        best_len = self.n + 1
        cells = [i for i, a in enumerate(self.assigned) if not a]
        if self.rng is not None:
            self.rng.shuffle(cells)
        for i in cells:
            dl = len(self.domains[i])
            if dl < best_len:
                best, best_len = i, dl
                if dl <= 1:
                    break
        return best

    def _search(self, limit: int | None) -> bool:
        """Depth-first search.  Returns True when ``limit`` solutions found."""
        self.stats.nodes += 1
        if self._deadline is not None and time.perf_counter() >= self._deadline:
            return False  # timeout
        if limit is not None and len(self._found) >= limit:
            return True
        i = self._select_cell()
        if i < 0:
            # Every cell assigned: record the solution.
            vals = [0] * (self.n * self.n)
            for idx, dom in enumerate(self.domains):
                vals[idx] = next(iter(dom))
            self._found.append(vals)
            return limit is not None and len(self._found) >= limit
        candidates = sorted(self.domains[i])
        if not candidates:
            self.stats.backtracks += 1
            return False
        if self.rng is not None:
            self.rng.shuffle(candidates)
        full_domain = set(candidates)
        for v in candidates:
            undo: list[tuple[int, int]] = []
            self.stats.decisions += 1
            # Narrow the decision cell's domain to {v}, recording removals
            # so the uniform restore brings back every value.
            ok = True
            for w in full_domain:
                if w != v and not self._remove(i, w, undo):
                    ok = False
                    break
            if ok:
                ok = self._propagate(i, v, undo)
            if ok:
                self.assigned[i] = True
                stop = self._search(limit)
                self.assigned[i] = False
                self._restore(undo)
                if stop:
                    return True
                continue
            self._restore(undo)
            self.stats.backtracks += 1
        return False

    # --- public API ------------------------------------------------------

    def _initial_propagate(self) -> bool:
        """Forward-check from every given clue once, before searching.

        Detects contradictory givens (e.g. two identical clues sharing a
        peer set) without touching validation policy: such inputs simply have
        no completion.  Removals persist for the whole search.
        """
        for i in range(self.n * self.n):
            if self.assigned[i]:
                v = next(iter(self.domains[i]))
                for p in self.peers[i]:
                    self.stats.propagation_steps += 1
                    if not self._remove(p, v, []):
                        return False
        return True

    def _flat_to_board(self, flat: list[int]) -> Board:
        n = self.n
        return Board([flat[r * n : (r + 1) * n] for r in range(n)])

    def solve(self, timeout: float | None = None) -> SolverResult:
        """Find one solution (or prove none exists).

        If ``timeout`` is given (seconds), the search aborts once the
        deadline is reached and returns status ``"timeout"``.
        """
        t0 = time.perf_counter()
        self._found = []
        self._deadline = t0 + timeout if timeout is not None else None
        if not self._initial_propagate():
            self.stats.runtime = time.perf_counter() - t0
            return SolverResult(
                status="unsatisfiable",
                runtime=self.stats.runtime,
                stats=self.stats.as_dict(),
            )
        self._search(limit=1)
        self.stats.runtime = time.perf_counter() - t0
        if self._found:
            board = self._flat_to_board(self._found[0])
            return SolverResult(
                status="solved",
                board=board,
                runtime=self.stats.runtime,
                stats=self.stats.as_dict(),
            )
        if self._deadline is not None and time.perf_counter() >= self._deadline:
            return SolverResult(
                status="timeout",
                runtime=self.stats.runtime,
                stats=self.stats.as_dict(),
            )
        return SolverResult(
            status="unsatisfiable",
            runtime=self.stats.runtime,
            stats=self.stats.as_dict(),
        )

    def count_solutions(self, max_solutions: int = 2) -> int:
        """Count solutions up to ``max_solutions`` (early-stopping path).

        Used for uniqueness verification with ``max_solutions=2``: two
        solutions are enough to establish that a puzzle is not unique.
        """
        if max_solutions < 1:
            raise ValueError("max_solutions must be >= 1")
        self._found = []
        if not self._initial_propagate():
            return 0
        self._search(limit=max_solutions)
        return len(self._found)


def solve_backtracking(
    board: Board,
    *,
    use_ac3: bool = False,
    randomize: bool = False,
    seed: int | None = None,
    timeout: float | None = None,
) -> SolverResult:
    """Convenience wrapper: solve ``board`` with default configuration."""
    return BacktrackingSolver(
        board, use_ac3=use_ac3, randomize=randomize, seed=seed, timeout=timeout
    ).solve(timeout=timeout)


def count_solutions(
    board: Board, max_solutions: int = 2, *, use_ac3: bool = False
) -> int:
    """Count solutions of ``board`` up to ``max_solutions`` (0 if unsat)."""
    return BacktrackingSolver(board, use_ac3=use_ac3).count_solutions(
        max_solutions
    )


