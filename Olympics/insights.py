import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


# Thresholds and tunables.
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "insights.json"
TOP_PRINT_COUNT = 20

CORRIDOR_OUTLIER_Z = 3.0
CORRIDOR_SPORT_MIN_ATHLETES = 5
CORRIDOR_SPORT_SHARE = 0.80
CORRIDOR_ASYMMETRY_MIN_COMBINED = 8
CORRIDOR_ASYMMETRY_RATIO = 5.0

SPORT_MIN_KNOWN_BIRTHPLACES = 25
SPORT_OUTLIER_ABS_Z = 2.0

NOC_DEPENDENCY_MIN_KNOWN = 5
NOC_DEPENDENCY_Z = 2.0
SPECIAL_NOCS = {"EOR", "AIN"}

SPLIT_CITY_MIN_NOCS = 2
FULL_DIASPORA_CITY_MIN_BORN = 5

TRIPLE_MISMATCH_CORRIDOR_MIN = 3
TRIPLE_MISMATCH_EXAMPLES = 8

TRAINING_NOC_MIN_RESIDENCES = 10
TRAINING_NOC_SHARE = 0.40
TRAINING_TOP_HOSTS = 10

MEDAL_NOC_MIN_MEDALISTS = 5
MEDAL_NOC_MIN_POINT_GAP = 15.0
MEDAL_SPORT_MIN_RATIO = 1.5

AGE_SPORT_MIN_KNOWN = 25
AGE_GAP_YEARS = 2.5

DYNASTY_MAX_MATCHES = 20

CONTESTED_REASON_CODES = {
    "gbr_constituent",
    "ned_kingdom",
    "den_kingdom",
    "tpe_china",
    "hkg_china",
    "pur_native",
    "usa_territory",
    "fra_territory",
}

CONTESTED_COUNTRY_GROUPS = [
    {"Great Britain", "Ireland"},
    {"China", "Hong Kong", "Chinese Taipei"},
    {"United States", "Puerto Rico", "American Samoa", "Guam", "Virgin Islands, US"},
    {"France", "Guadeloupe", "Martinique", "French Guiana", "Tahiti"},
    {"Netherlands", "Aruba", "Curacao", "Netherlands Antilles"},
    {"Denmark", "Faroe Islands", "Greenland"},
]


def load_json(name, default):
    path = DATA_DIR / name
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Skipping unreadable {path}: {exc}")
        return default


def as_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value, default=0):
    number = as_float(value)
    if number is None:
        return default
    return int(number)


def mean(values):
    return sum(values) / len(values) if values else 0.0


def pstdev(values):
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / len(values))


def z_score(value, avg, sigma):
    if not sigma:
        return 0.0
    return (value - avg) / sigma


def pct(value):
    number = as_float(value, 0.0)
    return f"{number:.1f}%"


def country_names(country_stats):
    names = set()
    for noc, record in country_stats.items():
        names.add(noc)
        country = record.get("country")
        if country:
            names.add(country)
    return names


def corridor_key(record):
    return (record.get("birth_country") or "", record.get("rep_country") or "")


def top_sport(record):
    sports = record.get("sports") or []
    if not sports:
        return None, 0
    best = max(sports, key=lambda item: as_int(item.get("count")))
    return best.get("sport") or "Unknown sport", as_int(best.get("count"))


def athlete_medal_count(athlete):
    if "medal_count" in athlete:
        return as_int(athlete.get("medal_count"))
    medals = athlete.get("medals")
    if isinstance(medals, list):
        return len(medals)
    return 0


def add_insight(insights, category, headline, value, baseline, score, evidence):
    insights.append(
        {
            "id": f"{category}-{len(insights) + 1}",
            "category": category,
            "headline": headline,
            "value": value,
            "baseline": baseline,
            "score": round(as_float(score, 0.0), 3),
            "evidence": evidence,
        }
    )


def safe_print(text):
    print(str(text).encode("ascii", errors="replace").decode("ascii"))


