"""
flag_detection.py
Step 1: Run lexicon + Detoxify multilingual over the deduplicated corpus.

Outputs (both private / gitignored):
    data/processed/identity_flags/comment_flags.parquet
        row_hash, match_id, subreddit, detected_language, swear_count,
        model_scored, identity_hostility_score, identity_hostility_flag,
        nationality_xenophobia_flag, flag_source, bucket
        -- NO text, author, or comment_id fields

Run order (USER executes these commands):
    # 1. Subset validation first (~5 000 rows, fast sanity check):
    python flag_detection.py --sample 5000
    # 2. Inspect comment_flags.parquet and qa_sample.csv, confirm output looks right.
    # 3. Full corpus (long-running — may take 1–3 h on CPU):
    python flag_detection.py

Options:
    --sample N          Load only N rows (skips row-count reconciliation)
    --config PATH       Path to flag_config.json [default: config/flag_config.json]
    --scored-dir PATH   Path to scored JSONL directory [default: ../data/processed/scored]
    --out PATH          Output parquet path [default: data/processed/identity_flags/comment_flags.parquet]
    --no-model          Lexicon-only run (skip Detoxify, mark all as model_unsupported unless
                        lexicon hits; useful for a fast cold-start test)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import re

import pandas as pd

from identity_common import (
    SCORED_DIR,
    OUTPUT_DIR,
    FLAG_CONFIG_PATH,
    load_flag_config,
    load_lexicon,
    load_corpus,
    is_model_supported,
    log,
    log_stage,
    row_hash,
)
from model_wrapper import IdentityScorer


# ---------------------------------------------------------------------------
# Lexicon matching helpers
# ---------------------------------------------------------------------------

def _build_pattern(terms: list[str]) -> re.Pattern:
    """Compile a case-insensitive pattern matching any of the given terms."""
    escaped = [re.escape(t) for t in sorted(terms, key=len, reverse=True)]
    return re.compile("|".join(escaped), re.IGNORECASE)


def lexicon_hit(text: str, pattern: re.Pattern) -> bool:
    if not text:
        return False
    return bool(pattern.search(text))


# ---------------------------------------------------------------------------
# Bucket assignment
# ---------------------------------------------------------------------------

BUCKET_ORDER = [
    "racial_ethnic_flagged",
    "nationality_flagged",
    "model_unsupported",
    "unflagged",
]


def assign_bucket(
    racial_ethnic_flag: bool,
    nationality_flag: bool,
    model_scored: bool,
) -> str:
    if racial_ethnic_flag:
        return "racial_ethnic_flagged"
    if nationality_flag:
        return "nationality_flagged"
    if not model_scored:
        return "model_unsupported"
    return "unflagged"


def assign_flag_source(
    racial_ethnic_flag: bool,
    nationality_flag: bool,
    racial_ethnic_lex: bool,
    nationality_lex: bool,
    model_above_threshold: bool,
) -> str:
    any_flag = racial_ethnic_flag or nationality_flag
    if not any_flag:
        return "none"
    lex_contributed = racial_ethnic_lex or nationality_lex
    model_contributed = model_above_threshold
    if lex_contributed and model_contributed:
        return "both"
    if lex_contributed:
        return "lexicon"
    return "model"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(
    config: dict,
    rows: list[dict],
    use_model: bool = True,
) -> pd.DataFrame:
    """Run the full flag-detection pass and return a DataFrame of per-comment flags."""

    lexicon = load_lexicon(config["lexicon_path"])
    re_pattern = {
        "racial_ethnic": _build_pattern(lexicon["racial_ethnic"]),
        "nationality": _build_pattern(lexicon["nationality"]),
    }

    identity_threshold: float = config["identity_threshold"]
    nationality_threshold: float = config["nationality_threshold"]

    # ------------------------------------------------------------------
    # Step A: lexicon pass (no model needed) — O(n * regex)
    # ------------------------------------------------------------------
    log("[lexicon] Running lexicon pass ...")
    racial_ethnic_lex = []
    nationality_lex = []
    for row in rows:
        text = row.get("text") or ""
        racial_ethnic_lex.append(lexicon_hit(text, re_pattern["racial_ethnic"]))
        nationality_lex.append(lexicon_hit(text, re_pattern["nationality"]))

    lex_racial_hits = sum(racial_ethnic_lex)
    lex_nat_hits = sum(nationality_lex)
    log_stage("lexicon_racial_ethnic_hits", lex_racial_hits)
    log_stage("lexicon_nationality_hits", lex_nat_hits)

    # ------------------------------------------------------------------
    # Step B: model pass — only on supported languages
    # ------------------------------------------------------------------
    model_scored_flags: list[bool] = []
    model_scores: list[float | None] = []

    if use_model:
        scorer = IdentityScorer(
            model_id=config["model_id"],
            identity_head=config["model_output_head"],
            fallback_head=config["model_output_fallback_head"],
            batch_size=config["batch_size"],
            max_chars=config["max_text_chars"],
        )

        # Build supported-language text list; unsupported get None placeholder
        texts_to_score: list[str | None] = []
        support_mask: list[bool] = []
        for row in rows:
            lang = row.get("detected_language") or ""
            supported = is_model_supported(lang)
            support_mask.append(supported)
            texts_to_score.append(row.get("text") if supported else None)

        supported_texts = [t for t in texts_to_score if t is not None]
        supported_count = len(supported_texts)
        unsupported_count = len(rows) - supported_count
        log_stage("model_supported_rows", supported_count)
        log_stage("model_unsupported_rows", unsupported_count)

        log("[model] Running inference (this may take a while on CPU) ...")
        scored_iter = iter(scorer.score_batched_iter(supported_texts))

        for supported in support_mask:
            if supported:
                score = next(scored_iter)
                model_scored_flags.append(True)
                model_scores.append(round(score, 6))
            else:
                model_scored_flags.append(False)
                model_scores.append(None)

        log_stage("model_inference_complete", supported_count)
    else:
        log("[model] Skipped (--no-model). All rows treated as model_unsupported unless lexicon hit.")
        for row in rows:
            model_scored_flags.append(False)
            model_scores.append(None)

    # ------------------------------------------------------------------
    # Step C: combine lexicon + model into per-comment flag columns
    # ------------------------------------------------------------------
    log("[flags] Combining lexicon and model signals ...")
    records = []
    for i, row in enumerate(rows):
        scored = model_scored_flags[i]
        score = model_scores[i]
        re_lex = racial_ethnic_lex[i]
        nat_lex = nationality_lex[i]
        above_threshold = scored and score is not None and score >= identity_threshold
        nat_above_threshold = scored and score is not None and score >= nationality_threshold

        # Racial/ethnic flag: lexicon OR (model scored AND above identity threshold)
        re_flag = re_lex or above_threshold
        # Nationality flag: nationality lexicon OR (model scored AND above nationality threshold)
        # Nationality is a separate, secondary track
        nat_flag = nat_lex or nat_above_threshold

        bucket = assign_bucket(re_flag, nat_flag, scored)
        flag_source = assign_flag_source(re_flag, nat_flag, re_lex, nat_lex, above_threshold)

        records.append(
            {
                # Privacy: no text, author, or raw comment_id
                "row_hash": row_hash(row.get("comment_id", f"row_{i}")),
                "match_id": row.get("match_id"),
                "subreddit": row.get("subreddit"),
                "detected_language": row.get("detected_language"),
                "swear_count": row.get("swear_count", 0),
                "model_scored": scored,
                "identity_hostility_score": score,
                "identity_hostility_flag": re_flag,
                "nationality_xenophobia_flag": nat_flag,
                "flag_source": flag_source,
                "bucket": bucket,
            }
        )

    df = pd.DataFrame(records)

    # Stage counts
    log_stage("total_rows", len(df))
    log_stage("racial_ethnic_flagged", int((df["bucket"] == "racial_ethnic_flagged").sum()))
    log_stage("nationality_flagged", int((df["bucket"] == "nationality_flagged").sum()))
    log_stage("model_unsupported", int((df["bucket"] == "model_unsupported").sum()))
    log_stage("unflagged", int((df["bucket"] == "unflagged").sum()))

    return df


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Flag identity hostility in the Reddit corpus.")
    p.add_argument(
        "--sample", type=int, default=None, metavar="N",
        help="Load only N rows (subset validation run). Skips row-count reconciliation.",
    )
    p.add_argument("--config", default=str(FLAG_CONFIG_PATH))
    p.add_argument("--scored-dir", default=str(SCORED_DIR))
    p.add_argument(
        "--out", default=str(OUTPUT_DIR / "comment_flags.parquet"),
        help="Output parquet path (private/gitignored intermediate).",
    )
    p.add_argument(
        "--no-model", action="store_true",
        help="Skip model inference. Lexicon-only run — fast but model_unsupported for all rows.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    config = load_flag_config()
    # Allow --config override
    if args.config != str(FLAG_CONFIG_PATH):
        import json
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)

    log(f"[start] Loading corpus from {args.scored_dir} ...")
    rows = load_corpus(Path(args.scored_dir), limit=args.sample)

    df = run(config, rows, use_model=not args.no_model)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    log(f"[output] Wrote {len(df):,} rows -> {out_path}")
    log("Done. Next: run export_qa_sample.py to generate the QA review CSV.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
