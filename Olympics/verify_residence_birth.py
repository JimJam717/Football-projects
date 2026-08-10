import argparse
import csv
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data" / "olympics_diaspora.json"
DEFAULT_OUTPUT = ROOT / "data" / "residence_birth_verification.csv"
DEFAULT_CACHE = ROOT / "data" / "wikidata_verification_cache.json"
API_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "OlympicsResidenceBirthVerifier/1.0 (local research script)"

CLAIM_BIRTH_PLACE = "P19"
CLAIM_RESIDENCE = "P551"
CLAIM_COUNTRY = "P17"
CLAIM_ADMIN = "P131"
CLAIM_BIRTH_DATE = "P569"
CLAIM_CITIZENSHIP = "P27"
CLAIM_SPORT = "P641"


COUNTRY_ALIASES = {
    "russian federation": "russia",
    "united states of america": "united states",
    "usa": "united states",
    "uk": "great britain",
    "united kingdom": "great britain",
    "england": "great britain",
    "scotland": "great britain",
    "wales": "great britain",
    "northern ireland": "great britain",
    "turkiye": "turkey",
    "trkiye": "turkey",
    "ir iran": "iran",
    "republic of korea": "south korea",
    "korea": "south korea",
    "hong kong, china": "hong kong",
    "republic of moldova": "moldova",
    "ua emirates": "united arab emirates",
    "syrian arab republic": "syria",
    "cote d'ivoire": "cote divoire",
    "cte d'ivoire": "cote divoire",
    "côte d'ivoire": "cote divoire",
    "curacao": "curacao",
    "curaao": "curacao",
}


def normalize_text(value):
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_country(value):
    text = normalize_text(value)
    return COUNTRY_ALIASES.get(text, text)


def display_name(name):
    """Convert common IOC all-caps surname style into a better search query."""
    if not name:
        return ""
    parts = str(name).split()
    if len(parts) >= 2 and parts[0].isupper():
        return " ".join(parts[1:] + [parts[0]]).title()
    return str(name).title()


def api_get(params, retries=4):
    params = dict(params)
    params["format"] = "json"
    url = f"{API_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code != 429 or attempt == retries - 1:
                raise
            retry_after = error.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else 5 * (attempt + 1)
            print(f"Wikidata rate-limited the request; waiting {wait}s...")
            time.sleep(wait)
        except URLError:
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("Wikidata request failed after retries")


def load_cache(path):
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return {"search": {}, "entities": {}}


def save_cache(path, cache):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(cache, handle, indent=2, ensure_ascii=False)


def search_people(query, cache, delay):
    key = normalize_text(query)
    if key in cache["search"]:
        return cache["search"][key]

    data = api_get({
        "action": "wbsearchentities",
        "language": "en",
        "type": "item",
        "limit": 8,
        "search": query,
    })
    ids = [item["id"] for item in data.get("search", [])]
    cache["search"][key] = ids
    time.sleep(delay)
    return ids


def get_entities(ids, cache, delay):
    ids = [entity_id for entity_id in ids if entity_id]
    missing = [entity_id for entity_id in ids if entity_id not in cache["entities"]]
    for start in range(0, len(missing), 40):
        chunk = missing[start:start + 40]
        if not chunk:
            continue
        data = api_get({
            "action": "wbgetentities",
            "ids": "|".join(chunk),
            "languages": "en",
            "props": "labels|claims",
        })
        for entity_id, entity in data.get("entities", {}).items():
            cache["entities"][entity_id] = entity
        time.sleep(delay)
    return {entity_id: cache["entities"].get(entity_id, {}) for entity_id in ids}


def label(entity):
    return entity.get("labels", {}).get("en", {}).get("value", "")


def claim_entity_ids(entity, prop):
    values = []
    for claim in entity.get("claims", {}).get(prop, []):
        mainsnak = claim.get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {})
        value = datavalue.get("value", {})
        if isinstance(value, dict) and value.get("entity-type") == "item":
            values.append(f"Q{value.get('numeric-id')}")
    return values