def detect_corridor_outliers(insights, corridors):
    counts = [as_int(record.get("athlete_count")) for record in corridors]
    logs = [math.log(count) for count in counts if count > 0]
    avg = mean(logs)
    sigma = pstdev(logs)
    for record in corridors:
        count = as_int(record.get("athlete_count"))
        if count <= 0:
            continue
        score = z_score(math.log(count), avg, sigma)
        if score >= CORRIDOR_OUTLIER_Z:
            birth, rep = corridor_key(record)
            sport, sport_count = top_sport(record)
            add_insight(
                insights,
                "corridor_outlier",
                f"{birth} -> {rep} is an unusually large Olympic migration corridor",
                count,
                f"log-count z >= {CORRIDOR_OUTLIER_Z}; mean={avg:.2f}, sigma={sigma:.2f}",
                score,
                f"{count} athletes; top sport: {sport} ({sport_count}).",
            )


def detect_corridor_sport_concentration(insights, corridors):
    for record in corridors:
        count = as_int(record.get("athlete_count"))
        if count < CORRIDOR_SPORT_MIN_ATHLETES:
            continue
        sport, sport_count = top_sport(record)
        if not sport:
            continue
        share = sport_count / count if count else 0.0
        if share >= CORRIDOR_SPORT_SHARE:
            birth, rep = corridor_key(record)
            add_insight(
                insights,
                "corridor_sport_concentration",
                f"{birth} -> {rep} is concentrated in {sport}",
                f"{sport_count}/{count} ({share * 100:.1f}%)",
                f"corridors with >= {CORRIDOR_SPORT_MIN_ATHLETES} athletes and top-sport share >= {CORRIDOR_SPORT_SHARE:.0%}",
                share * math.log1p(count),
                f"{sport_count} of {count} athletes in this corridor compete in {sport}.",
            )


def detect_corridor_asymmetry(insights, corridors):
    counts = {corridor_key(record): as_int(record.get("athlete_count")) for record in corridors}
    seen = set()
    for record in corridors:
        birth, rep = corridor_key(record)
        if not birth or not rep:
            continue
        pair_key = tuple(sorted([birth, rep]))
        if pair_key in seen:
            continue
        seen.add(pair_key)
        forward = counts.get((birth, rep), 0)
        reverse = as_int(record.get("reverse_count"), counts.get((rep, birth), 0))
        if reverse == 0 and (rep, birth) in counts:
            reverse = counts[(rep, birth)]
        combined = forward + reverse
        if combined < CORRIDOR_ASYMMETRY_MIN_COMBINED:
            continue
        smaller = min(forward, reverse)
        ratio = max(forward, reverse) / smaller if smaller else max(forward, reverse)
        if ratio < CORRIDOR_ASYMMETRY_RATIO:
            continue
        source, target = (birth, rep) if forward >= reverse else (rep, birth)
        dominant = max(forward, reverse)
        other = min(forward, reverse)
        add_insight(
            insights,
            "corridor_asymmetry",
            f"{source} -> {target} is a strongly one-way Olympic corridor",
            f"{dominant}:{other}",
            f"combined flow >= {CORRIDOR_ASYMMETRY_MIN_COMBINED}, ratio >= {CORRIDOR_ASYMMETRY_RATIO:g}",
            ratio,
            f"{dominant} athletes move in the dominant direction versus {other} in reverse.",
        )


def detect_sport_outliers(insights, sports):
    eligible = [
        record
        for record in sports
        if as_int(record.get("total_records_with_birthplace_data")) >= SPORT_MIN_KNOWN_BIRTHPLACES
        and as_float(record.get("diaspora_pct")) is not None
    ]
    values = [as_float(record.get("diaspora_pct"), 0.0) for record in eligible]
    avg = mean(values)
    sigma = pstdev(values)
    for record in eligible:
        value = as_float(record.get("diaspora_pct"), 0.0)
        score = z_score(value, avg, sigma)
        if abs(score) >= SPORT_OUTLIER_ABS_Z:
            direction = "high" if score > 0 else "low"
            add_insight(
                insights,
                "sport_outlier",
                f"{record.get('sport', 'Unknown sport')} has an unusually {direction} diaspora share",
                pct(value),
                f"sports with >= {SPORT_MIN_KNOWN_BIRTHPLACES} known birthplaces; mean={avg:.1f}%, sigma={sigma:.1f}",
                abs(score),
                f"{record.get('diaspora_count', 0)} of {record.get('total_classified_birthplace_records', 0)} classified athletes are diaspora.",
            )


