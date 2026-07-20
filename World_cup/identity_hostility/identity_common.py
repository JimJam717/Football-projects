"""
identity_common.py
Shared utilities for the identity-hostility pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Path roots (all relative; run scripts from identity_hostility/ directory)
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent
SWEARING_ROOT = ROOT.parent

SCORED_DIR = SWEARING_ROOT / "data" / "processed" / "scored"
DEDUPE_REPORT_PATH = SWEARING_ROOT / "data" / "collected" / "dedupe_report.json"
MATCH_CONFIG_PATH = SWEARING_ROOT / "worldcup2026_match_config.json"
FLAG_CONFIG_PATH = ROOT / "config" / "flag_config.json"

OUTPUT_DIR = ROOT / "data" / "processed" / "identity_flags"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Expected deduplicated row count — must match dedupe_report.json
EXPECTED_ROW_COUNT = 457898

# Detoxify multilingual supported languages (as returned by lingua)
SUPPORTED_LANGUAGES = frozenset(["en", "fr", "es", "it", "pt", "tr", "ru"])


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        # Windows console (cp1252) can't render some symbols (e.g. checkmarks).
        # Fall back to an ASCII-safe representation instead of crashing.
        print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)


def log_stage(stage: str, count: int) -> None:
    print(f"[{stage}] {count:,} rows", flush=True)


def abort(msg: str, code: int = 1) -> None:
    print(f"ABORT: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Config loaders
# ---------------------------------------------------------------------------

def load_flag_config() -> dict:
    with FLAG_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_match_config() -> dict:
    with MATCH_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_lexicon(lexicon_path: str | Path) -> dict:
    """Load the private identity lexicon. Returns dict with 'racial_ethnic' and
    'nationality' keys each containing a list of lowercase terms."""
    p = Path(lexicon_path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        abort(f"Identity lexicon not found at {p}. Create config/identity_lexicon.json before running.")
    with p.open("r", encoding="utf-8") as f:
        lex = json.load(f)
    if "racial_ethnic" not in lex or "nationality" not in lex:
        abort("identity_lexicon.json must have 'racial_ethnic' and 'nationality' keys.")
    return {
        "racial_ethnic": [t.lower() for t in lex["racial_ethnic"]],
        "nationality": [t.lower() for t in lex["nationality"]],
    }


# ---------------------------------------------------------------------------
# Stage map: match_id -> {phase, round, stage_label}
# ---------------------------------------------------------------------------

STAGE_LABEL_MAP = {
    "group_stage": "Group Stage",
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "quarterfinal": "Quarterfinal",
    "semifinal": "Semifinal",
    "final": "Final",
}


def build_stage_map(match_config: dict) -> dict[str, dict]:
    """Returns {match_id: {phase, round, stage_label}}."""
    result = {}
    for match in match_config.get("matches", []):
        mid = match["match_id"]
        phase = match.get("phase", "unknown")
        round_ = match.get("round", "")
        stage_label = STAGE_LABEL_MAP.get(phase, phase.replace("_", " ").title())
        result[mid] = {
            "phase": phase,
            "round": round_,
            "stage_label": stage_label,
            "date": match.get("date"),
        }
    return result


# ---------------------------------------------------------------------------
# Row hashing (privacy: replaces raw comment_id in stored/exported flag output)
# ---------------------------------------------------------------------------

_HASH_SALT = os.environ.get("IDENTITY_HASH_SALT", "worldcup2026_identity_pipeline_v1")


def row_hash(comment_id: str) -> str:
    """Return a deterministic, salted SHA-256 hex digest of comment_id.

    This is NOT a privacy guarantee against a determined attacker with the raw dataset,
    but it prevents accidental leakage of raw Reddit comment IDs into outputs.
    Override salt via IDENTITY_HASH_SALT env var.
    """
    payload = f"{_HASH_SALT}:{comment_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Corpus loader
# ---------------------------------------------------------------------------

def iter_scored_rows(scored_dir: Path = SCORED_DIR) -> Iterator[dict]:
    """Yield every row from all match JSONL files in the scored directory."""
    for path in sorted(scored_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


def load_corpus(
    scored_dir: Path = SCORED_DIR,
    limit: int | None = None,
) -> list[dict]:
    """Load the full deduplicated corpus and reconcile the row count.

    Parameters
    ----------
    limit : int or None
        If set, load at most `limit` rows (for subset/sample validation runs).
        Row-count reconciliation is skipped when limit is active.
    """
    rows = []
    for row in iter_scored_rows(scored_dir):
        rows.append(row)
        if limit is not None and len(rows) >= limit:
            break

    log_stage("corpus_loaded", len(rows))

    if limit is None:
        _reconcile_row_count(len(rows))

    return rows


def _reconcile_row_count(actual: int) -> None:
    """Abort if the loaded row count doesn't match the dedupe report."""
    if not DEDUPE_REPORT_PATH.exists():
        log(f"WARNING: dedupe report not found at {DEDUPE_REPORT_PATH}; skipping reconciliation.")
        return

    with DEDUPE_REPORT_PATH.open("r", encoding="utf-8") as f:
        report = json.load(f)

    expected = report.get("rows_after", EXPECTED_ROW_COUNT)
    if actual != expected:
        abort(
            f"Row count mismatch! Loaded {actual:,} rows but dedupe report says {expected:,}. "
            "Check that no scored files have been added or removed."
        )
    log(f"[corpus_reconcile] OK — {actual:,} rows match dedupe report.")


# ---------------------------------------------------------------------------
# Language gate
# ---------------------------------------------------------------------------

def is_model_supported(detected_language: str | None) -> bool:
    """Return True only if the language is in the Detoxify multilingual supported set."""
    return (detected_language or "").lower() in SUPPORTED_LANGUAGES
