import json
import tempfile
import unittest
from pathlib import Path

import collect_swearing_data
import detect_language
from attribute_speaker import attribute_row
from detect_language import process_file as detect_process_file
from rank_champion import main as rank_main
from score_swearing import process_file as score_process_file
from swearing_pipeline import (
    build_coverage_report,
    build_subreddit_to_country,
    build_unique_language_to_country,
    iter_jsonl,
    validate_configs,
    write_json,
    write_jsonl,
)


class FakeIsoCode:
    name = "en"


class FakeLanguage:
    iso_code_639_1 = FakeIsoCode()


class FakeConfidence:
    def __init__(self, value):
        self.language = FakeLanguage()
        self.value = value


class FakeDetector:
    def compute_language_confidence_values(self, _text):
        return [FakeConfidence(0.95), FakeConfidence(0.02)]


def small_match_config():
    return {
        "team_codes": {
            "England": "eng",
            "Germany": "ger",
            "Spain": "esp",
            "Ghostland": "gho",
        },
        "matches": [
            {
                "match_id": "eng_vs_ger_test",
                "phase": "group_stage",
                "round": "Group Test",
                "date": "2026-06-11",
                "team_a": "England",
                "team_b": "Germany",
                "note": None,
            }
        ]
        * 100,
    }


def small_team_config():
    return {
        "neutral_subreddits": ["soccer"],
        "teams": {
            "eng": {
                "country_name": "England",
                "languages": ["English"],
                "language_codes": ["en"],
                "country_subreddits": ["ThreeLions"],
                "aliases": ["England"],
            },
            "ger": {
                "country_name": "Germany",
                "languages": ["German"],
                "language_codes": ["de"],
                "country_subreddits": ["bundesliga"],
                "aliases": ["Germany"],
            },
            "esp": {
                "country_name": "Spain",
                "languages": ["Spanish"],
                "language_codes": ["es"],
                "country_subreddits": [],
                "aliases": ["Spain"],
            },
            "gho": {
                "country_name": "Ghostland",
                "languages": ["English"],
                "language_codes": ["en"],
                "country_subreddits": [],
                "aliases": ["Ghostland"],
            },
        },
    }


