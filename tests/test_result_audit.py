import pandas as pd
import pytest

CSV_PATH = "data/results/benchmark_sat_vs_nonsat.csv"

ALLOWED_STATUS = {"SOLVED_VALID", "TIMEOUT", "BUILD_FAIL", "RESOURCE_GUARD_LIVE", "INVALID_SOLUTION", "SOLVER_ERROR"}

def load_df():
    return pd.read_csv(CSV_PATH)

def test_no_duplicate_run_keys():
    df = load_df()
    assert df['run_key'].is_unique, "Duplicate run_key entries found"

def test_status_values_valid():
    df = load_df()
    unknown = set(df['status']) - ALLOWED_STATUS
    assert not unknown, f"Found unknown status values: {unknown}"

def test_n81_resource_guard_exclusions():
    df = load_df()
    # Pairwise and binary should be predeclared BUILD_FAIL for both ratios
    mask = (df['N'] == 81) & (df['solver'] == 'sat')
    pairwise = df[mask & (df['encoding'] == 'pairwise')]
    binary = df[mask & (df['encoding'] == 'binary')]
    assert all(pairwise['status'] == 'BUILD_FAIL'), "pairwise should be BUILD_FAIL for N=81"
    assert all(binary['status'] == 'BUILD_FAIL'), "binary should be BUILD_FAIL for N=81"
    # For r=0.5, commander has one RESOURCE_GUARD_LIVE
    commander = df[mask & (df['encoding'] == 'commander') & (df['requested_ratio'] == 0.5)]
    assert commander['status'].value_counts().get('RESOURCE_GUARD_LIVE', 0) == 1
    # Ensure attempted runs count matches total - predeclared for each ratio
    for ratio in [0.5, 0.9]:
        ratio_mask = mask & (df['requested_ratio'] == ratio)
        total = ratio_mask.sum()
        predeclared = (pairwise['requested_ratio'] == ratio).sum() + (binary['requested_ratio'] == ratio).sum()
        attempted = total - predeclared
        # 5 configurations (excluding pairwise & binary) * 20 puzzles = 100 attempted per ratio
        assert attempted == 100, f"Unexpected attempted count for N=81 r={ratio}: {attempted}"
