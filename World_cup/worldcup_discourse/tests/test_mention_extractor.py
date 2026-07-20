import unittest
from processing.mention_extractor import extract_mentions

class TestMentionExtractor(unittest.TestCase):
    def setUp(self):
        self.squads = {
            "england": [
                {"name": "Bukayo Saka", "aliases": ["Saka"]},
                {"name": "Harry Kane", "aliases": ["Kane", "HurriKane"]}
            ],
            "france": [
                {"name": "Kylian Mbappé", "aliases": ["Mbappe"]}
            ]
        }
        
    def test_exact_name_match(self):
        text = "I think Bukayo Saka will score today."
        mentions = extract_mentions(text, self.squads)
        self.assertEqual(len(mentions), 1)
        self.assertEqual(mentions[0]["name"], "Bukayo Saka")
        self.assertEqual(mentions[0]["nation"], "england")

    def test_alias_match(self):
        text = "Saka is the best right winger."
        mentions = extract_mentions(text, self.squads)
        self.assertEqual(len(mentions), 1)
        self.assertEqual(mentions[0]["name"], "Bukayo Saka")
        
    def test_case_insensitivity(self):
        text = "kylian mbappé is fast."
        mentions = extract_mentions(text, self.squads)
        self.assertEqual(len(mentions), 1)
        self.assertEqual(mentions[0]["name"], "Kylian Mbappé")
        
    def test_multi_player_match(self):
        text = "Kane and Saka are a great duo."
        mentions = extract_mentions(text, self.squads)
        self.assertEqual(len(mentions), 2)
        names = [m["name"] for m in mentions]
        self.assertIn("Bukayo Saka", names)
        self.assertIn("Harry Kane", names)
        
    def test_no_match(self):
        text = "Ronaldo is the goat."
        mentions = extract_mentions(text, self.squads)
        self.assertEqual(len(mentions), 0)
        
    def test_substring_not_matched(self):
        # Osaka should not match Saka
        text = "Naomi Osaka plays tennis."
        mentions = extract_mentions(text, self.squads)
        self.assertEqual(len(mentions), 0)

if __name__ == '__main__':
    unittest.main()