class SwearingPipelineTests(unittest.TestCase):
    def test_validation_reports_duplicate_match_ids(self):
        errors, _warnings, _coverage = validate_configs(small_match_config(), small_team_config())
        self.assertTrue(any("duplicate match_id" in error for error in errors))

    def test_unique_language_excludes_shared_languages(self):
        unique = build_unique_language_to_country(small_match_config(), small_team_config())
        self.assertEqual(unique["de"], "Germany")
        self.assertNotIn("en", unique)
        self.assertNotIn("es", unique)

    def test_coverage_flags_no_subreddit_no_unique_language(self):
        coverage = build_coverage_report(small_match_config(), small_team_config())
        by_country = {row["country_name"]: row for row in coverage}
        self.assertEqual(by_country["Ghostland"]["status"], "insufficient_data")
        self.assertEqual(by_country["Spain"]["status"], "insufficient_data")
        self.assertEqual(by_country["Germany"]["status"], "eligible")

    def test_tier1_subreddit_precedes_language(self):
        team_config = small_team_config()
        row = {
            "subreddit": "ThreeLions",
            "detected_language": "de",
            "text": "Das ist ein Test.",
        }
        attributed = attribute_row(
            row,
            build_subreddit_to_country(team_config),
            build_unique_language_to_country(small_match_config(), team_config),
        )
        self.assertEqual(attributed["attributed_country"], "England")
        self.assertEqual(attributed["attribution_tier"], "tier1_subreddit")

    def test_neutral_unique_language_attributes(self):
        team_config = small_team_config()
        row = {
            "subreddit": "soccer",
            "detected_language": "de",
            "text": "Das ist ein Test.",
        }
        attributed = attribute_row(
            row,
            build_subreddit_to_country(team_config),
            build_unique_language_to_country(small_match_config(), team_config),
        )
        self.assertEqual(attributed["attributed_country"], "Germany")
        self.assertEqual(attributed["attribution_tier"], "tier2_language")

    def test_language_and_scoring_preserve_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_path = tmp_path / "raw.jsonl"
            language_path = tmp_path / "language.jsonl"
            scored_path = tmp_path / "scored.jsonl"
            write_jsonl(
                raw_path,
                [
                    {
                        "match_id": "m1",
                        "subreddit": "soccer",
                        "comment_id": "c1",
                        "author": "a",
                        "timestamp": 1,
                        "text": "This damn match is a test with enough words.",
                    }
                ],
            )
            detect_process_file(raw_path, language_path, FakeDetector())
            language_row = next(iter_jsonl(language_path))
            self.assertIn("detected_language", language_row)
            self.assertIn("detected_language_confidence", language_row)
            self.assertEqual(language_row["detected_language"], "en")
            language_row["attributed_country"] = "England"
            write_jsonl(language_path, [language_row])
            score_process_file(language_path, scored_path)
            scored_row = next(iter_jsonl(scored_path))
            self.assertEqual(scored_row["comment_id"], "c1")
            self.assertGreaterEqual(scored_row["swear_count"], 1)
            self.assertGreater(scored_row["word_count"], 0)

    def test_rank_excludes_insufficient_and_sorts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            match_path = tmp_path / "matches.json"
            team_path = tmp_path / "teams.json"
            scored_dir = tmp_path / "scored"
            out_dir = tmp_path / "leaderboard"
            scored_dir.mkdir()

            match_config = small_match_config()
            match_config["matches"] = [
                {
                    "match_id": f"m{i}",
                    "phase": "group_stage",
                    "round": "Group Test",
                    "date": "2026-06-11",
                    "team_a": "England",
                    "team_b": "Germany",
                    "note": None,
                }
                for i in range(100)
            ]
            write_json(match_path, match_config)
            write_json(team_path, small_team_config())
            write_jsonl(
                scored_dir / "m0.jsonl",
                [
                    {
                        "match_id": "m0",
                        "subreddit": "bundesliga",
                        "comment_id": "c1",
                        "author": "a",
                        "timestamp": 1,
                        "text": "fuck",
                        "detected_language": "en",
                        "attributed_country": "Germany",
                        "swear_count": 1,
                        "word_count": 10,
                    },
                    {
                        "match_id": "m0",
                        "subreddit": "soccer",
                        "comment_id": "c2",
                        "author": "b",
                        "timestamp": 1,
                        "text": "fuck",
                        "detected_language": "en",
                        "attributed_country": "Ghostland",
                        "swear_count": 99,
                        "word_count": 1,
                    },
                ],
            )

            import sys

            old_argv = sys.argv
            try:
                sys.argv = [
                    "rank_champion.py",
                    "--match-config",
                    str(match_path),
                    "--team-config",
                    str(team_path),
                    "--input-dir",
                    str(scored_dir),
                    "--output-dir",
                    str(out_dir),
                    "--min-comments",
                    "1",
                    "--min-words",
                    "1",
                ]
                self.assertEqual(rank_main(), 0)
            finally:
                sys.argv = old_argv

            rows = json.loads((out_dir / "swearing_leaderboard.json").read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["country_name"], "Germany")
            self.assertEqual(rows[0]["rank"], 1)

    def test_collection_uses_explicit_window_and_reports_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_path = tmp_path / "m1.jsonl"
            calls = []

            def fake_request_page(params):
                calls.append(params)
                return {"data": []}, None

            original_request_page = collect_swearing_data.request_page
            try:
                collect_swearing_data.request_page = fake_request_page
                with output_path.open("w", encoding="utf-8") as output_file:
                    result = collect_swearing_data.collect_match_subreddit(
                        {"match_id": "m1", "date": "2026-06-11"},
                        "soccer",
                        output_file,
                        set(),
                        36,
                        5000,
                        progress_enabled=False,
                    )
            finally:
                collect_swearing_data.request_page = original_request_page

            self.assertEqual(result["new_comments"], 0)
            self.assertEqual(result["stop_reason"], "exhaustion")
            self.assertEqual(result["window_start_utc"], "2026-06-11T00:00:00Z")
            self.assertEqual(result["window_end_utc"], "2026-06-12T12:00:00Z")
            self.assertEqual(calls[0]["after"], 1781136000)
            self.assertEqual(calls[0]["before"], 1781265600)

    def test_language_sharding_splits_files_without_overlap(self):
        files = [Path(f"m{i}.jsonl") for i in range(6)]
        shard_zero = detect_language.select_shard_files(files, 2, 0)
        shard_one = detect_language.select_shard_files(files, 2, 1)
        self.assertEqual([path.name for path in shard_zero], ["m0.jsonl", "m2.jsonl", "m4.jsonl"])
        self.assertEqual([path.name for path in shard_one], ["m1.jsonl", "m3.jsonl", "m5.jsonl"])


if __name__ == "__main__":
    unittest.main()
