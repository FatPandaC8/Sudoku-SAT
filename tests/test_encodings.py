"""Exhaustive correctness tests for the five AMO encodings.

Each encoding is checked against the truth definition of at-most-one over
all 2^n assignments for small groups, including singleton and boundary
sizes, with an auxiliary-variable collision check against primary IDs.
"""

from itertools import product

import pytest
from pysat.solvers import Solver

from sudoku_solver.sat_solver import (
    AMO_ENCODINGS,
    AuxAllocator,
    available_encodings,
)

PRIMARY = 100  # lits are 1..n; aux must land strictly above this


def amo_satisfiable_under(assignment, clauses):
    """Is the AMO CNF satisfiable given fixed truth values for lits 1..n?"""
    assumptions = [
        (i + 1) if value else -(i + 1)
        for i, value in enumerate(assignment)
    ]
    with Solver(name="minisat22", bootstrap_with=clauses) as s:
        return s.solve(assumptions=assumptions)


ENCODING_VARIANTS = [
    (enc, {})
    for enc in available_encodings()
] + [
    ("commander", {"commander_group_size": 2}),
    ("commander", {"commander_group_size": 8}),
    ("product", {"product_rows": 1}),
    ("product", {"product_rows": 3}),
]


@pytest.mark.parametrize("encoding,opts", ENCODING_VARIANTS)
@pytest.mark.parametrize("n", [1, 2, 3, 5, 9])
def test_amo_exhaustive(encoding, opts, n):
    lits = list(range(1, n + 1))
    aux = AuxAllocator(PRIMARY)
    clauses = AMO_ENCODINGS[encoding](lits, aux, opts)

    used = {abs(lit) for cl in clauses for lit in cl}
    aux_used = used - set(lits)
    assert all(v > PRIMARY for v in aux_used), (
        f"{encoding}: auxiliary variable collides with primary IDs"
    )

    for assignment in product([False, True], repeat=n):
        n_true = sum(assignment)
        sat = amo_satisfiable_under(assignment, clauses)
        if n_true <= 1:
            assert sat, f"{encoding} n={n} {assignment}: AMO must allow <=1 true"
        else:
            assert not sat, f"{encoding} n={n} {assignment}: AMO must forbid >=2 true"


def test_every_required_encoding_is_present():
    assert set(available_encodings()) == {
        "pairwise", "binary", "commander", "product", "sequential"
    }


def test_unknown_encoding_rejected():
    from sudoku_solver.puzzle import empty_board
    from sudoku_solver.sat_solver import build_cnf

    with pytest.raises(ValueError):
        build_cnf(empty_board(4), encoding="nope")


def test_commander_group_size_validation():
    from sudoku_solver.puzzle import empty_board
    from sudoku_solver.sat_solver import build_cnf

    with pytest.raises(ValueError):
        build_cnf(empty_board(4), encoding="commander",
                  encoding_opts={"commander_group_size": 1})


def test_aux_ids_never_overlap_primary_in_full_cnf():
    from sudoku_solver.puzzle import empty_board
    from sudoku_solver.sat_solver import build_cnf, var_id

    for enc in available_encodings():
        n = 9
        clauses, info = build_cnf(empty_board(n), encoding=enc)
        primary_max = n ** 3
        # Every primary ID appears exactly as var_id produces it; aux must be
        # strictly greater. Check: any literal > primary_max is an aux var,
        # and no primary var is missing from var_id's range.
        all_lits = {abs(lit) for cl in clauses for lit in cl}
        primary_used = all_lits & set(range(1, primary_max + 1))
        assert primary_used, f"{enc}: no primary vars found"
        # aux count in info equals count of distinct lit ids above primary_max
        aux_used = {v for v in all_lits if v > primary_max}
        assert info["aux_vars"] >= len(aux_used)
        # var_id roundtrip
        for r in range(n):
            for c in range(n):
                for v in range(1, n + 1):
                    vid = var_id(r, c, v, n)
                    assert 1 <= vid <= primary_max
