import tempfile
import unittest
from pathlib import Path

from swearing_pipeline import load_json, write_jsonl
from swearing_tournament import (
    THIRD_PLACE_ASSIGNMENTS,
    aggregate_match_metrics,
    aggregate_top_swear_words,
    build_awards,
    build_groups,
    build_third_place_qualifiers,
    compare_teams,
    sort_teams,
)


def team(country, swears, comments=1000, qualified=True, group="A"):
    return {
        "country": country,
        "code": country[:3].lower(),
        "group": group,
        "comments": comments,
        "words": 10000,
        "swear_hits": int(swears * 10),
        "swears_per_1000_words": swears,
        "swears_per_100_comments": swears / 2,
        "rank": 1 if qualified else None,
        "qualified_for_rank": qualified,
        "sample_status": "qualified" if qualified else "low_comments",
        "data_status": "qualified" if qualified else "low_sample",
    }


class SwearingTournamentTests(unittest.TestCase):
    def test_extracts_current_world_cup_groups(self):
        match_config = load_json("worldcup2026_match_config.json")
        leaderboard = load_json("data/processed/leaderboard/swearing_leaderboard.json")
        groups, _lookup = build_groups(match_config, leaderboard)
        self.assertEqual(len(groups), 12)
        self.assertEqual(groups[0]["group"], "A")
        self.assertEqual([row["country"] for row in groups[0]["teams"]], ["Mexico", "South Africa", "Czechia", "South Korea"])

    def test_qualified_first_ordering_beats_low_sample_and_missing(self):
        qualified = team("Qualified", 1.0, qualified=True)
        low_sample = team("Low Sample", 99.0, qualified=False)
        missing = {
            "country": "Missing",
            "comments": 0,
            "swears_per_1000_words": 100.0,
            "swears_per_100_comments": 100.0,
            "data_status": "missing",
        }
        ordered = sort_teams([missing, low_sample, qualified])
        self.assertEqual([row["country"] for row in ordered], ["Qualified", "Low Sample", "Missing"])
        self.assertLess(compare_teams(qualified, low_sample), 0)

    def test_current_third_place_assignment_lookup(self):
        match_config = load_json("worldcup2026_match_config.json")
        leaderboard = load_json("data/processed/leaderboard/swearing_leaderboard.json")
        groups, _lookup = build_groups(match_config, leaderboard)
        third_place = build_third_place_qualifiers(groups)
        self.assertEqual(third_place["qualifier_group_key"], "ABCDGHIL")
        self.assertIn("ABCDGHIL", THIRD_PLACE_ASSIGNMENTS)
        self.assertEqual(third_place["assignment"]["1A"], "H")
        self.assertEqual(third_place["assignment"]["1G"], "A")
        self.assertEqual(len(third_place["qualified"]), 8)

    def test_award_winners_and_tiebreakers(self):
        teams = [
            team("Hot", 5.0, comments=1000, qualified=True),
            team("Clean", 0.5, comments=1000, qualified=True),
            team("Disciplined", 0.7, comments=1000, qualified=True),
            team("Tiny Fire", 30.0, comments=10, qualified=False),
        ]
        teams[2]["swears_per_100_comments"] = 0.1
        awards = {award["id"]: award for award in build_awards(teams, [], [], {})}
        self.assertEqual(awards["golden_ball"]["winner"]["country"], "Hot")
        self.assertEqual(awards["golden_glove"]["winner"]["country"], "Clean")
        self.assertEqual(awards["fair_play"]["winner"]["country"], "Disciplined")
        self.assertEqual(awards["breakthrough"]["winner"]["country"], "Tiny Fire")
        self.assertIsNone(awards["passion_index"]["winner"])

    def test_match_metric_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            scored_dir = Path(tmp)
            write_jsonl(
                scored_dir / "m1.jsonl",
                [
                    {"match_id": "m1", "swear_count": 2, "word_count": 100},
                    {"match_id": "m1", "swear_count": 1, "word_count": 50},
                ],
            )
            match_config = {
                "matches": [
                    {
                        "match_id": "m1",
                        "round": "Group A",
                        "team_a": "Alpha",
                        "team_b": "Beta",
                    }
                ]
            }
            metrics = aggregate_match_metrics(match_config, scored_dir)
            self.assertEqual(metrics[0]["match_id"], "m1")
            self.assertEqual(metrics[0]["comments"], 2)
            self.assertEqual(metrics[0]["swear_hits"], 3)
            self.assertEqual(metrics[0]["swears_per_1000_words"], 20.0)

    def test_top_swear_word_uses_lexicons_not_broad_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            scored_dir = Path(tmp)
            write_jsonl(
                scored_dir / "m1.jsonl",
                [
                    {
                        "match_id": "m1",
                        "detected_language": "en",
                        "text": "fuck hate shit fuck",
                    },
                    {
                        "match_id": "m1",
                        "detected_language": "es",
                        "text": "mierda hate",
                    },
                    {
                        "match_id": "m1",
                        "detected_language": "unknown",
                        "text": "fuck",
                    },
                ],
            )
            counts = aggregate_top_swear_words(scored_dir)
            by_word = {row["word"]: row["count"] for row in counts}
            self.assertEqual(by_word["fuck"], 2)
            self.assertEqual(by_word["shit"], 1)
            self.assertEqual(by_word["mierda"], 1)
            self.assertNotIn("hate", by_word)


if __name__ == "__main__":
    unittest.main()
