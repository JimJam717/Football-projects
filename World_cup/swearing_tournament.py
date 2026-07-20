import argparse
from collections import Counter, defaultdict
from functools import cmp_to_key
from pathlib import Path

from swearing_pipeline import (
    LEADERBOARD_DIR,
    MATCH_CONFIG_PATH,
    SCORED_DIR,
    LEXICONS,
    canonical_language_code,
    iter_jsonl,
    load_json,
    words,
    write_json,
)


TOURNAMENT_OUTPUT_PATH = LEADERBOARD_DIR / "swearing_tournament.json"
MATCH_METRICS_OUTPUT_PATH = LEADERBOARD_DIR / "swearing_match_metrics.json"
POPULATION_PATH = Path("data/context/country_population.json")

GROUP_IDS = tuple("ABCDEFGHIJKL")

ROUND32_SLOTS = [
    ("M73", "Round of 32", "2A", "2B"),
    ("M74", "Round of 32", "1E", "third:1E"),
    ("M75", "Round of 32", "1F", "2C"),
    ("M76", "Round of 32", "1C", "2F"),
    ("M77", "Round of 32", "1I", "third:1I"),
    ("M78", "Round of 32", "2E", "2I"),
    ("M79", "Round of 32", "1A", "third:1A"),
    ("M80", "Round of 32", "1L", "third:1L"),
    ("M81", "Round of 32", "1D", "third:1D"),
    ("M82", "Round of 32", "1G", "third:1G"),
    ("M83", "Round of 32", "2K", "2L"),
    ("M84", "Round of 32", "1H", "2J"),
    ("M85", "Round of 32", "1B", "third:1B"),
    ("M86", "Round of 32", "1J", "2H"),
    ("M87", "Round of 32", "1K", "third:1K"),
    ("M88", "Round of 32", "2D", "2G"),
]

KNOCKOUT_ROUNDS = [
    (
        "Round of 16",
        [
            ("M89", "M73", "M75"),
            ("M90", "M74", "M77"),
            ("M91", "M76", "M78"),
            ("M92", "M79", "M80"),
            ("M93", "M83", "M84"),
            ("M94", "M81", "M82"),
            ("M95", "M86", "M88"),
            ("M96", "M85", "M87"),
        ],
    ),
    (
        "Quarterfinal",
        [
            ("M97", "M89", "M90"),
            ("M98", "M93", "M94"),
            ("M99", "M91", "M92"),
            ("M100", "M95", "M96"),
        ],
    ),
    ("Semifinal", [("M101", "M97", "M98"), ("M102", "M99", "M100")]),
    ("Final", [("M104", "M101", "M102")]),
]

# This profanity tournament currently produces third-place qualifiers from
# groups A, B, C, D, G, H, I, and L. Keep this table isolated so more Annex C
# rows can be added without changing the derivation or UI.
THIRD_PLACE_ASSIGNMENTS = {
    "ABCDGHIL": {
        "1A": "H",
        "1B": "G",
        "1D": "B",
        "1E": "C",
        "1G": "A",
        "1I": "D",
        "1K": "L",
        "1L": "I",
    }
}


def parse_args():
    parser = argparse.ArgumentParser(description="Build the animated Swearing World Cup data.")
    parser.add_argument("--match-config", default=MATCH_CONFIG_PATH)
    parser.add_argument("--leaderboard", default=LEADERBOARD_DIR / "swearing_leaderboard.json")
    parser.add_argument("--scored-dir", default=SCORED_DIR)
    parser.add_argument("--population", default=POPULATION_PATH)
    parser.add_argument("--tournament-output", default=TOURNAMENT_OUTPUT_PATH)
    parser.add_argument("--match-output", default=MATCH_METRICS_OUTPUT_PATH)
    return parser.parse_args()


def data_priority(team):
    if team.get("data_status") == "qualified":
        return 2
    if team.get("data_status") == "low_sample":
        return 1
    return 0


def compare_teams(left, right):
    fields = [
        (data_priority(left), data_priority(right)),
        (float(left.get("swears_per_1000_words") or 0), float(right.get("swears_per_1000_words") or 0)),
        (float(left.get("swears_per_100_comments") or 0), float(right.get("swears_per_100_comments") or 0)),
        (int(left.get("comments") or 0), int(right.get("comments") or 0)),
    ]
    for left_value, right_value in fields:
        if left_value > right_value:
            return -1
        if left_value < right_value:
            return 1

    left_country = str(left.get("country") or left.get("country_name") or "")
    right_country = str(right.get("country") or right.get("country_name") or "")
    if left_country < right_country:
        return -1
    if left_country > right_country:
        return 1
    return 0


