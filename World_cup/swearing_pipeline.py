import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


MATCH_CONFIG_PATH = Path("worldcup2026_match_config.json")
TEAM_CONFIG_PATH = Path("worldcup2026_team_attribution_config.json")
DATA_COLLECTED_DIR = Path("data/collected")
DATA_PROCESSED_DIR = Path("data/processed")
LANGUAGE_DIR = DATA_PROCESSED_DIR / "language"
ATTRIBUTED_DIR = DATA_PROCESSED_DIR / "attributed"
SCORED_DIR = DATA_PROCESSED_DIR / "scored"
LEADERBOARD_DIR = DATA_PROCESSED_DIR / "leaderboard"
REPORT_DIR = DATA_PROCESSED_DIR / "reports"

EXPECTED_MATCH_COUNT = 100
SHARED_TIER2_LANGUAGE_CODES = {"ar", "en", "es", "fr", "pt"}
WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-žА-Яа-я0-9']+", re.UNICODE)


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def iter_jsonl(path):
    path = Path(path)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSON: {exc}") from exc


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_configs(match_config_path=MATCH_CONFIG_PATH, team_config_path=TEAM_CONFIG_PATH):
    return load_json(match_config_path), load_json(team_config_path)


def team_code_by_name(match_config):
    return dict(match_config.get("team_codes") or {})


def team_names_in_matches(match_config):
    names = set()
    for match in match_config.get("matches") or []:
        names.add(match.get("team_a"))
        names.add(match.get("team_b"))
    return {name for name in names if name}


def teams_by_code(team_config):
    return team_config.get("teams") or {}


def country_to_code(match_config):
    return {country: code for country, code in team_code_by_name(match_config).items()}


def build_language_to_countries(match_config, team_config):
    code_to_country = {code: country for country, code in team_code_by_name(match_config).items()}
    mapping = defaultdict(set)
    for code, team in teams_by_code(team_config).items():
        country = team.get("country_name") or code_to_country.get(code)
        for language_code in team.get("language_codes") or []:
            mapping[str(language_code).lower()].add(country)
    return {language: sorted(countries) for language, countries in mapping.items()}


def build_unique_language_to_country(match_config, team_config):
    unique = {}
    for language, countries in build_language_to_countries(match_config, team_config).items():
        if language in SHARED_TIER2_LANGUAGE_CODES:
            continue
        if len(countries) == 1:
            unique[language] = countries[0]
    return unique


def normalize_subreddit(subreddit):
    return str(subreddit or "").strip().lower().removeprefix("r/")


def build_subreddit_to_country(team_config):
    mapping = {}
    collisions = defaultdict(set)
    for team in teams_by_code(team_config).values():
        country = team.get("country_name")
        for subreddit in team.get("country_subreddits") or []:
            key = normalize_subreddit(subreddit)
            if not key:
                continue
            collisions[key].add(country)
            mapping[key] = country
    return {key: value for key, value in mapping.items() if len(collisions[key]) == 1}


def match_subreddits(match, match_config, team_config):
    code_by_country = country_to_code(match_config)
    teams = teams_by_code(team_config)
    subreddits = list(team_config.get("neutral_subreddits") or [])
    for country in (match.get("team_a"), match.get("team_b")):
        code = code_by_country.get(country)
        if code and code in teams:
            subreddits.extend(teams[code].get("country_subreddits") or [])

    seen = set()
    ordered = []
    for subreddit in subreddits:
        key = normalize_subreddit(subreddit)
        if key and key not in seen:
            seen.add(key)
            ordered.append(str(subreddit).strip().removeprefix("r/"))
    return ordered


def validate_configs(match_config, team_config):
    errors = []
    warnings = []
    matches = match_config.get("matches") or []
    team_codes = team_code_by_name(match_config)
    teams = teams_by_code(team_config)

    if len(matches) != EXPECTED_MATCH_COUNT:
        errors.append(f"expected {EXPECTED_MATCH_COUNT} scoped matches, found {len(matches)}")

    match_ids = [match.get("match_id") for match in matches]
    duplicate_ids = sorted([match_id for match_id, count in Counter(match_ids).items() if count > 1])
    if duplicate_ids:
        errors.append(f"duplicate match_id values: {', '.join(duplicate_ids)}")

    semifinal_matches = [
        match.get("match_id")
        for match in matches
        if "semi" in str(match.get("round") or "").lower()
        or str(match.get("match_id") or "").endswith("_sf")
    ]
    if semifinal_matches:
        errors.append(f"semifinals are in scoped matches: {', '.join(semifinal_matches)}")

    for match in matches:
        for side in ("team_a", "team_b"):
            country = match.get(side)
            code = team_codes.get(country)
            if not code:
                errors.append(f"{match.get('match_id')} has unknown {side}: {country}")
                continue
            if code not in teams:
                errors.append(f"{country} ({code}) is missing from team attribution config")

    for country, code in sorted(team_codes.items()):
        if code not in teams:
            errors.append(f"{country} ({code}) missing from team attribution config")
            continue
        team = teams[code]
        if team.get("country_name") != country:
            errors.append(f"{code} country_name must be {country!r}, found {team.get('country_name')!r}")
        if not isinstance(team.get("country_subreddits"), list):
            errors.append(f"{country} country_subreddits must be a list")
        if not isinstance(team.get("language_codes"), list) or not team.get("language_codes"):
            errors.append(f"{country} language_codes must be a non-empty list")

    neutral_subreddits = team_config.get("neutral_subreddits")
    if not isinstance(neutral_subreddits, list) or not neutral_subreddits:
        errors.append("neutral_subreddits must be a non-empty list")

    coverage = build_coverage_report(match_config, team_config)
    insufficient = [row["country_name"] for row in coverage if row["status"] == "insufficient_data"]
    if insufficient:
        warnings.append(f"insufficient attribution paths for: {', '.join(insufficient)}")

    return errors, warnings, coverage


