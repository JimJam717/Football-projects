import sys
from lingua import Language, LanguageDetectorBuilder

# Supported languages to load: English, French, Dutch, Arabic, Spanish, Portuguese
languages = [
    Language.ENGLISH,
    Language.FRENCH,
    Language.DUTCH,
    Language.ARABIC,
    Language.SPANISH,
    Language.PORTUGUESE,
    Language.GERMAN
]
detector = LanguageDetectorBuilder.from_languages(*languages).build()

def detect_language(text):
    if len(text.strip()) < 20:
        return "short_text"
    try:
        lang = detector.detect_language_of(text)
        if lang is None:
            return "unknown"
        
        lang_code = lang.iso_code_639_1.name.lower()

        # Confidence filter for structurally similar languages
        if lang_code in ["en", "nl", "de", "af"]:
            confidences = detector.compute_language_confidence_values(text)
            top_confidence = 0.0
            for c in confidences:
                if c.language == lang:
                    top_confidence = c.value
                    break
            if top_confidence < 0.85:
                return "unknown"

        return lang_code
    except Exception as e:
        print(f"[lang_detector] error: {e}", file=sys.stderr)
        return "unknown"
if __name__ == "__main__":
    print(detect_language("This is a test"))
    print(detect_language("C'est un test"))
    print(detect_language("Dit is een test"))
    print(detect_language(""))
