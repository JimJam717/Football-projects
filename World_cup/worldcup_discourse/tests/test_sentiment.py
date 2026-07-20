import unittest
from processing.sentiment import score_sentiment

class TestSentiment(unittest.TestCase):
    def test_positive(self):
        text = "I absolutely love how the team played today. Fantastic performance!"
        result = score_sentiment(text)
        self.assertEqual(result["label"], "positive")
        self.assertGreater(result["score"], 0.5)

    def test_negative(self):
        text = "This was the worst match I've ever seen. Complete disaster."
        result = score_sentiment(text)
        self.assertEqual(result["label"], "negative")
        self.assertGreater(result["score"], 0.5)

    def test_neutral(self):
        text = "The match ended in a 1-1 draw."
        result = score_sentiment(text)
        self.assertEqual(result["label"], "neutral")
        self.assertGreater(result["score"], 0.5)

if __name__ == '__main__':
    unittest.main()
