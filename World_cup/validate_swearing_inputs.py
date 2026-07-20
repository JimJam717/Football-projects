import argparse
import sys

from swearing_pipeline import (
    MATCH_CONFIG_PATH,
    REPORT_DIR,
    TEAM_CONFIG_PATH,
    build_language_to_countries,
    build_unique_language_to_country,
    load_configs,
    match_subreddits,
    validate_configs,
    write_csv,
    write_json,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Validate Swearing World Cup pipeline inputs.")
    parser.add_argument("--match-config", default=MATCH_CONFIG_PATH)
    parser.add_argument("--team-config", default=TEAM_CONFIG_PATH)
    parser.add_argument("--write-reports", action="store_true")
    parser.add_argument("--show-subreddits", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    match_config, team_config = load_configs(args.match_config, args.team_config)
    errors, warnings, coverage = validate_configs(match_config, team_config)

    if args.write_reports:
        write_csv(REPORT_DIR / "attribution_coverage.csv", coverage)
        write_json(
            REPORT_DIR / "language_lookup.json",
            {
                "language_to_countries": build_language_to_countries(match_config, team_config),
                "tier2_unique_language_to_country": build_unique_language_to_country(
                    match_config, team_config
                ),
            },
        )
        if args.show_subreddits:
            rows = [
                {
                    "match_id": match["match_id"],
                    "team_a": match["team_a"],
                    "team_b": match["team_b"],
                    "subreddits": ";".join(match_subreddits(match, match_config, team_config)),
                }
                for match in match_config.get("matches") or []
            ]
            write_csv(REPORT_DIR / "collection_subreddits_by_match.csv", rows)

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    print(
        f"Validated {len(match_config.get('matches') or [])} matches and "
        f"{len(team_config.get('teams') or {})} team attribution records."
    )
    if args.write_reports:
        print(f"Wrote reports under {REPORT_DIR}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