def detect_small_noc_dependency(insights, country_stats):
    qualifying = []
    for noc, record in country_stats.items():
        if noc in SPECIAL_NOCS:
            continue
        if as_int(record.get("total_records_with_birthplace_data")) >= NOC_DEPENDENCY_MIN_KNOWN:
            value = as_float(record.get("foreign_born_pct"))
            if value is not None:
                qualifying.append((noc, record, value))
    values = [item[2] for item in qualifying]
    avg = mean(values)
    sigma = pstdev(values)
    threshold = avg + NOC_DEPENDENCY_Z * sigma

    for noc, record in country_stats.items():
        if noc not in SPECIAL_NOCS:
            continue
        classified = as_int(record.get("total_classified_birthplace_records"))
        if classified:
            add_insight(
                insights,
                "refugee_neutral_team",
                f"{record.get('country', noc)} is 100% foreign-born by construction",
                pct(record.get("foreign_born_pct")),
                "EOR/AIN are separated from small-NOC dependency rankings",
                99.0,
                f"{record.get('foreign_born_count', 0)} of {classified} classified athletes are foreign-born.",
            )

    for noc, record, value in qualifying:
        if value >= threshold:
            add_insight(
                insights,
                "small_noc_dependency",
                f"{record.get('country', noc)} relies unusually heavily on foreign-born athletes",
                pct(value),
                f"qualifying NOC mean={avg:.1f}%, sigma={sigma:.1f}%, threshold={threshold:.1f}%",
                z_score(value, avg, sigma),
                f"{record.get('foreign_born_count', 0)} of {record.get('total_classified_birthplace_records', 0)} classified athletes are foreign-born.",
            )


def contested_city(city):
    athletes = city.get("all_athletes") or []
    if any(contested_reason_applies(athlete) for athlete in athletes):
        return True
    countries = set(city.get("represented_countries") or [])
    birth_country = city.get("birth_country")
    if birth_country:
        countries.add(birth_country)
    return any(len(countries & group) >= 2 for group in CONTESTED_COUNTRY_GROUPS)


def contested_reason_applies(athlete):
    reason = athlete.get("diaspora_reason") or ""
    if reason not in CONTESTED_REASON_CODES:
        return False
    birth_country = athlete.get("birth_country")
    if reason == "usa_territory" and birth_country == "United States":
        return False
    if reason == "fra_territory" and birth_country == "France":
        return False
    return True


def detect_split_cities(insights, cities, country_name_set):
    for city in cities:
        represented = city.get("represented_nocs") or []
        total = as_int(city.get("total_born"))
        city_name = city.get("city") or "Unknown city"
        birth_country = city.get("birth_country")
        if len(represented) >= SPLIT_CITY_MIN_NOCS and contested_city(city):
            add_insight(
                insights,
                "split_city",
                f"{city_name} natives split across {len(represented)} Olympic delegations",
                len(represented),
                "city has multiple represented NOCs and constituent/territory rules appear to apply",
                len(represented) + math.log1p(total),
                f"Represented NOCs: {', '.join(map(str, represented))}; birth country: {birth_country or 'unknown'}.",
            )
        diaspora_pct = as_float(city.get("diaspora_pct"), 0.0)
        if total >= FULL_DIASPORA_CITY_MIN_BORN and diaspora_pct == 100.0:
            caveat = ""
            if birth_country and birth_country not in country_name_set:
                caveat = " The recorded birth country had no NOC key in country_stats.json at Paris 2024."
            add_insight(
                insights,
                "full_diaspora_city",
                f"Every known Paris 2024 athlete born in {city_name} represented another NOC",
                f"{total}/{total}",
                f"total_born >= {FULL_DIASPORA_CITY_MIN_BORN} and diaspora_pct = 100%",
                math.log1p(total) + 5.0,
                f"{city_name}, {birth_country or 'unknown country'} produced {total} known-birthplace athletes, all diaspora.{caveat}",
            )


