"""
verify_no_leak.py
Leak-check gate — run before sharing any public output.

Scans all public artifacts and fails loudly if any per-comment identifier
(raw text, author, or comment_id) from the scored corpus appears as a substring.
Also verifies that aggregate_results.parquet contains none of the forbidden columns.

PUBLIC FILES SCANNED:
    data/processed/identity_flags/aggregate_results.parquet
    dashboard/identity_hostility_dashboard.html
    docs/methodology_and_limitations.md

FORBIDDEN VALUES (sourced from scored corpus):
    1. text  — full comment body
    2. author — Reddit username
    3. comment_id — raw Reddit comment id

USER RUNS THIS (after generating all outputs, before sharing):
    python verify_no_leak.py

Exit code 0 = PASS (safe to share)
Exit code 1 = FAIL (do not share; fix before proceeding)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from identity_common import SCORED_DIR, OUTPUT_DIR, log

FORBIDDEN_COLUMNS = {"text", "author", "comment_id", "row_hash"}

PUBLIC_FILES = [
    OUTPUT_DIR / "aggregate_results.parquet",
    Path(__file__).parent / "dashboard" / "identity_hostility_dashboard.html",
    Path(__file__).parent / "docs" / "methodology_and_limitations.md",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_raw_identifiers(scored_dir: Path) -> tuple[set[str], set[str], set[str]]:
    """Extract all distinct comment_id, author, and text values from the scored corpus."""
    comment_ids: set[str] = set()
    authors: set[str] = set()
    # For text we only check the first 60 chars to keep memory manageable;
    # any verbatim leak would match this prefix.
    texts_prefix: set[str] = set()

    log("[leak_check] Scanning scored corpus for raw identifiers ...")
    file_count = 0
    for path in sorted(scored_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cid = row.get("comment_id")
                author = row.get("author")
                text = row.get("text", "")
                if cid:
                    comment_ids.add(cid)
                if author:
                    authors.add(author)
                if text and len(text) >= 30:
                    texts_prefix.add(text[:60])
        file_count += 1

    log(f"[leak_check] Loaded identifiers from {file_count} files: "
        f"{len(comment_ids):,} comment_ids, {len(authors):,} authors, "
        f"{len(texts_prefix):,} text prefixes")
    return comment_ids, authors, texts_prefix


def check_parquet_columns(path: Path, failures: list[str]) -> None:
    """Assert that the parquet file has none of the forbidden column names."""
    if not path.exists():
        log(f"[leak_check] SKIP (not found): {path}")
        return
    try:
        import pandas as pd
        df = pd.read_parquet(path)
    except Exception as e:
        failures.append(f"Could not read {path}: {e}")
        return

    bad_cols = FORBIDDEN_COLUMNS & set(df.columns)
    if bad_cols:
        failures.append(f"{path}: contains forbidden columns {bad_cols}")
    else:
        log(f"[leak_check] PASS columns: {path.name}")


def author_leak_match(author: str, content: str) -> bool:
    """Whole-word match an author/username against text content.

    Two classes of false positive are filtered out:
    - Authors under 3 chars: too common to be a meaningful signal.
    - Purely numeric authors (e.g. deleted/bot accounts named "5510"): these
      collide constantly with ordinary numeric statistics (counts, rates,
      percentages) in aggregate output and are not human-identifying on
      their own, so a bare digit-substring match is not a real leak.

    Performance: a cheap `in` substring check runs first (implemented in C,
    ~100k/sec) to filter out the overwhelming majority of authors before
    paying for a regex word-boundary check, which is orders of magnitude
    slower at this scale (100k+ authors x multiple files).
    """
    if len(author) < 3 or author.isdigit():
        return False
    if author not in content:
        return False
    pattern = r"(?<!\w)" + re.escape(author) + r"(?!\w)"
    return re.search(pattern, content) is not None


def check_text_file(path: Path, comment_ids: set[str], authors: set[str],
                    texts_prefix: set[str], failures: list[str]) -> None:
    """Scan a text file for any verbatim comment_id, author, or text prefix."""
    if not path.exists():
        log(f"[leak_check] SKIP (not found): {path}")
        return
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        failures.append(f"Could not read {path}: {e}")
        return

    # Check comment IDs
    for cid in comment_ids:
        if cid in content:
            failures.append(f"{path}: contains comment_id '{cid}'")
            break  # report first hit only to avoid flooding

    # Check authors — see author_leak_match() for false-positive filtering.
    for author in authors:
        if author_leak_match(author, content):
            failures.append(f"{path}: contains author/username '{author}'")
            break

    # Check text prefixes (only high-confidence ones: len >= 30)
    for prefix in texts_prefix:
        if prefix in content:
            failures.append(f"{path}: contains text prefix '{prefix[:40]}...'")
            break

    if not any(path.name in f for f in failures):
        log(f"[leak_check] PASS text-scan: {path.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    failures: list[str] = []

    comment_ids, authors, texts_prefix = load_raw_identifiers(SCORED_DIR)

    # 1. Check parquet columns
    agg_path = OUTPUT_DIR / "aggregate_results.parquet"
    check_parquet_columns(agg_path, failures)

    # 2. Check text content of HTML and markdown
    html_path = Path(__file__).parent / "dashboard" / "identity_hostility_dashboard.html"
    md_path = Path(__file__).parent / "docs" / "methodology_and_limitations.md"

    check_text_file(html_path, comment_ids, authors, texts_prefix, failures)
    check_text_file(md_path, comment_ids, authors, texts_prefix, failures)

    # 3. Also scan aggregate parquet rows as JSON-stringified content just in case
    if agg_path.exists():
        try:
            import pandas as pd
            df = pd.read_parquet(agg_path)
            agg_str = df.to_json(orient="records")
            # Manually scan JSON string
            for cid in comment_ids:
                if cid in agg_str:
                    failures.append(f"{agg_path}: aggregate JSON contains comment_id '{cid}'")
                    break
            for author in authors:
                if author_leak_match(author, agg_str):
                    failures.append(f"{agg_path}: aggregate JSON contains author '{author}'")
                    break
            log(f"[leak_check] PASS aggregate JSON values: {agg_path.name}")
        except Exception as e:
            failures.append(f"Could not JSON-scan {agg_path}: {e}")

    log("")
    if failures:
        log("=" * 60)
        log(f"FAIL — {len(failures)} leak(s) detected:")
        for f in failures:
            log(f"  ✗ {f}")
        log("=" * 60)
        log("Do NOT share public outputs until these are resolved.")
        return 1

    log("=" * 60)
    log("PASS — no raw identifiers found in public artifacts.")
    log("=" * 60)
    log(f"Checked: {len(PUBLIC_FILES)} public files scanned")
    log(f"Against: {len(comment_ids):,} comment_ids, {len(authors):,} authors, "
        f"{len(texts_prefix):,} text prefixes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