def build_coverage_report(match_config, team_config):
    team_codes = team_code_by_name(match_config)
    teams = teams_by_code(team_config)
    unique_language_to_country = build_unique_language_to_country(match_config, team_config)
    rows = []

    for country, code in sorted(team_codes.items()):
        team = teams.get(code)
        if not team:
            rows.append(
                {
                    "team_code": code,
                    "country_name": country,
                    "tier1_available": False,
                    "tier2_available": False,
                    "eligible_for_attribution": False,
                    "status": "config_error",
                }
            )
            continue

        tier1_available = bool(team.get("country_subreddits"))
        tier2_languages = [
            language
            for language in team.get("language_codes") or []
            if unique_language_to_country.get(language) == country
        ]
        tier2_available = bool(tier2_languages)
        eligible = tier1_available or tier2_available
        rows.append(
            {
                "team_code": code,
                "country_name": country,
                "tier1_available": tier1_available,
                "tier1_subreddits": ";".join(team.get("country_subreddits") or []),
                "tier2_available": tier2_available,
                "tier2_languages": ";".join(tier2_languages),
                "eligible_for_attribution": eligible,
                "status": "eligible" if eligible else "insufficient_data",
            }
        )

    return rows


def write_csv(path, rows, fieldnames=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def validate_phase_fields(row, required_fields, source):
    missing = [field for field in required_fields if field not in row]
    if missing:
        raise ValueError(f"{source} is missing required fields: {', '.join(missing)}")


def words(text):
    return WORD_RE.findall(str(text or "").lower())


LANGUAGE_ALIASES = {
    "nb": "no",
}


def canonical_language_code(language_code):
    code = str(language_code or "").lower()
    return LANGUAGE_ALIASES.get(code, code)


ENGLISH_PROFANITY = {
    "arse",
    "ass",
    "asshole",
    "bastard",
    "bitch",
    "bollocks",
    "bullshit",
    "crap",
    "cunt",
    "damn",
    "dick",
    "fuck",
    "fucked",
    "fucker",
    "fucking",
    "hell",
    "motherfucker",
    "piss",
    "shit",
    "shitty",
    "twat",
    "wanker",
}

SPANISH_PROFANITY = {
    "cabron",
    "cojones",
    "joder",
    "mierda",
    "pendejo",
    "pinche",
    "puta",
    "puto",
}

FRENCH_PROFANITY = {
    "bordel",
    "con",
    "connard",
    "connasse",
    "emmerde",
    "merde",
    "putain",
    "salope",
}

GERMAN_PROFANITY = {
    "arsch",
    "arschloch",
    "fotze",
    "mist",
    "scheisse",
    "scheiße",
    "verdammt",
    "wichser",
}

PORTUGUESE_PROFANITY = {
    "caralho",
    "foda",
    "fodase",
    "foder",
    "merda",
    "porra",
    "puta",
    "puto",
}

DUTCH_PROFANITY = {
    "godverdomme",
    "klootzak",
    "kut",
    "lul",
    "tering",
}

ITALIAN_PROFANITY = {
    "cazzo",
    "merda",
    "stronzo",
    "vaffanculo",
}

TURKISH_PROFANITY = {
    "amk",
    "bok",
    "orospu",
    "sik",
    "siktir",
}

ARABIC_PROFANITY = {
    "خرا",
    "زب",
    "شرموط",
    "كسمك",
    "كس",
}

CZECH_PROFANITY = {
    "blbec",
    "hajzl",
    "hovno",
    "kurva",
    "prdel",
    "sracka",
    "sračka",
}

BOSNIAN_PROFANITY = {
    "jebem",
    "jebote",
    "kurac",
    "picka",
    "pička",
    "sranje",
}

CROATIAN_PROFANITY = {
    "jebem",
    "jebote",
    "kurac",
    "picka",
    "pička",
    "sranje",
}

NORWEGIAN_PROFANITY = {
    "dritt",
    "faen",
    "helvete",
    "jævla",
    "jaevla",
}

SWEDISH_PROFANITY = {
    "fan",
    "helvete",
    "javla",
    "jävla",
    "skit",
}

AFRIKAANS_PROFANITY = {
    "fok",
    "kak",
    "moer",
}

PERSIAN_PROFANITY = {
    "کیر",
    "کس",
    "گوه",
}

ZULU_PROFANITY = {
    "nyela",
}

LEXICONS = {
    "af": AFRIKAANS_PROFANITY,
    "ar": ARABIC_PROFANITY,
    "bs": BOSNIAN_PROFANITY,
    "cs": CZECH_PROFANITY,
    "de": GERMAN_PROFANITY,
    "en": ENGLISH_PROFANITY,
    "es": SPANISH_PROFANITY,
    "fa": PERSIAN_PROFANITY,
    "fr": FRENCH_PROFANITY,
    "hr": CROATIAN_PROFANITY,
    "it": ITALIAN_PROFANITY,
    "nl": DUTCH_PROFANITY,
    "no": NORWEGIAN_PROFANITY,
    "pt": PORTUGUESE_PROFANITY,
    "sv": SWEDISH_PROFANITY,
    "tr": TURKISH_PROFANITY,
    "zu": ZULU_PROFANITY,
}


def count_swears(text, language_code):
    lexicon = LEXICONS.get(canonical_language_code(language_code), set())
    tokens = words(text)
    return sum(1 for token in tokens if token in lexicon), len(tokens)
