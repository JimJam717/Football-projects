"""
test_flag_sentiment.py
======================
Tests whether flagged comments have a different sentiment-label distribution
than unflagged comments, pooled across all matches and all players.

Data sources
------------
- data/processed/*_sentiment.jsonl
  Sentiment-scored records with record_id or id and sentiment_label.
- reports/phase2_basic_results/flagged_comments/*.csv
  Flagged record IDs in the record_id field.

Statistical test
----------------
Chi-square test of independence between flag status (flagged/unflagged)
and sentiment_label (negative/neutral/positive), with Cramer's V as the
effect size.

Secondary check
---------------
Negative-share difference:
    negative_share = negative_count / total_count

Output
------
reports/analysis/flag_sentiment_test.txt
"""

import csv
import glob
import json
import math
import os
from collections import Counter
from pathlib import Path

from scipy.stats import chi2_contingency


BASE_DIR = Path(__file__).parent
SENTIMENT_GLOB = str(BASE_DIR / "data" / "processed" / "*_sentiment.jsonl")
FLAGGED_DIR = BASE_DIR / "reports" / "phase2_basic_results" / "flagged_comments"
OUTPUT_FILE = BASE_DIR / "reports" / "analysis" / "flag_sentiment_test.txt"
SENTIMENT_LABELS = ("negative", "neutral", "positive")


