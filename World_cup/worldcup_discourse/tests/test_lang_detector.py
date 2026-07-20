import unittest
from processing.lang_detector import detect_language

class TestLangDetector(unittest.TestCase):
    def test_english(self):
        text = "This is a great match!"
        self.assertEqual(detect_language(text), "en")
        
    def test_french(self):
        text = "C'est un match incroyable!"
        self.assertEqual(detect_language(text), "fr")
        
    def test_dutch(self):
        text = "Dit is een geweldige wedstrijd!"
        self.assertEqual(detect_language(text), "nl")

if __name__ == '__main__':
    unittest.main()
