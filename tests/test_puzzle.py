"""Tests for the core board model: parsing, symbols, validation."""

import pytest

from sudoku_solver.puzzle import (
    Board,
    EMPTY,
    SolverResult,
    format_puzzle,
    is_valid_size,
    is_valid_solution,
    parse_puzzle,
    subgrid_dims,
    symbol_for,
    validate_partial,
    validate_solution,
    value_for,
)


# --- sizes -----------------------------------------------------------------

@pytest.mark.parametrize("n,ok", [
    (4, True), (9, True), (16, True), (25, True), (36, True),
    (2, False), (3, False), (8, False), (12, False), (0, False), (-9, False),
])
def test_is_valid_size(n, ok):
    assert is_valid_size(n) is ok


@pytest.mark.parametrize("n,k", [(4, 2), (9, 3), (16, 4), (25, 5), (36, 6)])
def test_subgrid_dims(n, k):
    assert subgrid_dims(n) == k


def test_subgrid_dims_rejects_invalid():
    with pytest.raises(ValueError):
        subgrid_dims(10)


# --- symbol conversion -----------------------------------------------------

def test_symbol_roundtrip():
    for v in range(1, 37):
        assert value_for(symbol_for(v)) == v


def test_symbols_above_9_use_letters():
    assert symbol_for(10) == "A"
    assert symbol_for(35) == "Z"
    assert value_for("A") == 10
    assert value_for("F") == 15  # 16x16 uses 1..9,A..F


def test_unknown_symbol_rejected():
    from sudoku_solver.puzzle import PuzzleError

    with pytest.raises(PuzzleError):
        value_for("_")


# --- parsing / formatting --------------------------------------------------

def test_parse_9x9():
    p = parse_puzzle(
        "53..7....\n6..195...\n.98....6.\n8...6...3\n4..8.3..1\n"
        "7...2...6\n.6....28.\n...419..5\n....8..79"
    )
    assert p.size == 9 and p.k == 3
    assert p.at(0, 0) == 5 and p.at(0, 2) == EMPTY
    assert p.clue_count() == 30


def test_parse_16x16_and_25x25():
    p16 = parse_puzzle("." * 256)
    assert p16.size == 16 and p16.k == 4
    p25 = parse_puzzle("." * 625)
    assert p25.size == 25 and p25.k == 5


def test_parse_accepts_zero_as_empty():
    p = parse_puzzle("1000\n0000\n0000\n0000")
    assert p.at(0, 0) == 1
    assert p.at(0, 1) == EMPTY


def test_parse_rejects_bad_shapes():
    from sudoku_solver.puzzle import PuzzleError

    with pytest.raises(PuzzleError):
        parse_puzzle("123")       # not a square count
    with pytest.raises(PuzzleError):
        parse_puzzle("")


def test_parse_rejects_out_of_range_values():
    from sudoku_solver.puzzle import PuzzleError

    with pytest.raises(PuzzleError):
        parse_puzzle("5" * 16)  # 5 > size 4


def test_format_roundtrip():
    p = parse_puzzle("53..7....\n" + "." * 72)
    assert parse_puzzle(format_puzzle(p)) == p


def test_format_roundtrip_16():
    p = parse_puzzle("." * 256)
    p.set(0, 0, 10)  # 'A'
    p.set(15, 15, 15)  # 'F'
    back = parse_puzzle(format_puzzle(p))
    assert back == p


# --- validation ------------------------------------------------------------

def test_valid_partial_accepted():
    p = parse_puzzle("53..7....\n" + "." * 72)
    assert validate_partial(p) == []


def test_duplicate_in_row_rejected():
    p = parse_puzzle("11.......\n" + "." * 72)
    problems = validate_partial(p)
    assert any("row" in msg for msg in problems)


def test_duplicate_in_column_rejected():
    cells = [["."] * 9 for _ in range(9)]
    cells[0][0] = "7"
    cells[5][0] = "7"
    p = parse_puzzle("\n".join("".join(r) for r in cells))
    problems = validate_partial(p)
    assert any("column" in msg for msg in problems)


def test_duplicate_in_subgrid_rejected():
    cells = [["."] * 9 for _ in range(9)]
    cells[0][0] = "4"
    cells[1][1] = "4"  # same 3x3 box, different row/col
    p = parse_puzzle("\n".join("".join(r) for r in cells))
    problems = validate_partial(p)
    assert any("subgrid" in msg for msg in problems)


def test_out_of_range_value_rejected():
    b = Board([[0] * 4 for _ in range(4)])
    b.set(0, 0, 9)
    assert any("out-of-range" in m for m in validate_partial(b))


def test_wrong_dimensions_rejected():
    b = Board([[1, 2], [3]])
    assert validate_partial(b)


def test_completed_solution_validation():
    sol = parse_puzzle(
        "534678912\n672195348\n198342567\n859761423\n426853791\n"
        "713924856\n961537284\n287419635\n345286179"
    )
    assert validate_solution(sol) == []


def test_incomplete_solution_rejected():
    p = parse_puzzle("53..7....\n" + "." * 72)
    assert any("empty" in m for m in validate_solution(p))


def test_givens_must_be_preserved():
    givens = parse_puzzle("53..7....\n" + "." * 72)
    # A *valid* complete Sudoku grid that differs from the givens at (0,0).
    wrong = parse_puzzle(
        "123456789\n456789123\n789123456\n234567891\n567891234\n"
        "891234567\n345678912\n678912345\n912345678"
    )
    assert validate_solution(wrong) == []  # itself is a valid grid
    problems = validate_solution(wrong, givens)
    assert any("given" in m for m in problems)


def test_is_valid_solution_bool_helper():
    givens = parse_puzzle("53..7....\n" + "." * 72)
    assert not is_valid_solution(givens)  # not complete
    sol = parse_puzzle(
        "534678912\n672195348\n198342567\n859761423\n426853791\n"
        "713924856\n961537284\n287419635\n345286179"
    )
    assert is_valid_solution(sol, givens)


# --- common solver result --------------------------------------------------

def test_solver_result_shape():
    r = SolverResult(status="timeout", runtime=1.0, error="took too long")
    assert r.solved is False
    r2 = SolverResult(status="solved", board=Board([[1]]))
    assert r2.solved is True
