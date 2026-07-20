"""
test_outcome_effect.py
======================
Tests whether match outcome is associated with sentiment-label distribution
or flagged-comment rates, pooled across all matches and all players.

Data sources
------------
- data/processed/*_sentiment.jsonl
  Sentiment-scored records with record_id or id and sentiment_label.
- reports/phase2_basic_results/flagged_comments/*.csv
  Flagged record IDs in the record_id field.
- match_outcomes.py
  Hardcoded match_id -> outcome and match_id -> nation placeholders.

Output
------
reports/analysis/outcome_effect_test.txt
"""

import csv
import glob
import json
import math
import os
from collections import Counter
from pathlib import Path

from scipy.stats import chi2_contingency, fisher_exact

from match_outcomes import MATCH_NATIONS, MATCH_OUTCOMES


BASE_DIR = Path(__file__).parent
SENTIMENT_GLOB = str(BASE_DIR / "data" / "processed" / "*_sentiment.jsonl")
FLAGGED_DIR = BASE_DIR / "reports" / "phase2_basic_results" / "flagged_comments"
OUTPUT_FILE = BASE_DIR / "reports" / "analysis" / "outcome_effect_test.txt"

OUTCOMES = ("win", "loss", "draw")
SENTIMENT_LABELS = ("negative", "neutral", "positive")
FLAG_STATUSES = ("flagged", "unflagged")
PLACEHOLDERS = {None, "", "TBD", "TODO", "PLACEHOLDER"}
EXCLUDED_MATCH_IDS = {"2022_france_morocco_qf"}


def match_id_from_sentiment_path(path: str) -> str:
    return os.path.basename(path).replace("_sentiment.jsonl", "")


def normalize_id(value) -> str:
    return str(value or "").strip()


def is_placeholder(value) -> bool:
    if value is None:
        return True
    return str(value).strip().upper() in PLACEHOLDERS


