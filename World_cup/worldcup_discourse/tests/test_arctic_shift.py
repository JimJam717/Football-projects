import unittest

from run_test_case import run_france_morocco_smoke_test


class TestArcticShift(unittest.TestCase):
    def test_france_morocco_smoke_test(self):
        summary = run_france_morocco_smoke_test(show_progress=True)

        self.assertGreater(summary["total_raw_records"], 0)
        self.assertGreater(summary["total_mentioned_records"], 0)
        self.assertGreater(summary["sentiment_scored_records"], 0)
        self.assertTrue(summary["lang_counts"])


if __name__ == "__main__":
    unittest.main()