def sort_teams(teams):
    return sorted(teams, key=cmp_to_key(compare_teams))


def team_from_leaderboard(country, code, leaderboard_by_country, group=None):
    row = leaderboard_by_country.get(country)
    if not row:
        return {
            "country": country,
            "code": code,
            "group": group,
            "comments": 0,
            "words": 0,
            "swear_hits": 0,
            "swears_per_1000_words": 0.0,
            "swears_per_100_comments": 0.0,
            "rank": None,
            "qualified_for_rank": False,
            "sample_status": "missing",
            "data_status": "missing",
        }

    qualified = bool(row.get("qualified_for_rank"))
    return {
        "country": row.get("country_name") or country,
        "code": row.get("team_code") or code,
        "group": group,
        "comments": int(row.get("comments") or 0),
        "words": int(row.get("words") or 0),
        "swear_hits": int(row.get("swear_hits") or 0),
        "swears_per_1000_words": float(row.get("swears_per_1000_words") or 0.0),
        "swears_per_100_comments": float(row.get("swears_per_100_comments") or 0.0),
        "rank": row.get("rank") or None,
        "qualified_for_rank": qualified,
        "sample_status": row.get("sample_status") or "unknown",
        "data_status": "qualified" if qualified else "low_sample",
    }


def extract_group_members(match_config):
    groups = defaultdict(list)
    seen = set()
    for match in match_config.get("matches") or []:
        if match.get("phase") != "group_stage":
            continue
        group_id = str(match.get("round") or "").split()[-1]
        for side in ("team_a", "team_b"):
            country = match.get(side)
            key = (group_id, country)
            if country and key not in seen:
                seen.add(key)
                groups[group_id].append(country)
    return {group_id: groups[group_id] for group_id in GROUP_IDS if group_id in groups}


def build_groups(match_config, leaderboard_rows):
    leaderboard_by_country = {row.get("country_name"): row for row in leaderboard_rows}
    code_by_country = match_config.get("team_codes") or {}
    groups = []
    source_lookup = {}

    for group_id, countries in extract_group_members(match_config).items():
        teams = [
            team_from_leaderboard(
                country,
                code_by_country.get(country),
                leaderboard_by_country,
                group=group_id,
            )
            for country in countries
        ]
        ordered = sort_teams(teams)
        for index, team in enumerate(ordered, start=1):
            team["group_position"] = index
            source_lookup[f"{index}{group_id}"] = team
        groups.append(
            {
                "group": group_id,
                "teams": ordered,
                "top_two": ordered[:2],
                "third_place": ordered[2] if len(ordered) > 2 else None,
            }
        )

    return groups, source_lookup


def build_third_place_qualifiers(groups):
    third_place = [group["third_place"] for group in groups if group.get("third_place")]
    ordered = sort_teams(third_place)
    qualifiers = ordered[:8]
    qualifier_groups = "".join(sorted(team["group"] for team in qualifiers))
    assignment = THIRD_PLACE_ASSIGNMENTS.get(qualifier_groups)
    if assignment is None:
        raise ValueError(
            f"No third-place assignment configured for groups {qualifier_groups}. "
            "Add the Annex C row to THIRD_PLACE_ASSIGNMENTS."
        )
    return {
        "qualifier_group_key": qualifier_groups,
        "all": ordered,
        "qualified": qualifiers,
        "assignment": assignment,
    }


def team_ref(team):
    if team is None:
        return None
    return {
        "country": team.get("country"),
        "code": team.get("code"),
        "group": team.get("group"),
        "data_status": team.get("data_status"),
        "sample_status": team.get("sample_status"),
        "rank": team.get("rank"),
        "comments": team.get("comments"),
        "words": team.get("words"),
        "swear_hits": team.get("swear_hits"),
        "swears_per_1000_words": team.get("swears_per_1000_words"),
        "swears_per_100_comments": team.get("swears_per_100_comments"),
    }


