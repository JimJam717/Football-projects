"""
tests/test_flag_logic.py
Unit tests for flag_detection bucket/signal logic.
No I/O — all logic is tested with in-memory data.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import re
import pytest

from flag_detection import (
    _build_pattern,
    lexicon_hit,
    assign_bucket,
    assign_flag_source,
    BUCKET_ORDER,
)
from identity_common import is_model_supported, row_hash


# ---------------------------------------------------------------------------
# Lexicon matching
# ---------------------------------------------------------------------------

class TestLexiconHit:
    def setup_method(self):
        self.pattern = _build_pattern(["racist", "go back to", "third world"])

    def test_hit_exact(self):
        assert lexicon_hit("that was racist", self.pattern)

    def test_hit_multiword(self):
        assert lexicon_hit("go back to where you came from", self.pattern)

    def test_hit_case_insensitive(self):
        assert lexicon_hit("RACIST comment", self.pattern)
        assert lexicon_hit("Third World country", self.pattern)

    def test_no_hit(self):
        assert not lexicon_hit("great goal by the team", self.pattern)

    def test_empty_text(self):
        assert not lexicon_hit("", self.pattern)
        assert not lexicon_hit(None, self.pattern)


# ---------------------------------------------------------------------------
# Bucket assignment and precedence
# ---------------------------------------------------------------------------

class TestBucketAssignment:
    def test_racial_ethnic_takes_precedence_over_nationality(self):
        assert assign_bucket(True, True, True) == "racial_ethnic_flagged"

    def test_nationality_without_racial(self):
        assert assign_bucket(False, True, True) == "nationality_flagged"

    def test_model_unsupported_when_not_scored_and_no_lex(self):
        assert assign_bucket(False, False, False) == "model_unsupported"

    def test_unflagged_when_scored_and_no_hit(self):
        assert assign_bucket(False, False, True) == "unflagged"

    def test_racial_ethnic_wins_even_if_model_unsupported(self):
        # Lexicon hit on unsupported language should still surface racial_ethnic
        assert assign_bucket(True, False, False) == "racial_ethnic_flagged"

    def test_bucket_order_matches_constant(self):
        assert BUCKET_ORDER[0] == "racial_ethnic_flagged"
        assert BUCKET_ORDER[1] == "nationality_flagged"
        assert BUCKET_ORDER[2] == "model_unsupported"
        assert BUCKET_ORDER[3] == "unflagged"


# ---------------------------------------------------------------------------
# Flag source assignment
# ---------------------------------------------------------------------------

class TestFlagSource:
    def test_none_when_no_flags(self):
        assert assign_flag_source(False, False, False, False, False) == "none"

    def test_lexicon_only(self):
        assert assign_flag_source(True, False, True, False, False) == "lexicon"

    def test_model_only(self):
        assert assign_flag_source(True, False, False, False, True) == "model"

    def test_both(self):
        assert assign_flag_source(True, False, True, False, True) == "both"

    def test_nationality_lexicon(self):
        assert assign_flag_source(False, True, False, True, False) == "lexicon"


# ---------------------------------------------------------------------------
# Language gate
# ---------------------------------------------------------------------------

class TestLanguageGate:
    def test_supported_languages(self):
        for lang in ["en", "fr", "es", "it", "pt", "tr", "ru"]:
            assert is_model_supported(lang), f"{lang} should be supported"

    def test_unsupported_languages(self):
        for lang in ["de", "nl", "ar", "zh", "ja", "ko", "unknown", "short_text", None, ""]:
            assert not is_model_supported(lang), f"{lang} should NOT be supported"

    def test_case_insensitive(self):
        assert is_model_supported("EN")
        assert is_model_supported("Fr")


# ---------------------------------------------------------------------------
# Row hashing
# ---------------------------------------------------------------------------

class TestRowHash:
    def test_deterministic(self):
        assert row_hash("abc123") == row_hash("abc123")

    def test_different_ids_different_hashes(self):
        assert row_hash("abc123") != row_hash("def456")

    def test_output_is_hex_string(self):
        h = row_hash("test")
        assert isinstance(h, str)
        assert all(c in "0123456789abcdef" for c in h)

    def test_length(self):
        # We truncate to 24 chars
        assert len(row_hash("anything")) == 24
