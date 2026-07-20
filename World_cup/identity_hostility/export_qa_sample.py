"""
export_qa_sample.py
Step 2/4: Export a private QA review sample for manual threshold calibration.

Reads comment_flags.parquet + the original scored corpus to produce a CSV
containing ~150-200 flagged rows with FULL, UNTRUNCATED comment text.

This file is PRIVATE and GITIGNORED. It is for your eyes only to judge
false positives and tune thresholds in config/flag_config.json.

After reviewing, update identity_threshold / nationality_threshold in
config/flag_config.json and rerun flag_detection.py.

USER RUNS THIS:
    python export_qa_sample.py
    python export_qa_sample.py --n 200 --seed 99
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from identity_common import (
    SCORED_DIR,
    OUTPUT_DIR,
    log,
    log_stage,
    abort,
)


def load_comment_flags(flags_path: Path) -> pd.DataFrame:
    if not flags_path.exists():
        abort(f"comment_flags.parquet not found at {flags_path}. Run flag_detection.py first.")
    return pd.read_parquet(flags_path)


def build_hash_to_text(scored_dir: Path) -> dict[str, dict]:
    """Scan scored JSONL files and build a row_hash -> {text, match_id, subreddit} lookup.

    Note: row_hash is recomputed here from comment_id so we can join back without
    exposing comment_id in the exported QA CSV.
    """
    from identity_common import row_hash
    import json

    lookup: dict[str, dict] = {}
    for path in sorted(scored_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                cid = row.get("comment_id", "")
                rh = row_hash(cid)
                lookup[rh] = {
                    "text": row.get("text", ""),
                    "detected_language": row.get("detected_language"),
                    "swear_count": row.get("swear_count", 0),
                }
    return lookup


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export private QA sample for threshold calibration.")
    p.add_argument("--n", type=int, default=200, help="Sample size (default 200)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--flags", default=str(OUTPUT_DIR / "comment_flags.parquet"),
        help="Path to comment_flags.parquet",
    )
    p.add_argument("--scored-dir", default=str(SCORED_DIR))
    p.add_argument(
        "--out", default=str(OUTPUT_DIR / "qa_sample.csv"),
        help="Output CSV path (PRIVATE/GITIGNORED — never share or commit this file)",
    )
    p.add_argument(
        "--include-unflagged", type=int, default=20, metavar="K",
        help="Also include K unflagged rows as negative control (default 20)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    flags_path = Path(args.flags)
    scored_dir = Path(args.scored_dir)
    out_path = Path(args.out)

    log(f"[qa_sample] Loading flags from {flags_path} ...")
    df = load_comment_flags(flags_path)
    log_stage("flags_loaded", len(df))

    # Stratified sample: pull from each actually-flagged bucket, then add negative
    # controls. IMPORTANT: "model_unsupported" is NOT a flagged bucket — it means
    # the model couldn't score the row (short text / unsupported language). It
    # must be excluded here, or it silently dilutes the QA sample with rows that
    # were never flagged as hostile at all.
    flagged = df[df["bucket"].isin(["racial_ethnic_flagged", "nationality_flagged"])].copy()
    unflagged_pool = df[df["bucket"] == "unflagged"].copy()

    log_stage("flagged_pool", len(flagged))
    log_stage("unflagged_pool", len(unflagged_pool))
    log_stage("model_unsupported_excluded", int((df["bucket"] == "model_unsupported").sum()))

    n_flagged = min(args.n, len(flagged))
    n_unflagged = min(args.include_unflagged, len(unflagged_pool))

    sample_flagged = flagged.sample(n=n_flagged, random_state=args.seed)
    sample_unflagged = unflagged_pool.sample(n=n_unflagged, random_state=args.seed)
    sample = pd.concat([sample_flagged, sample_unflagged], ignore_index=True)
    sample = sample.sample(frac=1, random_state=args.seed).reset_index(drop=True)  # shuffle

    log(f"[qa_sample] Building text lookup from scored corpus ({scored_dir}) ...")
    lookup = build_hash_to_text(scored_dir)

    # Join full text back in
    sample["text"] = sample["row_hash"].map(lambda h: lookup.get(h, {}).get("text", ""))

    # QA-friendly columns (includes full text)
    qa_cols = [
        "bucket",
        "flag_source",
        "identity_hostility_score",
        "identity_hostility_flag",
        "nationality_xenophobia_flag",
        "model_scored",
        "swear_count",
        "detected_language",
        "match_id",
        "subreddit",
        "text",   # ← FULL untruncated text; keep this file local/gitignored
    ]
    qa = sample[[c for c in qa_cols if c in sample.columns]].copy()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    qa.to_csv(out_path, index=False, encoding="utf-8-sig")

    log(f"[qa_sample] Wrote {len(qa)} rows -> {out_path}")
    log("")
    log("NEXT STEPS:")
    log("  1. Open qa_sample.csv in Excel/Sheets (keep it LOCAL — never commit or share).")
    log("  2. Skim the 'text' column in flagged rows. Mark obvious false positives.")
    log("  3. If many false positives at current threshold, raise identity_threshold in")
    log("     config/flag_config.json (e.g. 0.5 -> 0.6).")
    log("  4. If too many misses, lower the threshold.")
    log("  5. Rerun: python flag_detection.py")
    log("  6. Then: python export_qa_sample.py  (to spot-check again)")
    log("  7. When satisfied: python aggregate_results.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
