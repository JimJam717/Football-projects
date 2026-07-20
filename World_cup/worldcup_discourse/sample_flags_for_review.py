"""
sample_flags_for_review.py
--------------------------
Read the per-category flagged-comment CSV exports from
    reports/phase2_basic_results/flagged_comments/
and, for each sensitive-language category, randomly sample up to 40 rows
(fixed random seed for reproducibility).

Output columns: match_id, category, matched_keyword, text, human_label

Output path: reports/analysis/flag_review_sample.csv

Usage
-----
    python sample_flags_for_review.py

Run from the worldcup_discourse directory (or anywhere – the script resolves
paths relative to its own location).
"""

import ast
import json
import os
import pathlib
import random

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RANDOM_SEED = 42
SAMPLE_SIZE = 40

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

INPUT_DIR = SCRIPT_DIR / "reports" / "phase2_basic_results" / "flagged_comments"
OUTPUT_PATH = SCRIPT_DIR / "reports" / "analysis" / "flag_review_sample.csv"

# Only the per-category files (skip the combined preview / JSONL)
CATEGORY_FILES = [
    "abusive_or_hard_language.csv",
    "identity_or_discrimination_context.csv",
    "negative_match_tone.csv",
    "severe_identity_slur.csv",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_matched_terms(raw: str) -> str:
    """
    Extract every keyword value from the matched_terms column and return
    them as a comma-separated string.

    The column looks like one of:
        {"abusive_or_hard_language": ["fuck"]}
        {"racism_or_discrimination_discussion": ["racist"], "abusive_or_hard_language": ["fucking"]}

    Falls back to the raw string if parsing fails.
    """
    if not isinstance(raw, str) or not raw.strip():
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Some exports use single quotes; try ast as a fallback
        try:
            parsed = ast.literal_eval(raw)
        except Exception:
            return raw.strip()

    if not isinstance(parsed, dict):
        return raw.strip()

    keywords: list[str] = []
    for values in parsed.values():
        if isinstance(values, list):
            keywords.extend(str(v) for v in values)
        else:
            keywords.append(str(values))

    return ", ".join(keywords)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    rng = random.Random(RANDOM_SEED)
    frames: list[pd.DataFrame] = []

    for filename in CATEGORY_FILES:
        filepath = INPUT_DIR / filename
        if not filepath.exists():
            print(f"[WARN] File not found, skipping: {filepath}")
            continue

        category = filepath.stem  # e.g. "abusive_or_hard_language"

        df = pd.read_csv(filepath, dtype=str, low_memory=False)

        # Drop completely empty rows (the severe_identity_slur file has a
        # trailing blank line that becomes an all-NaN row)
        df = df.dropna(how="all").reset_index(drop=True)

        n_rows = len(df)
        if n_rows == 0:
            print(f"[WARN] No data rows in {filename}, skipping.")
            continue

        sample_n = min(SAMPLE_SIZE, n_rows)
        sampled_indices = rng.sample(range(n_rows), sample_n)
        sample_df = df.iloc[sorted(sampled_indices)].copy()

        # Build the output frame with the required columns
        out = pd.DataFrame(
            {
                "match_id": sample_df["match_id"].str.strip(),
                "category": category,
                "matched_keyword": sample_df["matched_terms"].apply(
                    parse_matched_terms
                ),
                "text": sample_df["text_preview"].str.strip(),
                "human_label": "",  # blank column for manual annotation
            }
        )

        frames.append(out)
        print(f"[OK] {filename}: {n_rows} rows -> sampled {sample_n}")

    if not frames:
        print("[ERROR] No data loaded – check INPUT_DIR path.")
        return

    combined = pd.concat(frames, ignore_index=True)

    # Ensure output directory exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    combined.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(
        f"\nWrote {len(combined)} rows "
        f"({len(frames)} categories) -> {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