def resolve_source(source, source_lookup, third_place):
    if source.startswith("third:"):
        slot = source.split(":", 1)[1]
        group_id = third_place["assignment"][slot]
        return source_lookup[f"3{group_id}"], f"3{group_id}"
    return source_lookup[source], source


def build_match(slot, round_name, team_a, team_b, source_a, source_b):
    winner = team_a if compare_teams(team_a, team_b) <= 0 else team_b
    loser = team_b if winner is team_a else team_a
    margin = abs(
        float(team_a.get("swears_per_1000_words") or 0)
        - float(team_b.get("swears_per_1000_words") or 0)
    )
    warnings = []
    for team in (team_a, team_b):
        if team.get("data_status") != "qualified":
            warnings.append(f"{team.get('country')}: {team.get('sample_status')}")
    return {
        "slot": slot,
        "round": round_name,
        "source_a": source_a,
        "source_b": source_b,
        "team_a": team_ref(team_a),
        "team_b": team_ref(team_b),
        "winner": team_ref(winner),
        "loser": team_ref(loser),
        "margin": round(margin, 6),
        "warnings": warnings,
    }


def build_bracket(source_lookup, third_place):
    matches_by_slot = {}
    rounds = []

    round32 = []
    for slot, round_name, source_a, source_b in ROUND32_SLOTS:
        team_a, resolved_a = resolve_source(source_a, source_lookup, third_place)
        team_b, resolved_b = resolve_source(source_b, source_lookup, third_place)
        match = build_match(slot, round_name, team_a, team_b, resolved_a, resolved_b)
        matches_by_slot[slot] = match
        round32.append(match)
    rounds.append({"round": "Round of 32", "matches": round32})

    for round_name, round_slots in KNOCKOUT_ROUNDS:
        matches = []
        for slot, previous_a, previous_b in round_slots:
            team_a = matches_by_slot[previous_a]["winner"]
            team_b = matches_by_slot[previous_b]["winner"]
            match = build_match(slot, round_name, team_a, team_b, f"W{previous_a}", f"W{previous_b}")
            matches_by_slot[slot] = match
            matches.append(match)
        rounds.append({"round": round_name, "matches": matches})

    return rounds, matches_by_slot["M104"]["winner"]


def aggregate_match_metrics(match_config, scored_dir):
    match_lookup = {match.get("match_id"): match for match in match_config.get("matches") or []}
    totals = defaultdict(Counter)
    for input_path in sorted(Path(scored_dir).glob("*.jsonl")):
        for row in iter_jsonl(input_path):
            match_id = row.get("match_id") or input_path.stem
            totals[match_id]["comments"] += 1
            totals[match_id]["words"] += int(row.get("word_count") or 0)
            totals[match_id]["swear_hits"] += int(row.get("swear_count") or 0)

    metrics = []
    for match_id, counts in sorted(totals.items()):
        match = match_lookup.get(match_id, {})
        words_total = counts["words"]
        comments = counts["comments"]
        swear_hits = counts["swear_hits"]
        metrics.append(
            {
                "match_id": match_id,
                "round": match.get("round"),
                "team_a": match.get("team_a"),
                "team_b": match.get("team_b"),
                "comments": comments,
                "words": words_total,
                "swear_hits": swear_hits,
                "swears_per_1000_words": round((swear_hits / words_total) * 1000, 6)
                if words_total
                else 0.0,
                "swears_per_100_comments": round((swear_hits / comments) * 100, 6)
                if comments
                else 0.0,
            }
        )
    metrics.sort(key=lambda row: (row["swears_per_1000_words"], row["swears_per_100_comments"]), reverse=True)
    return metrics


def aggregate_top_swear_words(scored_dir):
    counts = Counter()
    for input_path in sorted(Path(scored_dir).glob("*.jsonl")):
        for row in iter_jsonl(input_path):
            lexicon = LEXICONS.get(canonical_language_code(row.get("detected_language")), set())
            if not lexicon:
                continue
            for token in words(row.get("text")):
                if token in lexicon:
                    counts[token] += 1
    return [{"word": word, "count": count} for word, count in counts.most_common(25)]


def load_population(path):
    path = Path(path)
    if not path.exists():
        return {}
    payload = load_json(path)
    if isinstance(payload, list):
        return {row["country"]: row["population"] for row in payload}
    return payload