def is_triple_mismatch(athlete):
    if "identity_profile" in athlete:
        return athlete.get("identity_profile") == "triple_mismatch"
    birth = athlete.get("birth_country")
    nationality = athlete.get("nationality") or athlete.get("nationality_country")
    rep = athlete.get("rep_country")
    if not birth or not nationality or not rep:
        return False
    return len({birth, nationality, rep}) == 3


def describe_athlete(athlete):
    bits = [
        athlete.get("name") or "Unknown athlete",
        athlete.get("sport") or "unknown sport",
        f"born {athlete.get('birth_country') or 'unknown'}",
    ]
    nationality = athlete.get("nationality") or athlete.get("nationality_country")
    if nationality:
        bits.append(f"national of {nationality}")
    bits.append(f"represents {athlete.get('rep_country') or athlete.get('rep_noc') or 'unknown'}")
    medals = athlete_medal_count(athlete)
    if medals:
        bits.append(f"{medals} medal(s)")
    return "; ".join(bits)


def detect_triple_mismatches(insights, athletes):
    triples = [athlete for athlete in athletes if is_triple_mismatch(athlete)]
    if not triples:
        return
    triples.sort(key=lambda athlete: (athlete_medal_count(athlete), athlete.get("name") or ""), reverse=True)
    examples = triples[:TRIPLE_MISMATCH_EXAMPLES]
    add_insight(
        insights,
        "triple_mismatch",
        f"{len(triples)} athletes have born/national-of/represents triple mismatches",
        len(triples),
        "identity_profile == triple_mismatch, or birth/nationality/representation are all present and different",
        20.0 + math.log1p(len(triples)),
        "Examples: " + " | ".join(describe_athlete(athlete) for athlete in examples),
    )

    corridor_counts = Counter((athlete.get("birth_country"), athlete.get("rep_country")) for athlete in triples)
    for (birth, rep), count in corridor_counts.items():
        if birth and rep and count >= TRIPLE_MISMATCH_CORRIDOR_MIN:
            add_insight(
                insights,
                "triple_mismatch_corridor",
                f"{birth} -> {rep} has a cluster of triple-mismatch athletes",
                count,
                f"corridor has >= {TRIPLE_MISMATCH_CORRIDOR_MIN} triple-mismatch athletes",
                count,
                f"{count} athletes in this corridor have born/national-of/represents all different.",
            )


def athlete_trains_abroad(athlete):
    if "trains_abroad" in athlete:
        return bool(athlete.get("trains_abroad"))
    residence = athlete.get("residence_country")
    rep = athlete.get("rep_country")
    return bool(residence and rep and residence != rep)


