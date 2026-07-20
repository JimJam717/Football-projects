"""
run_snapshot_pipeline.py
========================
Runs the four snapshot-report steps in sequence, stopping immediately if any
step exits with a non-zero return code.  After a clean run it prints the
modification timestamps and CSV row counts for the three key report files.

Usage (from worldcup_discourse/):
    python run_snapshot_pipeline.py
"""

import csv
import datetime
import os
import subprocess
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Each entry is the display label and the argument list for subprocess.
STEPS = [
    ("generate_sensitive_language_scan.py", [sys.executable, "generate_sensitive_language_scan.py"]),
    ("export_flagged_comments.py",          [sys.executable, "export_flagged_comments.py"]),
    ("generate_flagged_context_audit.py",   [sys.executable, "generate_flagged_context_audit.py"]),
    ("generate_basic_results.py",           [sys.executable, "generate_basic_results.py"]),
]

REPORT_DIR = os.path.join("reports", "phase2_basic_results")

REPORT_FILES = [
    "raw_volume_by_match.csv",
    "sensitive_language_overview.csv",
    "sentiment_by_match.csv",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_step(label: str, cmd: list[str]) -> None:
    """Run a single pipeline step; raise SystemExit on failure."""
    separator = "-" * 60
    print(f"\n{separator}")
    print(f"STEP: {label}")
    print(separator)

    result = subprocess.run(cmd, capture_output=False)   # let stdout/stderr stream live

    if result.returncode != 0:
        # Re-run capturing output so we can echo it cleanly in the error block,
        # but only if the first run didn't already print it.  Since we used
        # capture_output=False above, any output was already visible.  We
        # simply report the return code and exit.
        print(f"\n[ERROR] '{label}' exited with code {result.returncode}.", file=sys.stderr)
        print(       "[ERROR] No further steps will be run.", file=sys.stderr)
        sys.exit(result.returncode)

    print(f"\n[OK] {label} completed successfully.")


def csv_row_count(path: str) -> int:
    """Return the number of data rows in a CSV (header not counted)."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        rows = sum(1 for _ in reader)
    # subtract 1 for the header row; guard against empty files
    return max(rows - 1, 0)


def file_mtime(path: str) -> str:
    """Return the file's last-modified time as a human-readable local string."""
    ts = os.path.getmtime(path)
    dt = datetime.datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def print_report_summary() -> None:
    """Print timestamps and row counts for the three key report CSVs."""
    separator = "=" * 60
    print(f"\n{separator}")
    print("REPORT FILE SUMMARY")
    print(separator)

    any_missing = False
    for filename in REPORT_FILES:
        path = os.path.join(REPORT_DIR, filename)
        if not os.path.exists(path):
            print(f"  [MISSING] {filename}")
            any_missing = True
            continue

        mtime   = file_mtime(path)
        n_rows  = csv_row_count(path)
        print(f"  {filename}")
        print(f"    Modified : {mtime}")
        print(f"    Data rows: {n_rows}")

    if any_missing:
        print(
            "\n[WARNING] One or more expected report files were not found. "
            "Check that generate_basic_results.py completed without errors.",
            file=sys.stderr,
        )

    print(separator)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("SNAPSHOT PIPELINE")
    print(f"Started : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"CWD     : {os.getcwd()}")
    print("=" * 60)

    for label, cmd in STEPS:
        run_step(label, cmd)

    print("\n[ALL STEPS COMPLETE]")
    print_report_summary()


if __name__ == "__main__":
    main()
