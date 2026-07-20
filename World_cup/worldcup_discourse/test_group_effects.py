"""
test_group_effects.py
=====================
Statistical tests for flag-rate differences across match-outcome groups and
across source / subreddit groups.

Reads
-----
reports/analysis/match_table.csv
    Produced by build_match_table.py.  Requires the manually-filled columns
    ``outcome`` and ``nation`` to be non-empty before any test is run.

Writes
------
reports/analysis/group_effects_test.txt
    Plain-text report with test statistics, p-values, and cell-count warnings.

Test selection
--------------
* Chi-square (scipy.stats.chi2_contingency) is used when every expected cell
  count in the contingency table is >= 5.
* Fisher's exact test (scipy.stats.fisher_exact, 2x2 only) is used when any
  expected cell count is < 5 and the table is 2x2.
* For tables larger than 2x2 with small expected counts the script runs
  chi-square anyway but flags every cell whose expected count is < 5 with a
  warning so the reader knows the p-value may not be reliable.
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE  = SCRIPT_DIR / "reports" / "analysis" / "match_table.csv"
OUTPUT_DIR  = SCRIPT_DIR / "reports" / "analysis"
OUTPUT_FILE = OUTPUT_DIR / "group_effects_test.txt"

# Flag-rate columns that exist in match_table.csv
FLAG_COLUMNS = [
    "flag_abusive_or_hard_language",
    "flag_negative_match_tone",
    "flag_identity_targeted_context",
    "flag_racism_or_discrimination_discussion",
    "flag_severe_identity_slur",
]

# Minimum expected count per cell; below this the test result is unreliable
MIN_EXPECTED = 5

# ---------------------------------------------------------------------------
# Dependency check - scipy may not be installed in all venvs
# ---------------------------------------------------------------------------
try:
    from scipy.stats import chi2_contingency, fisher_exact
except ImportError:
    print(
        "ERROR: scipy is required but not installed.\n"
        "Install it with:  pip install scipy\n"
        "or, if using the project venv:  venv\\Scripts\\pip install scipy"
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_csv(path: Path) -> list:
    """Return a list of row dicts from a CSV file; skip completely blank rows."""
    with open(path, newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh) if any(row.values())]


def int_or_zero(value) -> int:
    """Parse an integer from a string; return 0 on failure."""
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return 0


def total_flags(row: dict) -> int:
    """Sum all flag columns for one row."""
    return sum(int_or_zero(row.get(col, 0)) for col in FLAG_COLUMNS)


def expected_counts(observed):
    """Compute expected cell counts for a contingency table."""
    import numpy as np
    obs = np.array(observed, dtype=float)
    row_sums = obs.sum(axis=1, keepdims=True)
    col_sums = obs.sum(axis=0, keepdims=True)
    grand = obs.sum()
    if grand == 0:
        return (obs * 0).tolist()
    return (row_sums * col_sums / grand).tolist()


def small_cell_warnings(exp, row_labels, col_labels):
    """Return a list of warning strings for cells with expected count < MIN_EXPECTED."""
    warnings = []
    for i, row_lbl in enumerate(row_labels):
        for j, col_lbl in enumerate(col_labels):
            if exp[i][j] < MIN_EXPECTED:
                warnings.append(
                    "  [!] Cell [{} x {}] expected={:.2f} < {}".format(
                        row_lbl, col_lbl, exp[i][j], MIN_EXPECTED
                    )
                )
    return warnings


def run_test(contingency, row_label="group", col_label="flagged / not-flagged"):
    """
    Run the appropriate test on a contingency table.

    Parameters
    ----------
    contingency : {group_label: {"flagged": n, "not_flagged": m}}
    row_label   : human-readable name for the row grouping variable
    col_label   : human-readable name for the column variable

    Returns
    -------
    dict with keys: test_name, statistic, p_value, dof, warnings, table_str
    """
    import numpy as np

    groups = sorted(contingency.keys())
    observed = [
        [contingency[g]["flagged"], contingency[g]["not_flagged"]]
        for g in groups
    ]
    col_labels = ["flagged", "not_flagged"]

    exp = expected_counts(observed)
    warnings = small_cell_warnings(exp, groups, col_labels)

    n_rows = len(observed)
    is_2x2 = n_rows == 2
    any_small = any(
        exp[i][j] < MIN_EXPECTED for i in range(n_rows) for j in range(2)
    )

    if is_2x2 and any_small:
        test_name = "Fisher's exact"
        table_2x2 = [[observed[0][0], observed[0][1]],
                     [observed[1][0], observed[1][1]]]
        stat, p = fisher_exact(table_2x2)
        dof = None
    else:
        test_name = "Chi-square"
        obs_arr = np.array(observed, dtype=float)
        stat, p, dof, _ = chi2_contingency(obs_arr)

    # Build a plain-text table string
    col_w = max(len(g) for g in groups + [row_label])
    header = "  {:<{}}  {:>10}  {:>12}  {:>8}".format(
        "Group", col_w, "Flagged", "Not flagged", "Total"
    )
    divider = "  " + "-" * (col_w + 36)
    rows_txt = []
    for i, g in enumerate(groups):
        f  = observed[i][0]
        nf = observed[i][1]
        rows_txt.append(
            "  {:<{}}  {:>10}  {:>12}  {:>8}".format(g, col_w, f, nf, f + nf)
        )

    table_str = "\n".join([header, divider] + rows_txt)

    return {
        "test_name": test_name,
        "statistic": stat,
        "p_value":   p,
        "dof":       dof,
        "warnings":  warnings,
        "table_str": table_str,
    }


def format_result(title, result):
    """Return a formatted block of text for one test result."""
    lines = [
        "=" * 70,
        "  {}".format(title),
        "=" * 70,
        "",
        "  Contingency table:",
        result["table_str"],
        "",
    ]

    test = result["test_name"]
    stat = result["statistic"]
    p    = result["p_value"]
    dof  = result["dof"]

    if dof is not None:
        lines.append("  Test       : {}  (df={})".format(test, dof))
    else:
        lines.append("  Test       : {}".format(test))

    lines.append("  Statistic  : {:.4f}".format(stat))
    lines.append("  p-value    : {:.4g}".format(p))

    sig = "Yes (p < 0.05)" if p < 0.05 else "No  (p >= 0.05)"
    lines.append("  Significant: {}".format(sig))

    if result["warnings"]:
        lines.append("")
        lines.append(
            "  Small-cell warnings (expected count < 5 -> treat p-value with caution):"
        )
        lines.extend(result["warnings"])

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Guard: check that outcome and nation are populated
# ---------------------------------------------------------------------------

def check_required_columns(rows):
    """
    Exit early if any row is missing a non-blank ``outcome`` or ``nation``
    value.  Prints a descriptive message identifying the offending rows.
    """
    missing_outcome = [r["match_id"] for r in rows
                       if not r.get("outcome", "").strip()]
    missing_nation  = [r["match_id"] for r in rows
                       if not r.get("nation",  "").strip()]

    if missing_outcome or missing_nation:
        print("=" * 70)
        print("  PRE-FLIGHT CHECK FAILED -- statistical tests not run")
        print("=" * 70)
        print()
        print("  The 'outcome' and/or 'nation' columns in match_table.csv are")
        print("  blank for one or more rows.  Fill them in manually (they are")
        print("  intentionally left empty by build_match_table.py) and re-run.")
        print()
        if missing_outcome:
            print("  Missing 'outcome' ({} rows):".format(len(missing_outcome)))
            for mid in missing_outcome:
                print("    * {}".format(mid))
        if missing_nation:
            print("  Missing 'nation' ({} rows):".format(len(missing_nation)))
            for mid in missing_nation:
                print("    * {}".format(mid))
        print()
        print("  No output file was written.")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Build contingency tables
# ---------------------------------------------------------------------------

def contingency_by_outcome(rows):
    """
    Group matches by ``outcome`` and count total flagged vs. not-flagged rows
    within each outcome group.

    Flag counts in match_table.csv are per-match aggregates.  We treat
    total_rows as the denominator and total_flags as the flagged count, so
    not_flagged = total_rows - total_flags (floored at 0).
    """
    tbl = defaultdict(lambda: {"flagged": 0, "not_flagged": 0})
    for row in rows:
        outcome = row["outcome"].strip()
        total   = int_or_zero(row.get("total_rows", 0))
        flagged = total_flags(row)
        not_fl  = max(total - flagged, 0)
        tbl[outcome]["flagged"]     += flagged
        tbl[outcome]["not_flagged"] += not_fl
    return dict(tbl)


def contingency_by_source(rows):
    """
    Parse the ``source_breakdown`` column (format: 'key=n; key2=n2') and
    build a contingency table keyed by source/subreddit.

    For each subreddit the number of flagged rows is estimated proportionally:
        flagged_for_source ~= total_flags(match) * (source_count / total_source_count)
    rounded to the nearest integer.  not_flagged = source_count - flagged.
    """
    tbl = defaultdict(lambda: {"flagged": 0, "not_flagged": 0})

    for row in rows:
        breakdown = row.get("source_breakdown", "").strip()
        if not breakdown:
            continue

        source_counts = {}
        for part in breakdown.split(";"):
            part = part.strip()
            if "=" not in part:
                continue
            key, _, val = part.partition("=")
            source_counts[key.strip()] = int_or_zero(val)

        total_source = sum(source_counts.values())
        if total_source == 0:
            continue

        total_flags_match = total_flags(row)

        for src, count in source_counts.items():
            flagged = round(total_flags_match * count / total_source)
            not_fl  = max(count - flagged, 0)
            tbl[src]["flagged"]     += flagged
            tbl[src]["not_flagged"] += not_fl

    return dict(tbl)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # ------------------------------------------------------------------ load
    if not INPUT_FILE.exists():
        print("ERROR: Input file not found:\n  {}".format(INPUT_FILE))
        print("Run build_match_table.py first.")
        sys.exit(1)

    rows = read_csv(INPUT_FILE)
    if not rows:
        print("ERROR: {} is empty.".format(INPUT_FILE))
        sys.exit(1)

    # ---------------------------------------------- pre-flight column check
    check_required_columns(rows)

    # ------------------------------------------------------ build & run tests
    lines = [
        "group_effects_test.txt",
        "Generated by test_group_effects.py",
        "Input: {}".format(INPUT_FILE),
        "Matches analysed: {}".format(len(rows)),
        "",
        "Two tests are reported:",
        "  1. Flag rate by match OUTCOME (e.g. win / draw / loss)",
        "  2. Flag rate by SOURCE / SUBREDDIT",
        "",
        "Test selection rule:",
        "  * If every expected cell count >= 5  ->  Chi-square",
        "  * If any expected cell count < 5 and table is 2x2  ->  Fisher's exact",
        "  * If any expected cell count < 5 and table is larger than 2x2 ->",
        "    Chi-square is used but small-cell warnings are issued.",
        "",
    ]

    # --- Test 1: by outcome ---
    outcome_tbl = contingency_by_outcome(rows)
    if len(outcome_tbl) < 2:
        lines.append(
            "SKIPPED -- Test 1 (by outcome): fewer than 2 distinct outcome "
            "values found; a group comparison is not possible."
        )
        lines.append("")
    else:
        res1 = run_test(outcome_tbl, row_label="outcome")
        lines.append(format_result("Test 1: Flag rate by match OUTCOME", res1))

    # --- Test 2: by source/subreddit ---
    source_tbl = contingency_by_source(rows)
    if len(source_tbl) < 2:
        lines.append(
            "SKIPPED -- Test 2 (by source/subreddit): fewer than 2 distinct "
            "sources found; a group comparison is not possible."
        )
        lines.append("")
    else:
        res2 = run_test(source_tbl, row_label="source/subreddit")
        lines.append(format_result("Test 2: Flag rate by SOURCE / SUBREDDIT", res2))

    # ---------------------------------------------------------- write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = "\n".join(lines)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        fh.write(report)

    print(report)
    print("\nReport written to: {}".format(OUTPUT_FILE))


if __name__ == "__main__":
    main()