def detect_training_abroad(insights, athletes):
    known = [athlete for athlete in athletes if athlete.get("residence_country")]
    if not known:
        return

    host_counts = Counter()
    noc_known = Counter()
    noc_abroad = Counter()
    for athlete in known:
        noc = athlete.get("rep_noc") or athlete.get("rep_country") or "Unknown"
        noc_known[noc] += 1
        if athlete_trains_abroad(athlete):
            host_counts[athlete.get("residence_country")] += 1
            noc_abroad[noc] += 1

    top_hosts = host_counts.most_common(TRAINING_TOP_HOSTS)
    if top_hosts:
        add_insight(
            insights,
            "training_host",
            f"{top_hosts[0][0]} is the largest recorded training-abroad host country",
            top_hosts[0][1],
            "athletes with residence_country present and trains_abroad true",
            top_hosts[0][1],
            "Top hosts: " + ", ".join(f"{country} ({count})" for country, count in top_hosts),
        )

    for noc, total in noc_known.items():
        if total < TRAINING_NOC_MIN_RESIDENCES:
            continue
        abroad = noc_abroad[noc]
        share = abroad / total if total else 0.0
        if share >= TRAINING_NOC_SHARE:
            add_insight(
                insights,
                "team_trains_elsewhere",
                f"{noc} is a team that largely trains elsewhere",
                f"{abroad}/{total} ({share * 100:.1f}%)",
                f"min {TRAINING_NOC_MIN_RESIDENCES} known residences and >= {TRAINING_NOC_SHARE:.0%} abroad",
                share * 10.0,
                f"{abroad} of {total} athletes with known residence live outside their represented country.",
            )


def detect_medal_performance(insights, country_stats, sports, athletes):
    has_country_medals = any("diaspora_medal_pct" in record for record in country_stats.values())
    if has_country_medals:
        for noc, record in country_stats.items():
            medalists = as_int(record.get("medal_winning_athletes"), as_int(record.get("medal_count")))
            delegation_share = as_float(record.get("foreign_born_pct"), 0.0)
            medal_share = as_float(record.get("diaspora_medal_pct"))
            if medal_share is None or medalists < MEDAL_NOC_MIN_MEDALISTS:
                continue
            gap = medal_share - delegation_share
            if gap >= MEDAL_NOC_MIN_POINT_GAP:
                add_insight(
                    insights,
                    "medal_overperformance_noc",
                    f"{record.get('country', noc)} converts diaspora athletes into medals at an unusually high rate",
                    f"+{gap:.1f} points",
                    f"min {MEDAL_NOC_MIN_MEDALISTS} medal-winning athletes and medalist share exceeds delegation share by >= {MEDAL_NOC_MIN_POINT_GAP} points",
                    gap,
                    f"Diaspora share among medalists: {medal_share:.1f}%; delegation diaspora share: {delegation_share:.1f}%.",
                )

    has_sport_medals = any("diaspora_medal_pct" in record for record in sports)
    if has_sport_medals:
        for record in sports:
            population_share = as_float(record.get("diaspora_pct"), 0.0)
            medal_share = as_float(record.get("diaspora_medal_pct"))
            if medal_share is None or population_share <= 0:
                continue
            ratio = medal_share / population_share
            if ratio >= MEDAL_SPORT_MIN_RATIO:
                add_insight(
                    insights,
                    "medal_overperformance_sport",
                    f"Diaspora athletes overperform in {record.get('sport', 'unknown sport')} medals",
                    f"{ratio:.2f}x",
                    f"diaspora medal share >= {MEDAL_SPORT_MIN_RATIO}x population share",
                    ratio,
                    f"Diaspora share among medalists: {medal_share:.1f}%; sport population share: {population_share:.1f}%.",
                )

    if has_country_medals or has_sport_medals:
        return

    medalists = [athlete for athlete in athletes if athlete_medal_count(athlete) > 0]
    if medalists:
        add_insight(
            insights,
            "medal_data_available",
            f"{len(medalists)} athlete records include medal data, but aggregate medal fields are absent",
            len(medalists),
            "country_stats/sport_stats need diaspora_medal_pct for over/under-performance detectors",
            1.0,
            "Run the enriched pipeline to add country and sport medal aggregates.",
        )