def discover_match_ids() -> list[str]:
    """Find match IDs present in sentiment files or flagged-comments outputs."""
    match_ids = set()
    for path in glob.glob(SENTIMENT_GLOB):
        match_id = match_id_from_sentiment_path(path)
        if match_id not in EXCLUDED_MATCH_IDS:
            match_ids.add(match_id)

    for csv_path in FLAGGED_DIR.glob("*.csv"):
        with open(csv_path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if "match_id" not in (reader.fieldnames or []):
                continue
            for row in reader:
                match_id = normalize_id(row.get("match_id"))
                if match_id and match_id not in EXCLUDED_MATCH_IDS:
                    match_ids.add(match_id)

    jsonl_path = FLAGGED_DIR / "flagged_comments_full.jsonl"
    if jsonl_path.exists():
        with open(jsonl_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                match_id = normalize_id(record.get("match_id"))
                if match_id and match_id not in EXCLUDED_MATCH_IDS:
                    match_ids.add(match_id)

    return sorted(match_ids)


def validate_match_metadata(match_ids: list[str]) -> list[str]:
    """Return messages for missing or placeholder outcome/nation values."""
    problems = []
    for match_id in match_ids:
        outcome = MATCH_OUTCOMES.get(match_id)
        nation = MATCH_NATIONS.get(match_id)
        if is_placeholder(outcome):
            problems.append(f"  {match_id}: outcome is not filled in")
        elif str(outcome).strip().lower() not in OUTCOMES:
            problems.append(f"  {match_id}: outcome must be one of {', '.join(OUTCOMES)}")
        if is_placeholder(nation):
            problems.append(f"  {match_id}: nation is not filled in")
    return problems


def load_flagged_records(flagged_dir: Path) -> set[tuple[str, str]]:
    """Collect flagged (match_id, record_id) pairs from CSV files."""
    flagged_records = set()
    csv_files = list(flagged_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {flagged_dir}")

    for csv_path in csv_files:
        with open(csv_path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames or []
            if "record_id" not in fieldnames:
                continue
            has_match_id = "match_id" in fieldnames
            for row in reader:
                record_id = normalize_id(row.get("record_id"))
                match_id = normalize_id(row.get("match_id")) if has_match_id else ""
                if record_id and match_id and match_id not in EXCLUDED_MATCH_IDS:
                    flagged_records.add((match_id, record_id))

    print(
        f"  Loaded {len(flagged_records):,} unique flagged (match_id, record_id) "
        f"pairs from {len(csv_files)} CSV file(s)."
    )
    return flagged_records


def load_sentiment_records(sentiment_glob: str) -> tuple[list[dict], int]:
    """Load sentiment records with record_id/id, sentiment_label, and match_id."""
    records = []
    n_skipped = 0
    files = sorted(glob.glob(sentiment_glob))
    if not files:
        raise FileNotFoundError(f"No sentiment JSONL files matched: {sentiment_glob}")

    print(f"  Found {len(files)} sentiment JSONL file(s).")
    for path in files:
        file_match_id = match_id_from_sentiment_path(path)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    n_skipped += 1
                    continue

                record_id = normalize_id(record.get("record_id") or record.get("id"))
                label = normalize_id(record.get("sentiment_label")).lower()
                match_id = normalize_id(record.get("match_id")) or file_match_id
                if match_id in EXCLUDED_MATCH_IDS:
                    continue
                if not record_id or label not in SENTIMENT_LABELS or not match_id:
                    n_skipped += 1
                    continue
                records.append(
                    {
                        "match_id": match_id,
                        "record_id": record_id,
                        "sentiment_label": label,
                    }
                )

    print(f"  Loaded sentiment records: {len(records):,}")
    print(f"  Skipped sentiment rows  : {n_skipped:,}")
    return records, n_skipped


def zero_table(rows: tuple[str, ...], cols: tuple[str, ...]) -> dict[str, Counter]:
    return {row: Counter({col: 0 for col in cols}) for row in rows}


def build_tables(sentiment_records: list[dict], flagged_records: set[tuple[str, str]]) -> dict:
    sentiment_table = zero_table(OUTCOMES, SENTIMENT_LABELS)
    flag_table = zero_table(OUTCOMES, FLAG_STATUSES)
    totals_by_outcome = Counter()

    for record in sentiment_records:
        match_id = record["match_id"]
        outcome = str(MATCH_OUTCOMES[match_id]).strip().lower()
        flag_status = (
            "flagged"
            if (match_id, record["record_id"]) in flagged_records
            else "unflagged"
        )

        sentiment_table[outcome][record["sentiment_label"]] += 1
        flag_table[outcome][flag_status] += 1
        totals_by_outcome[outcome] += 1

    return {
        "sentiment_table": sentiment_table,
        "flag_table": flag_table,
        "totals_by_outcome": totals_by_outcome,
    }


def as_matrix(table: dict[str, Counter], rows: tuple[str, ...], cols: tuple[str, ...]) -> list[list[int]]:
    return [[table[row][col] for col in cols] for row in rows]


def cramers_v(statistic: float, total_n: int, rows: int, cols: int) -> float:
    denominator = total_n * min(rows - 1, cols - 1)
    if denominator == 0:
        return 0.0
    return math.sqrt(statistic / denominator)


def run_independence_test(table: dict[str, Counter], rows: tuple[str, ...], cols: tuple[str, ...]) -> dict:
    tested_rows = tuple(row for row in rows if sum(table[row][col] for col in cols) > 0)
    if len(tested_rows) < 2:
        raise ValueError("At least two non-empty outcome groups are required for a test.")

    matrix = as_matrix(table, tested_rows, cols)
    chi2_stat, chi2_p, dof, expected = chi2_contingency(matrix)
    min_expected = min(value for row in expected for value in row)
    total_n = sum(sum(row) for row in matrix)

    result = {
        "test_name": "Chi-square test of independence",
        "statistic": chi2_stat,
        "p_value": chi2_p,
        "degrees_of_freedom": dof,
        "expected_counts": expected,
        "min_expected_count": min_expected,
        "validity_warning": min_expected < 5,
        "cramers_v": cramers_v(chi2_stat, total_n, len(tested_rows), len(cols)),
        "tested_rows": tested_rows,
    }

    if min_expected < 5:
        fisher = fisher_exact(matrix)
        result.update(
            {
                "test_name": "Fisher's exact test",
                "statistic": float(fisher.statistic),
                "p_value": float(fisher.pvalue),
            }
        )

    return result


def pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator * 100


def share_metrics(tables: dict) -> list[str]:
    sentiment_table = tables["sentiment_table"]
    flag_table = tables["flag_table"]
    totals = tables["totals_by_outcome"]

    lines = [
        "--- Simple outcome-group rates ---",
        "  Outcome       N  Negative share     Flag rate",
        "  ---------------------------------------------",
    ]
    negative_pct = {}
    flag_pct = {}
    for outcome in OUTCOMES:
        total = totals[outcome]
        negative_pct[outcome] = pct(sentiment_table[outcome]["negative"], total)
        flag_pct[outcome] = pct(flag_table[outcome]["flagged"], total)
        lines.append(
            f"  {outcome:<7} {total:>7,}  "
            f"{negative_pct[outcome]:>12.2f}%  {flag_pct[outcome]:>10.2f}%"
        )

    lines += [
        "",
        "--- Win-loss percentage point spread ---",
        f"  Negative-share spread (win - loss): {negative_pct['win'] - negative_pct['loss']:.2f} pp",
        f"  Flag-rate spread      (win - loss): {flag_pct['win'] - flag_pct['loss']:.2f} pp",
    ]
    return lines


def format_count_table(
    title: str,
    table: dict[str, Counter],
    rows: tuple[str, ...],
    cols: tuple[str, ...],
) -> list[str]:
    header = "  Outcome" + "".join(f"{col.title():>12}" for col in cols) + f"{'Total':>12}"
    lines = [title, header, "  " + "-" * (len(header) - 2)]
    for row in rows:
        row_total = sum(table[row][col] for col in cols)
        lines.append(
            f"  {row:<7}"
            + "".join(f"{table[row][col]:>12,}" for col in cols)
            + f"{row_total:>12,}"
        )
    return lines


def format_test_result(title: str, result: dict) -> list[str]:
    lines = [
        title,
        f"  Test                 : {result['test_name']}",
        f"  Statistic            : {result['statistic']:.6f}",
        f"  p-value              : {result['p_value']:.6e}",
        f"  Degrees of freedom   : {result['degrees_of_freedom']}",
        f"  Cramer's V           : {result['cramers_v']:.6f}",
        f"  Min expected count   : {result['min_expected_count']:.4f}",
    ]
    if result["validity_warning"]:
        lines.append(
            "  WARNING: At least one expected cell count is below 5; "
            "Fisher's exact test was used."
        )
    return lines


def write_output(
    tables: dict,
    sentiment_result: dict,
    flag_result: dict,
    n_sentiment: int,
    n_flagged_pairs: int,
    n_skipped: int,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "=" * 72,
        "  Outcome Effect Tests",
        "  Pooled across all matches with the same outcome and all players",
        "=" * 72,
        "",
        "--- Sample sizes ---",
        f"  Sentiment records loaded          : {n_sentiment:,}",
        f"  Unique flagged match-record pairs : {n_flagged_pairs:,}",
        f"  Skipped sentiment rows            : {n_skipped:,}",
        "",
        *format_count_table(
            "--- Contingency table: outcome x sentiment_label ---",
            tables["sentiment_table"],
            OUTCOMES,
            SENTIMENT_LABELS,
        ),
        "",
        *format_test_result("--- Sentiment-label independence test ---", sentiment_result),
        "",
        *format_count_table(
            "--- Contingency table: outcome x flagged status ---",
            tables["flag_table"],
            OUTCOMES,
            FLAG_STATUSES,
        ),
        "",
        *format_test_result("--- Flag-status independence test ---", flag_result),
        "",
        *share_metrics(tables),
        "",
        "=" * 72,
    ]

    text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(f"\nResults written to: {output_path}")
    print()
    print(text)


def main() -> None:
    print("\n[1/5] Discovering match IDs ...")
    match_ids = discover_match_ids()
    for match_id in match_ids:
        print(f"  {match_id}")

    metadata_problems = validate_match_metadata(match_ids)
    if metadata_problems:
        print(
            "\nmatch_outcomes.py still contains placeholder, missing, or invalid values.\n"
            "Fill in MATCH_OUTCOMES with win/loss/draw and MATCH_NATIONS with the\n"
            "team/nation context for each match before running the outcome tests.\n"
        )
        print("Values needing attention:")
        print("\n".join(metadata_problems))
        return

    print("\n[2/5] Loading flagged record IDs ...")
    flagged_records = load_flagged_records(FLAGGED_DIR)

    print("\n[3/5] Loading sentiment labels from JSONL files ...")
    sentiment_records, n_skipped = load_sentiment_records(SENTIMENT_GLOB)

    print("\n[4/5] Building contingency tables ...")
    tables = build_tables(sentiment_records, flagged_records)

    print("\n[5/5] Running independence tests ...")
    sentiment_result = run_independence_test(
        tables["sentiment_table"], OUTCOMES, SENTIMENT_LABELS
    )
    flag_result = run_independence_test(tables["flag_table"], OUTCOMES, FLAG_STATUSES)

    write_output(
        tables,
        sentiment_result,
        flag_result,
        len(sentiment_records),
        len(flagged_records),
        n_skipped,
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()
