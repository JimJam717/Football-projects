"""
run_metrics_pipeline.py
=======================
Runs the post-sentiment metrics refresh in sequence.

Usage, from worldcup_discourse/:
    python run_metrics_pipeline.py

Default steps:
    1. generate_basic_results.py
    2. build_match_table.py
    3. test_flag_sentiment.py

Optional:
    python run_metrics_pipeline.py --include-group-effects

Only use --include-group-effects after filling outcome and nation in
reports/analysis/match_table.csv. Note that build_match_table.py rewrites
those columns blank, so this pipeline runs group effects only after the table
has just been rebuilt.
"""

import argparse
import subprocess
import sys


BASE_STEPS = [
    ("generate_basic_results.py", [sys.executable, "generate_basic_results.py"]),
    ("build_match_table.py", [sys.executable, "build_match_table.py"]),
    ("test_flag_sentiment.py", [sys.executable, "test_flag_sentiment.py"]),
]

GROUP_EFFECTS_STEP = (
    "test_group_effects.py",
    [sys.executable, "test_group_effects.py"],
)


def run_step(label, command):
    print("=" * 70, flush=True)
    print(f"STEP: {label}", flush=True)
    print("=" * 70, flush=True)

    result = subprocess.run(command)
    if result.returncode != 0:
        print(f"\n[ERROR] {label} exited with code {result.returncode}.", file=sys.stderr)
        print("[ERROR] Stopping metrics pipeline.", file=sys.stderr)
        return result.returncode

    print(f"\n[OK] {label} completed successfully.\n", flush=True)
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the post-sentiment metrics refresh pipeline."
    )
    parser.add_argument(
        "--include-group-effects",
        action="store_true",
        help="Also run test_group_effects.py after the core metrics steps.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    steps = list(BASE_STEPS)
    if args.include_group_effects:
        steps.append(GROUP_EFFECTS_STEP)

    print("Post-sentiment metrics pipeline", flush=True)
    print("Steps:", flush=True)
    for label, _ in steps:
        print(f"  - {label}", flush=True)
    print("", flush=True)

    for label, command in steps:
        exit_code = run_step(label, command)
        if exit_code:
            return exit_code

    print("=" * 70, flush=True)
    print("[ALL STEPS COMPLETE]", flush=True)
    print("Key outputs:", flush=True)
    print("  reports/phase2_basic_results/", flush=True)
    print("  reports/analysis/match_table.csv", flush=True)
    print("  reports/analysis/flag_sentiment_test.txt", flush=True)
    if args.include_group_effects:
        print("  reports/analysis/group_effects_test.txt", flush=True)
    print("=" * 70, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
