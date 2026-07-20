import argparse
from collections import Counter
from pathlib import Path

from swearing_pipeline import DATA_COLLECTED_DIR, LANGUAGE_DIR, iter_jsonl, validate_phase_fields, write_json, write_jsonl


LINGUA_LANGUAGE_NAMES = {
    "af": "AFRIKAANS",
    "ar": "ARABIC",
    "bs": "BOSNIAN",
    "cs": "CZECH",
    "de": "GERMAN",
    "en": "ENGLISH",
    "es": "SPANISH",
    "fa": "PERSIAN",
    "fr": "FRENCH",
    "hr": "CROATIAN",
    "ht": "HAITIAN_CREOLE",
    "it": "ITALIAN",
    "ja": "JAPANESE",
    "ko": "KOREAN",
    "nl": "DUTCH",
    "no": "BOKMAL",
    "pap": "PAPIAMENTO",
    "pt": "PORTUGUESE",
    "sv": "SWEDISH",
    "tr": "TURKISH",
    "uz": "UZBEK",
    "zu": "ZULU",
}

DEFAULT_MIN_CONFIDENCE = 0.65
DEFAULT_MIN_MARGIN = 0.12
MIN_TEXT_CHARS = 20
MODEL_NAME = "lingua-language-detector"


class MissingLinguaError(RuntimeError):
    pass


def load_lingua_languages():
    try:
        from lingua import Language
    except ImportError as exc:
        raise MissingLinguaError(
            "lingua-language-detector is required for accurate language detection. "
            "Install it with: python -m pip install lingua-language-detector"
        ) from exc

    languages = []
    unsupported = {}
    for code, language_name in LINGUA_LANGUAGE_NAMES.items():
        language = getattr(Language, language_name, None)
        if language is None:
            unsupported[code] = language_name
            continue
        languages.append(language)
    if not languages:
        raise MissingLinguaError("No configured Lingua languages are available.")
    return languages, unsupported


def build_lingua_detector():
    try:
        from lingua import LanguageDetectorBuilder
    except ImportError as exc:
        raise MissingLinguaError(
            "lingua-language-detector is required for accurate language detection. "
            "Install it with: python -m pip install lingua-language-detector"
        ) from exc

    languages, unsupported = load_lingua_languages()
    detector = LanguageDetectorBuilder.from_languages(*languages).build()
    return detector, unsupported


def language_code(language):
    iso_code = getattr(language, "iso_code_639_1", None)
    if iso_code is None:
        return str(language.name).lower()
    return iso_code.name.lower()


def detect_language_detail(text, detector, min_confidence=DEFAULT_MIN_CONFIDENCE, min_margin=DEFAULT_MIN_MARGIN):
    stripped = str(text or "").strip()
    if len(stripped) < MIN_TEXT_CHARS:
        return {
            "detected_language": "short_text",
            "detected_language_confidence": 0.0,
            "language_confidence_margin": 0.0,
            "language_detection_model": MODEL_NAME,
        }

    confidences = list(detector.compute_language_confidence_values(stripped))
    if not confidences:
        return {
            "detected_language": "unknown",
            "detected_language_confidence": 0.0,
            "language_confidence_margin": 0.0,
            "language_detection_model": MODEL_NAME,
        }

    top = confidences[0]
    runner_up = confidences[1] if len(confidences) > 1 else None
    top_confidence = float(top.value)
    margin = top_confidence - (float(runner_up.value) if runner_up else 0.0)
    detected = language_code(top.language)
    if top_confidence < min_confidence or margin < min_margin:
        detected = "unknown"

    return {
        "detected_language": detected,
        "detected_language_confidence": round(top_confidence, 6),
        "language_confidence_margin": round(margin, 6),
        "language_detection_model": MODEL_NAME,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Append high-confidence Lingua language detection to collected comments.")
    parser.add_argument("--input-dir", default=DATA_COLLECTED_DIR)
    parser.add_argument("--output-dir", default=LANGUAGE_DIR)
    parser.add_argument("--match-id")
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    parser.add_argument("--min-margin", type=float, default=DEFAULT_MIN_MARGIN)
    parser.add_argument("--summary-path", default=Path(LANGUAGE_DIR) / "language_detection_summary.json")
    return parser.parse_args()


def process_file(input_path, output_path, detector, min_confidence=DEFAULT_MIN_CONFIDENCE, min_margin=DEFAULT_MIN_MARGIN):
    rows = []
    counts = Counter()
    for row in iter_jsonl(input_path):
        validate_phase_fields(
            row,
            ["match_id", "subreddit", "comment_id", "author", "timestamp", "text"],
            input_path,
        )
        output = dict(row)
        detail = detect_language_detail(
            output.get("text"),
            detector,
            min_confidence=min_confidence,
            min_margin=min_margin,
        )
        output.update(detail)
        counts[output["detected_language"]] += 1
        rows.append(output)
    write_jsonl(output_path, rows)
    return len(rows), counts


def select_shard_files(files, shard_count, shard_index):
    return [
        path
        for index, path in enumerate(files)
        if index % shard_count == shard_index
    ]


def main():
    args = parse_args()
    if args.shard_count < 1:
        print("ERROR: --shard-count must be at least 1")
        return 1
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        print("ERROR: --shard-index must be between 0 and shard-count - 1")
        return 1
    if args.match_id and args.shard_count != 1:
        print("ERROR: use either --match-id or sharding, not both")
        return 1

    try:
        detector, unsupported = build_lingua_detector()
    except MissingLinguaError as exc:
        print(f"ERROR: {exc}")
        return 1

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    files = sorted(input_dir.glob("*.jsonl"))
    if args.match_id:
        files = [input_dir / f"{args.match_id}.jsonl"]
    elif args.shard_count > 1:
        files = select_shard_files(files, args.shard_count, args.shard_index)

    total = 0
    language_counts = Counter()
    file_counts = {}
    for input_path in files:
        if not input_path.exists():
            continue
        count, counts = process_file(
            input_path,
            output_dir / input_path.name,
            detector,
            min_confidence=args.min_confidence,
            min_margin=args.min_margin,
        )
        total += count
        language_counts.update(counts)
        file_counts[input_path.name] = count
        print(f"{input_path.name}: language tagged {count} comments")

    summary_path = Path(args.summary_path)
    default_summary_path = Path(LANGUAGE_DIR) / "language_detection_summary.json"
    if args.shard_count > 1 and summary_path == default_summary_path:
        summary_path = Path(LANGUAGE_DIR) / f"language_detection_summary_shard_{args.shard_index}_of_{args.shard_count}.json"

    write_json(
        summary_path,
        {
            "model": MODEL_NAME,
            "min_confidence": args.min_confidence,
            "min_margin": args.min_margin,
            "shard_count": args.shard_count,
            "shard_index": args.shard_index,
            "total_comments": total,
            "language_counts": dict(sorted(language_counts.items())),
            "file_counts": file_counts,
            "unsupported_requested_lingua_languages": unsupported,
        },
    )
    if unsupported:
        print(f"WARNING: Lingua did not expose these requested languages: {unsupported}")
    print(f"Total language tagged comments: {total}")
    print(f"Wrote summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
