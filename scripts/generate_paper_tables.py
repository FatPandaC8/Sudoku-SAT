#!/usr/bin/env python3
"""Generate paper-ready tables and analysis for the scoped SAT vs. Non-SAT benchmark."""

import csv
import json
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = REPO_ROOT / "data" / "results" / "benchmark_sat_vs_nonsat.csv"
OUTPUT_DIR = REPO_ROOT / "docs" / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(INPUT_CSV)

# --- Table 1: Primary Comparison: SAT vs. Non-SAT ---
t1_rows = []
for group_name, mask in [
    ("SAT Solvers (PySAT)", df["solver"] == "sat"),
    ("Non-SAT Solvers (OR-Tools CP-SAT)", df["solver"] != "sat"),
]:
    sub = df[mask]
    n_configs = sub.groupby(["solver", "encoding", "backend"], dropna=False).ngroups
    n_recorded = len(sub)
    n_predecl = (sub["status"] == "BUILD_FAIL").sum()
    n_attempted = n_recorded - n_predecl
    n_valid = (sub["status"] == "SOLVED_VALID").sum()
    n_timeout = (sub["status"] == "TIMEOUT").sum()
    n_guard = (sub["status"] == "RESOURCE_GUARD_LIVE").sum()
    n_invalid = (sub["status"] == "INVALID_SOLUTION").sum()
    
    solve_rate = (n_valid / n_attempted * 100) if n_attempted > 0 else 0.0
    timeout_rate = (n_timeout / n_attempted * 100) if n_attempted > 0 else 0.0
    
    valid_times = sub[sub["status"] == "SOLVED_VALID"]["t_total"]
    med_time = valid_times.median()
    q25 = valid_times.quantile(0.25)
    q75 = valid_times.quantile(0.75)
    iqr = q75 - q25

    t1_rows.append({
        "Solver Group": group_name,
        "Configurations": n_configs,
        "Recorded Matrix Cells": n_recorded,
        "Predeclared Exclusions": n_predecl,
        "Attempted Runs": n_attempted,
        "Valid Solutions": n_valid,
        "Valid Solve Rate (%)": round(solve_rate, 2),
        "Timeouts": n_timeout,
        "Timeout Rate (% of attempted)": round(timeout_rate, 2),
        "Resource Guard Live Rejections": n_guard,
        "Invalid Solutions": n_invalid,
        "Median Solve Time (s)": round(med_time, 6),
        "Q25 (s)": round(q25, 6),
        "Q75 (s)": round(q75, 6),
        "IQR (s)": round(iqr, 6),
    })

t1_df = pd.DataFrame(t1_rows)
t1_df.to_csv(OUTPUT_DIR / "table1_sat_vs_nonsat_primary.csv", index=False)

# --- Table 2: Per-Solver Breakdown ---
configs = [
    ("sat_pairwise_cadical153", "SAT", "sat", "pairwise", "cadical153"),
    ("sat_sequential_cadical153", "SAT", "sat", "sequential", "cadical153"),
    ("sat_binary_cadical153", "SAT", "sat", "binary", "cadical153"),
    ("sat_commander_cadical153", "SAT", "sat", "commander", "cadical153"),
    ("sat_product_cadical153", "SAT", "sat", "product", "cadical153"),
    ("sat_sequential_glucose4", "SAT", "sat", "sequential", "glucose4"),
    ("sat_sequential_minisat22_extra_backend", "SAT", "sat", "sequential", "minisat22"),
    ("cpsat", "Non-SAT", "cpsat", None, "cpsat"),
]

t2_rows = []
for label, fam, s, enc, b in configs:
    if fam == "SAT":
        sub = df[(df["solver"] == s) & (df["encoding"] == enc) & (df["backend"] == b)]
    else:
        sub = df[df["solver"] == s]
    
    n_recorded = len(sub)
    n_predecl = (sub["status"] == "BUILD_FAIL").sum()
    n_att = n_recorded - n_predecl
    n_valid = (sub["status"] == "SOLVED_VALID").sum()
    n_to = (sub["status"] == "TIMEOUT").sum()
    n_guard = (sub["status"] == "RESOURCE_GUARD_LIVE").sum()
    n_inv = (sub["status"] == "INVALID_SOLUTION").sum()
    
    solve_rate = (n_valid / n_att * 100) if n_att > 0 else 0.0
    val_times = sub[sub["status"] == "SOLVED_VALID"]["t_total"]
    med_time = val_times.median() if len(val_times) else np.nan
    
    t2_rows.append({
        "Solver Configuration": label,
        "Family": fam,
        "Recorded Matrix Cells": n_recorded,
        "Predeclared Exclusions": n_predecl,
        "Attempted Runs": n_att,
        "Valid Solutions": n_valid,
        "Valid Solve Rate (%)": round(solve_rate, 2),
        "Timeouts": n_to,
        "Resource Guard Live": n_guard,
        "Invalid Solutions": n_inv,
        "Median Valid Solve Time (s)": round(med_time, 6) if pd.notna(med_time) else "-",
    })

t2_df = pd.DataFrame(t2_rows)
t2_df.to_csv(OUTPUT_DIR / "table2_per_solver_breakdown.csv", index=False)

# --- Table 3: Difficulty Stratification (N x removal_ratio) ---
t3_rows = []
for (N, ratio), sub in df.groupby(["N", "requested_ratio"]):
    for fam_label, fam_mask in [("SAT", sub["solver"] == "sat"), ("Non-SAT (CP-SAT)", sub["solver"] != "sat")]:
        f_sub = sub[fam_mask]
        n_predecl = (f_sub["status"] == "BUILD_FAIL").sum()
        att = f_sub[f_sub["status"] != "BUILD_FAIL"]
        n_att = len(att)
        n_valid = (att["status"] == "SOLVED_VALID").sum()
        n_to = (att["status"] == "TIMEOUT").sum()
        n_guard = (att["status"] == "RESOURCE_GUARD_LIVE").sum()
        n_inv = (att["status"] == "INVALID_SOLUTION").sum()
        
        solve_rate = (n_valid / n_att * 100) if n_att > 0 else 0.0
        val_times = att[att["status"] == "SOLVED_VALID"]["t_total"]
        med_time = val_times.median() if len(val_times) else np.nan
        
        t3_rows.append({
            "Grid Size N": N,
            "Removal Ratio": ratio,
            "Solver Group": fam_label,
            "Attempted Runs": n_att,
            "Valid Solutions": n_valid,
            "Valid Solve Rate (%)": round(solve_rate, 2),
            "Timeouts": n_to,
            "Resource Guard Live": n_guard,
            "Invalid Solutions": n_inv,
            "Predeclared Exclusions": n_predecl,
            "Median Valid Solve Time (s)": round(med_time, 6) if pd.notna(med_time) else "-",
        })

t3_df = pd.DataFrame(t3_rows)
t3_df.to_csv(OUTPUT_DIR / "table3_difficulty_stratification.csv", index=False)

print("Generated Table 1, Table 2, and Table 3 CSVs in", OUTPUT_DIR)