def load_flagged_ids(flagged_dir: Path) -> set:
    """Collect all flagged record IDs from every CSV in flagged_dir."""
    flagged_ids: set = set()
    csv_files = list(flagged_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {flagged_dir}")

    for csv_path in csv_files:
        with open(csv_path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if "record_id" not in (reader.fieldnames or []):
                continue
            for row in reader:
                rid = row.get("record_id", "").strip()
                if rid:
                    flagged_ids.add(rid)

    print(
        f"  Loaded {len(flagged_ids):,} unique flagged record IDs "
        f"from {len(csv_files)} CSV file(s)."
    )
    return flagged_ids


def load_sentiment_labels(sentiment_glob: str, flagged_ids: set):
    """
    Read all *_sentiment.jsonl files and split sentiment_label into
    flagged and unflagged groups.

    Returns (flagged_labels, unflagged_labels, n_skipped, match_sentiment_counts)
    where match_sentiment_counts maps basename -> line count.
    """
    flagged_labels: list[str] = []
    unflagged_labels: list[str] = []
    n_skipped = 0
    match_sentiment_counts: dict[str, int] = {}

    files = sorted(glob.glob(sentiment_glob))
    if not files:
        raise FileNotFoundError(f"No sentiment JSONL files matched: {sentiment_glob}")

    print(f"  Found {len(files)} sentiment JSONL file(s).")
    for fpath in files:
        fname = os.path.basename(fpath)
        line_count = 0
        with open(fpath, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                line_count += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    n_skipped += 1
                    continue

                label = record.get("sentiment_label")
                rid = record.get("record_id") or record.get("id", "")
                if label not in SENTIMENT_LABELS:
                    n_skipped += 1
                    continue

                if rid in flagged_ids:
                    flagged_labels.append(label)
                else:
                    unflagged_labels.append(label)

        match_sentiment_counts[fname] = line_count

    print(f"  Flagged records with sentiment  : {len(flagged_labels):,}")
    print(f"  Unflagged records with sentiment: {len(unflagged_labels):,}")
    print(f"  Skipped (missing/bad label)     : {n_skipped:,}")
    return flagged_labels, unflagged_labels, n_skipped, match_sentiment_counts


def write_data_gap_report(
    flagged_ids: set,
    flagged_labels: list,
    unflagged_labels: list,
    n_skipped: int,
    match_sentiment_counts: dict,
    flagged_dir: Path,
    output_path: Path,
) -> None:
    """Write a diagnostic report when no overlap exists between datasets."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    flagged_by_match: dict[str, int] = {}
    for csv_path in sorted(flagged_dir.glob("*.csv")):
        with open(csv_path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if "record_id" not in (reader.fieldnames or []) or "match_id" not in (reader.fieldnames or []):
                continue
            for row in reader:
                match_id = row.get("match_id", "unknown").strip()
                flagged_by_match[match_id] = flagged_by_match.get(match_id, 0) + 1

    lines = [
        "=" * 62,
        "  Chi-square Test: Flag Status vs Sentiment Label",
        "  (Pooled across all matches and all players)",
        "=" * 62,
        "",
        "STATUS: DATA GAP - TEST COULD NOT BE RUN",
        "",
        "No flagged record has a corresponding sentiment label, so the",
        "flagged and unflagged label distributions cannot be compared.",
        "",
        "--- Flagged records by match (from flagged_comments/ CSVs) ---",
    ]
    for match_id, count in sorted(flagged_by_match.items()):
        lines.append(f"  {match_id}: {count:,} flagged records")

    lines += ["", "--- Sentiment JSONL line counts ---"]
    for fname, count in sorted(match_sentiment_counts.items()):
        match_key = fname.replace("_sentiment.jsonl", "")
        overlap = "(FLAGGED MATCH - EMPTY)" if match_key in flagged_by_match and count == 0 else ""
        lines.append(f"  {fname}: {count:,} lines  {overlap}")

    lines += [
        "",
        "--- Counts at point of failure ---",
        f"  Total unique flagged IDs loaded : {len(flagged_ids):,}",
        f"  Flagged IDs matched to sentiment: {len(flagged_labels):,}",
        f"  Unflagged records loaded        : {len(unflagged_labels):,}",
        f"  Skipped records                 : {n_skipped:,}",
        "",
        "=" * 62,
    ]

    text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(f"\nDiagnostic report written to: {output_path}")
    print()
    print(text)


def label_counts(labels: list[str]) -> Counter:
    counts = Counter(labels)
    return Counter({label: counts[label] for label in SENTIMENT_LABELS})


def row_percentages(counts: Counter) -> dict[str, float]:
    total = sum(counts[label] for label in SENTIMENT_LABELS)
    if total == 0:
        return {label: 0.0 for label in SENTIMENT_LABELS}
    return {label: counts[label] / total * 100 for label in SENTIMENT_LABELS}


def cramers_v(chi2: float, total_n: int, rows: int, cols: int) -> float:
    denominator = total_n * min(rows - 1, cols - 1)
    if denominator == 0:
        return 0.0
    return math.sqrt(chi2 / denominator)


def run_test(flagged_labels: list[str], unflagged_labels: list[str]) -> dict:
    """Run chi-square independence test and compute Cramer's V."""
    if not flagged_labels:
        raise ValueError("No flagged sentiment labels found - cannot run test.")
    if not unflagged_labels:
        raise ValueError("No unflagged sentiment labels found - cannot run test.")

    flagged_counts = label_counts(flagged_labels)
    unflagged_counts = label_counts(unflagged_labels)
    table = [
        [flagged_counts[label] for label in SENTIMENT_LABELS],
        [unflagged_counts[label] for label in SENTIMENT_LABELS],
    ]

    chi2, p_value, dof, expected = chi2_contingency(table)
    min_expected_count = min(value for row in expected for value in row)
    total_n = len(flagged_labels) + len(unflagged_labels)
    flagged_negative_share = flagged_counts["negative"] / len(flagged_labels)
    unflagged_negative_share = unflagged_counts["negative"] / len(unflagged_labels)

    return {
        "n_flagged": len(flagged_labels),
        "n_unflagged": len(unflagged_labels),
        "flagged_counts": flagged_counts,
        "unflagged_counts": unflagged_counts,
        "flagged_pct": row_percentages(flagged_counts),
        "unflagged_pct": row_percentages(unflagged_counts),
        "chi2_statistic": chi2,
        "p_value": p_value,
        "degrees_of_freedom": dof,
        "expected_counts": expected,
        "chi2_valid": min_expected_count >= 5,
        "min_expected_count": min_expected_count,
        "cramers_v": cramers_v(chi2, total_n, rows=2, cols=len(SENTIMENT_LABELS)),
        "flagged_negative_share": flagged_negative_share,
        "unflagged_negative_share": unflagged_negative_share,
        "negative_share_difference_pp": (flagged_negative_share - unflagged_negative_share) * 100,
    }


def format_count_row(group: str, counts: Counter, total: int) -> str:
    return (
        f"  {group:<10}"
        f"  {counts['negative']:>10,}"
        f"  {counts['neutral']:>10,}"
        f"  {counts['positive']:>10,}"
        f"  {total:>10,}"
    )


def format_pct_row(group: str, percentages: dict[str, float]) -> str:
    return (
        f"  {group:<10}"
        f"  {percentages['negative']:>9.2f}%"
        f"  {percentages['neutral']:>9.2f}%"
        f"  {percentages['positive']:>9.2f}%"
    )


def write_output(results: dict, n_skipped: int, output_path: Path) -> None:
    """Write a human-readable results file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "=" * 62,
        "  Chi-square Test: Flag Status vs Sentiment Label",
        "  (Pooled across all matches and all players)",
        "=" * 62,
        "",
        "--- Sample sizes ---",
        f"  Flagged comments   (n): {results['n_flagged']:,}",
        f"  Unflagged comments (n): {results['n_unflagged']:,}",
        f"  Skipped records       : {n_skipped:,}",
        "",
        "--- Contingency table: counts ---",
        "  Group         Negative     Neutral    Positive       Total",
        "  ----------------------------------------------------------",
        format_count_row("Flagged", results["flagged_counts"], results["n_flagged"]),
        format_count_row("Unflagged", results["unflagged_counts"], results["n_unflagged"]),
        "",
        "--- Contingency table: row percentages ---",
        "  Group         Negative     Neutral    Positive",
        "  ---------------------------------------------",
        format_pct_row("Flagged", results["flagged_pct"]),
        format_pct_row("Unflagged", results["unflagged_pct"]),
        "",
        "--- Chi-square test of independence ---",
        f"  Chi-square statistic : {results['chi2_statistic']:.4f}",
        f"  Degrees of freedom   : {results['degrees_of_freedom']}",
        f"  p-value              : {results['p_value']:.6e}",
        f"  Cramer's V           : {results['cramers_v']:.6f}",
        f"  Min expected count   : {results['min_expected_count']:.4f}",
        *(
            []
            if results["chi2_valid"]
            else [
                "  WARNING: At least one expected cell count is below 5; "
                "the chi-square approximation may not be reliable."
            ]
        ),
        "",
        "--- Negative-share check ---",
        f"  Negative share - flagged  : {results['flagged_negative_share'] * 100:.2f}%",
        f"  Negative share - unflagged: {results['unflagged_negative_share'] * 100:.2f}%",
        f"  Difference               : {results['negative_share_difference_pp']:.2f} percentage points",
        "",
        "--- Interpretation ---",
    ]

    p_value = results["p_value"]
    sig = "statistically significant" if p_value < 0.05 else "NOT statistically significant"
    v = results["cramers_v"]
    magnitude = (
        "negligible (V < 0.1)"
        if v < 0.1
        else "small (0.1 <= V < 0.3)"
        if v < 0.3
        else "medium (0.3 <= V < 0.5)"
        if v < 0.5
        else "large (V >= 0.5)"
    )

    lines += [
        f"  Sentiment-label distribution differs by flag status: {sig} (alpha = 0.05).",
        f"  Effect size (Cramer's V = {v:.4f}): {magnitude}.",
        "",
        "=" * 62,
    ]

    text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(f"\nResults written to: {output_path}")
    print()
    print(text)


def main():
    print("\n[1/3] Loading flagged record IDs ...")
    flagged_ids = load_flagged_ids(FLAGGED_DIR)

    print("\n[2/3] Loading sentiment labels from JSONL files ...")
    flagged_labels, unflagged_labels, n_skipped, match_sentiment_counts = (
        load_sentiment_labels(SENTIMENT_GLOB, flagged_ids)
    )

    if not flagged_labels:
        print(
            "\n[WARNING] Zero flagged records matched a sentiment label.\n"
            "          Writing data-gap diagnostic report instead of test results."
        )
        write_data_gap_report(
            flagged_ids,
            flagged_labels,
            unflagged_labels,
            n_skipped,
            match_sentiment_counts,
            FLAGGED_DIR,
            OUTPUT_FILE,
        )
        return

    print("\n[3/3] Running chi-square test ...")
    results = run_test(flagged_labels, unflagged_labels)
    write_output(results, n_skipped, OUTPUT_FILE)


if __name__ == "__main__":
    main()