def claim_year(entity, prop):
    for claim in entity.get("claims", {}).get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if isinstance(value, dict) and "time" in value:
            match = re.search(r"([+-]\d{4,})", value["time"])
            if match:
                return int(match.group(1))
    return None


def countries_for_places(place_ids, cache, delay):
    if not place_ids:
        return [], []

    places = get_entities(place_ids, cache, delay)
    country_ids = set()
    admin_ids = set()
    place_labels = []

    for place_id, place in places.items():
        place_labels.append(label(place) or place_id)
        country_ids.update(claim_entity_ids(place, CLAIM_COUNTRY))
        admin_ids.update(claim_entity_ids(place, CLAIM_ADMIN))

    if not country_ids and admin_ids:
        admins = get_entities(sorted(admin_ids), cache, delay)
        for admin in admins.values():
            country_ids.update(claim_entity_ids(admin, CLAIM_COUNTRY))

    countries = get_entities(sorted(country_ids), cache, delay) if country_ids else {}
    country_labels = sorted({label(country) for country in countries.values() if label(country)})
    return place_labels, country_labels


def score_candidate(entity, athlete, cache, delay):
    score = 0
    reasons = []

    candidate_year = claim_year(entity, CLAIM_BIRTH_DATE)
    if candidate_year and athlete.get("birth_year") and candidate_year == athlete["birth_year"]:
        score += 3
        reasons.append("birth_year")

    sport_ids = claim_entity_ids(entity, CLAIM_SPORT)
    sport_labels = [label(item) for item in get_entities(sport_ids, cache, delay).values()]
    if athlete.get("sport") and any(
        normalize_text(athlete["sport"]) in normalize_text(sport)
        or normalize_text(sport) in normalize_text(athlete["sport"])
        for sport in sport_labels
    ):
        score += 2
        reasons.append("sport")

    citizenship_ids = claim_entity_ids(entity, CLAIM_CITIZENSHIP)
    citizenship_labels = [label(item) for item in get_entities(citizenship_ids, cache, delay).values()]
    country_signals = [athlete.get("rep_country"), athlete.get("nationality")]
    if any(
        normalize_country(source) == normalize_country(target)
        for source in country_signals
        for target in citizenship_labels
        if source and target
    ):
        score += 1
        reasons.append("citizenship")

    return score, ",".join(reasons)


def compare_country(source_country, wikidata_countries):
    if not source_country:
        return "source_missing"
    if not wikidata_countries:
        return "wikidata_missing"

    source_key = normalize_country(source_country)
    wd_keys = {normalize_country(country) for country in wikidata_countries}
    return "match" if source_key in wd_keys else "mismatch"


def verify_athlete(athlete, cache, delay):
    queries = [display_name(athlete.get("name")), athlete.get("name", "")]
    candidate_ids = []
    for query in queries:
        for entity_id in search_people(query, cache, delay):
            if entity_id not in candidate_ids:
                candidate_ids.append(entity_id)

    candidates = get_entities(candidate_ids, cache, delay)
    scored = []
    for entity_id, entity in candidates.items():
        score, reasons = score_candidate(entity, athlete, cache, delay)
        scored.append((score, entity_id, entity, reasons))
    scored.sort(reverse=True, key=lambda item: item[0])

    if not scored:
        return {
            "wikidata_status": "not_found",
            "wikidata_id": "",
            "wikidata_label": "",
            "match_reasons": "",
            "birth_status": "not_checked",
            "residence_status": "not_checked",
            "wikidata_birth_places": "",
            "wikidata_birth_countries": "",
            "wikidata_residences": "",
            "wikidata_residence_countries": "",
            "source_url": "",
        }

    best_score, best_id, best_entity, reasons = scored[0]
    if best_score < 2 or (len(scored) > 1 and best_score == scored[1][0]):
        wikidata_status = "ambiguous"
    else:
        wikidata_status = "matched_person"

    birth_places, birth_countries = countries_for_places(
        claim_entity_ids(best_entity, CLAIM_BIRTH_PLACE),
        cache,
        delay,
    )
    residences, residence_countries = countries_for_places(
        claim_entity_ids(best_entity, CLAIM_RESIDENCE),
        cache,
        delay,
    )

    return {
        "wikidata_status": wikidata_status,
        "wikidata_id": best_id,
        "wikidata_label": label(best_entity),
        "match_reasons": reasons,
        "birth_status": compare_country(athlete.get("birth_country"), birth_countries),
        "residence_status": compare_country(athlete.get("residence_country"), residence_countries),
        "wikidata_birth_places": "; ".join(birth_places),
        "wikidata_birth_countries": "; ".join(birth_countries),
        "wikidata_residences": "; ".join(residences),
        "wikidata_residence_countries": "; ".join(residence_countries),
        "source_url": f"https://www.wikidata.org/wiki/{best_id}",
    }