def detect_age_gap(insights, athletes):
    by_sport = defaultdict(lambda: {"diaspora": [], "homegrown": []})
    for athlete in athletes:
        age = as_float(athlete.get("age_at_games"))
        sport = athlete.get("sport")
        if age is None or not sport:
            continue
        bucket = "diaspora" if athlete.get("is_diaspora") else "homegrown"
        by_sport[sport][bucket].append(age)

    for sport, groups in by_sport.items():
        diaspora = groups["diaspora"]
        homegrown = groups["homegrown"]
        if len(diaspora) + len(homegrown) < AGE_SPORT_MIN_KNOWN or not diaspora or not homegrown:
            continue
        gap = mean(diaspora) - mean(homegrown)
        if abs(gap) >= AGE_GAP_YEARS:
            direction = "older" if gap > 0 else "younger"
            add_insight(
                insights,
                "age_gap",
                f"Diaspora athletes in {sport} are meaningfully {direction} than homegrown athletes",
                f"{gap:+.1f} years",
                f"min {AGE_SPORT_MIN_KNOWN} known ages and absolute mean gap >= {AGE_GAP_YEARS} years",
                abs(gap),
                f"Diaspora mean age {mean(diaspora):.1f} (n={len(diaspora)}); homegrown mean age {mean(homegrown):.1f} (n={len(homegrown)}).",
            )


def detect_dynasties(insights, athletes, known_countries):
    matches = []
    for athlete in athletes:
        relatives = athlete.get("sporting_relatives")
        if not relatives:
            continue
        rep_country = athlete.get("rep_country")
        rep_noc = athlete.get("rep_noc")
        for country in known_countries:
            if len(country) < 4 or country == rep_country or country == rep_noc:
                continue
            if re.search(rf"\b{re.escape(country)}\b", relatives, flags=re.IGNORECASE):
                matches.append((athlete, country))
                break
    if not matches:
        return
    snippets = []
    for athlete, country in matches[:DYNASTY_MAX_MATCHES]:
        relatives = str(athlete.get("sporting_relatives"))[:180]
        snippets.append(f"{athlete.get('name')} ({athlete.get('rep_noc')}) may link to {country}: {relatives}")
    add_insight(
        insights,
        "cross_flag_dynasty",
        f"{len(matches)} athletes have low-confidence sporting-relative text pointing to another NOC",
        len(matches),
        "sporting_relatives mentions a country different from the athlete's represented country",
        0.5 + math.log1p(len(matches)),
        " | ".join(snippets),
    )


def main():
    athletes = load_json("olympics_diaspora.json", [])
    countries = load_json("country_stats.json", {})
    cities = load_json("city_stats.json", [])
    sports = load_json("sport_stats.json", [])
    corridors = load_json("corridor_stats.json", [])

    if not isinstance(athletes, list):
        athletes = []
    if not isinstance(countries, dict):
        countries = {}
    if not isinstance(cities, list):
        cities = []
    if not isinstance(sports, list):
        sports = []
    if not isinstance(corridors, list):
        corridors = []

    insights = []
    known_countries = country_names(countries)

    detect_corridor_outliers(insights, corridors)
    detect_corridor_sport_concentration(insights, corridors)
    detect_corridor_asymmetry(insights, corridors)
    detect_sport_outliers(insights, sports)
    detect_small_noc_dependency(insights, countries)
    detect_split_cities(insights, cities, known_countries)
    detect_triple_mismatches(insights, athletes)
    detect_training_abroad(insights, athletes)
    detect_medal_performance(insights, countries, sports, athletes)
    detect_age_gap(insights, athletes)
    detect_dynasties(insights, athletes, known_countries)

    insights.sort(key=lambda item: item["score"], reverse=True)
    for index, insight in enumerate(insights, start=1):
        insight["id"] = f"insight-{index:03d}"

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as handle:
        json.dump(insights, handle, ensure_ascii=True, indent=2)
        handle.write("\n")

    safe_print(f"Wrote {OUTPUT_FILE} with {len(insights)} insights.")
    safe_print(f"Top {min(TOP_PRINT_COUNT, len(insights))} insights:")
    for index, insight in enumerate(insights[:TOP_PRINT_COUNT], start=1):
        safe_print(f"{index:2}. [{insight['category']}] score={insight['score']:.3f} {insight['headline']}")
        safe_print(f"    value={insight['value']} | baseline={insight['baseline']}")
        safe_print(f"    evidence={insight['evidence']}")


if __name__ == "__main__":
    main()