def build_awards(teams, match_metrics, top_swear_words, population=None):
    population = population or {}
    qualified = [team for team in teams if team.get("data_status") == "qualified"]
    low_sample = [team for team in teams if team.get("data_status") == "low_sample"]

    def award_team(award_id, label, metric, winner, note):
        return {
            "id": award_id,
            "label": label,
            "winner": team_ref(winner) if winner else None,
            "metric": metric,
            "value": winner.get(metric) if winner and metric in winner else None,
            "eligibility_note": note,
        }

    awards = [
        award_team(
            "golden_ball",
            "Golden Ball",
            "swears_per_1000_words",
            max(qualified, key=lambda row: row["swears_per_1000_words"], default=None),
            "Highest swear hits per 1,000 words among qualified teams.",
        ),
        award_team(
            "golden_glove",
            "Golden Glove",
            "swears_per_1000_words",
            min(qualified, key=lambda row: row["swears_per_1000_words"], default=None),
            "Lowest swear hits per 1,000 words among qualified teams.",
        ),
        award_team(
            "fair_play",
            "Fair Play Award",
            "swears_per_100_comments",
            min(qualified, key=lambda row: row["swears_per_100_comments"], default=None),
            "Lowest swear hits per 100 comments among qualified teams.",
        ),
        award_team(
            "breakthrough",
            "Breakthrough Award",
            "swears_per_1000_words",
            max(low_sample, key=lambda row: row["swears_per_1000_words"], default=None),
            "Highest swear hits per 1,000 words among low-sample teams; unranked.",
        ),
    ]

    passion_rows = []
    if population:
        max_population = max(float(value or 0) for value in population.values())
        if max_population:
            for team in qualified:
                value = float(population.get(team["country"]) or 0)
                if value <= 0:
                    continue
                candidate = dict(team)
                candidate["passion_index"] = round(
                    candidate["swears_per_1000_words"] / (value / max_population),
                    6,
                )
                passion_rows.append(candidate)
    awards.append(
        award_team(
            "passion_index",
            "Passion Index",
            "passion_index",
            max(passion_rows, key=lambda row: row["passion_index"], default=None),
            "Enabled only when data/context/country_population.json is present.",
        )
    )

    top_match = match_metrics[0] if match_metrics else None
    awards.append(
        {
            "id": "top_swear_match",
            "label": "Top Swear Match",
            "winner": top_match,
            "metric": "swears_per_1000_words",
            "value": top_match.get("swears_per_1000_words") if top_match else None,
            "eligibility_note": "Highest match-level swear hits per 1,000 words across scored comments.",
        }
    )

    top_word = top_swear_words[0] if top_swear_words else None
    awards.append(
        {
            "id": "top_swear_word",
            "label": "Top Swear Word",
            "winner": top_word,
            "metric": "count",
            "value": top_word.get("count") if top_word else None,
            "eligibility_note": "Most frequent exact lexicon swear token across scored comments.",
        }
    )
    return awards


def build_tournament_data(match_config, leaderboard_rows, scored_dir=SCORED_DIR, population_path=POPULATION_PATH):
    groups, source_lookup = build_groups(match_config, leaderboard_rows)
    third_place = build_third_place_qualifiers(groups)
    bracket, champion = build_bracket(source_lookup, third_place)
    match_metrics = aggregate_match_metrics(match_config, scored_dir)
    top_swear_words = aggregate_top_swear_words(scored_dir)
    all_teams = [team for group in groups for team in group["teams"]]
    awards = build_awards(all_teams, match_metrics, top_swear_words, load_population(population_path))

    return {
        "title": "Animated Swearing World Cup",
        "methodology_note": (
            "Subreddit-identity fanbase ranking. Qualified teams meet the minimum sample; "
            "low-sample teams are shown but unranked."
        ),
        "groups": groups,
        "third_place": third_place,
        "bracket": bracket,
        "champion": champion,
        "awards": awards,
        "top_swear_words": top_swear_words,
        "match_metrics": match_metrics,
    }


def main():
    args = parse_args()
    match_config = load_json(args.match_config)
    leaderboard_rows = load_json(args.leaderboard)
    tournament = build_tournament_data(
        match_config,
        leaderboard_rows,
        scored_dir=args.scored_dir,
        population_path=args.population,
    )
    write_json(args.tournament_output, tournament)
    write_json(args.match_output, tournament["match_metrics"])
    print(f"Wrote {args.tournament_output}")
    print(f"Wrote {args.match_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