def include_athlete(athlete, focus):
    if focus == "all":
        return True
    if focus == "diaspora":
        return bool(athlete.get("is_diaspora"))
    if focus == "missing_birth":
        return not athlete.get("birth_country")
    if focus == "residence_abroad":
        return athlete.get("residence_status") == "abroad"
    if focus == "concerns":
        return (
            bool(athlete.get("is_diaspora"))
            or not athlete.get("birth_country")
            or athlete.get("residence_status") == "abroad"
        )
    raise ValueError(f"Unknown focus: {focus}")


def main():
    parser = argparse.ArgumentParser(
        description="Verify athlete birth and residence countries against structured Wikidata claims."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--cache", default=str(DEFAULT_CACHE))
    parser.add_argument(
        "--focus",
        choices=["concerns", "diaspora", "missing_birth", "residence_abroad", "all"],
        default="concerns",
        help="Which rows to check. Default focuses on rows most likely to affect analysis.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum rows to check; 0 means no limit.")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between Wikidata API calls.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    cache_path = Path(args.cache)

    with input_path.open("r", encoding="utf-8") as handle:
        athletes = json.load(handle)

    selected = [athlete for athlete in athletes if include_athlete(athlete, args.focus)]
    if args.limit:
        selected = selected[:args.limit]

    cache = load_cache(cache_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "code",
        "name",
        "sport",
        "rep_country",
        "birth_country",
        "residence_country",
        "residence_status",
        "wikidata_status",
        "wikidata_id",
        "wikidata_label",
        "match_reasons",
        "birth_status",
        "residence_verification_status",
        "wikidata_birth_places",
        "wikidata_birth_countries",
        "wikidata_residences",
        "wikidata_residence_countries",
        "source_url",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, athlete in enumerate(selected, start=1):
            result = verify_athlete(athlete, cache, args.delay)
            writer.writerow({
                "code": athlete.get("code", ""),
                "name": athlete.get("name", ""),
                "sport": athlete.get("sport", ""),
                "rep_country": athlete.get("rep_country", ""),
                "birth_country": athlete.get("birth_country", ""),
                "residence_country": athlete.get("residence_country", ""),
                "residence_status": athlete.get("residence_status", ""),
                "wikidata_status": result["wikidata_status"],
                "wikidata_id": result["wikidata_id"],
                "wikidata_label": result["wikidata_label"],
                "match_reasons": result["match_reasons"],
                "birth_status": result["birth_status"],
                "residence_verification_status": result["residence_status"],
                "wikidata_birth_places": result["wikidata_birth_places"],
                "wikidata_birth_countries": result["wikidata_birth_countries"],
                "wikidata_residences": result["wikidata_residences"],
                "wikidata_residence_countries": result["wikidata_residence_countries"],
                "source_url": result["source_url"],
            })
            if index % 25 == 0:
                save_cache(cache_path, cache)
                print(f"Checked {index}/{len(selected)} athletes...")

    save_cache(cache_path, cache)
    print(f"Wrote verification review to {output_path}")
    print(f"Wrote Wikidata cache to {cache_path}")


if __name__ == "__main__":
    main()
