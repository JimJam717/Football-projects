import argparse
import csv
import json
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd

from pipeline import (
    ATHLETES_CSV,
    COUNTRY_TO_NOC_MAP,
    countries_equivalent,
    country_matches_noc,
    normalize_country_key,
    normalize_optional_country,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_PROCESSED = ROOT / "data" / "olympics_diaspora.json"
DEFAULT_OUTPUT = ROOT / "data" / "birth_residence_audit.csv"


def clean(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def normalized(value):
    return normalize_optional_country(value) if clean(value) else None


def values_match(left, right):
    left_norm = normalize_country_key(left)
    right_norm = normalize_country_key(right)
    return left_norm == right_norm


def manual_search_url(athlete):
    query = " ".join(
        str(part)
        for part in [
            athlete.get("name"),
            athlete.get("sport"),
            athlete.get("rep_country"),
            "birthplace residence Paris 2024",
        ]
        if part
    )
    return f"https://www.google.com/search?q={quote_plus(query)}"


def load_processed(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return {str(item["code"]): item for item in json.load(handle)}


def issue_priority(issues):
    critical = {
        "processed_birth_country_differs_from_source",
        "processed_residence_country_differs_from_source",
        "birth_place_without_birth_country",
        "residence_place_without_residence_country",
    }
    review = {
        "foreign_birth_country",
        "foreign_residence_country",
        "birth_residence_country_differ",
        "birth_nationality_representation_all_differ",
    }
    if any(issue in critical for issue in issues):
        return "high"
    if any(issue in review for issue in issues):
        return "review"
    return "low"


def audit_row(source, processed):
    issues = []
    notes = []

    source_birth_country = clean(source.get("birth_country"))
    source_birth_place = clean(source.get("birth_place"))
    source_residence_country = clean(source.get("residence_country"))
    source_residence_place = clean(source.get("residence_place"))
    source_rep_country = clean(source.get("country"))
    source_rep_noc = clean(source.get("country_code"))
    source_nationality = clean(source.get("nationality"))

    processed_birth_country = processed.get("birth_country") if processed else None
    processed_residence_country = processed.get("residence_country") if processed else None

    normalized_birth_country = normalized(source_birth_country)
    normalized_residence_country = normalized(source_residence_country)

    if source_birth_place and not source_birth_country:
        issues.append("birth_place_without_birth_country")
    if source_birth_country and not source_birth_place:
        issues.append("birth_country_without_birth_place")

    if source_residence_place and not source_residence_country:
        issues.append("residence_place_without_residence_country")
    if source_residence_country and not source_residence_place:
        issues.append("residence_country_without_residence_place")

    if processed and not values_match(source_birth_country, processed_birth_country):
        if source_birth_country or processed_birth_country:
            issues.append("processed_birth_country_differs_from_source")

    if processed and not values_match(source_residence_country, processed_residence_country):
        if source_residence_country or processed_residence_country:
            issues.append("processed_residence_country_differs_from_source")

    if source_birth_country and normalized_birth_country != source_birth_country:
        notes.append(f"birth_country_normalized_to={normalized_birth_country}")
    if source_residence_country and normalized_residence_country != source_residence_country:
        notes.append(f"residence_country_normalized_to={normalized_residence_country}")

    if source_birth_country and source_rep_country and not country_matches_noc(
        source_birth_country,
        source_birth_place,
        source_rep_noc,
        source_rep_country,
    ):
        issues.append("foreign_birth_country")

    if source_residence_country and source_rep_country and not country_matches_noc(
        source_residence_country,
        source_residence_place,
        source_rep_noc,
        source_rep_country,
    ):
        issues.append("foreign_residence_country")

    if source_birth_country and source_residence_country and not countries_equivalent(
        source_birth_country,
        source_residence_country,
    ):
        issues.append("birth_residence_country_differ")

    if (
        source_birth_country
        and source_nationality
        and source_rep_country
        and not countries_equivalent(source_birth_country, source_nationality)
        and not countries_equivalent(source_birth_country, source_rep_country)
        and not countries_equivalent(source_nationality, source_rep_country)
    ):
        issues.append("birth_nationality_representation_all_differ")

    if source_birth_country and normalize_country_key(source_birth_country) not in COUNTRY_TO_NOC_MAP:
        notes.append("birth_country_not_in_country_to_noc_map")
    if source_residence_country and normalize_country_key(source_residence_country) not in COUNTRY_TO_NOC_MAP:
        notes.append("residence_country_not_in_country_to_noc_map")

    if not issues:
        issues.append("no_local_issue_detected")

    athlete = {
        "code": source.get("code"),
        "name": source.get("name"),
        "sport": processed.get("sport") if processed else clean(source.get("disciplines")),
        "rep_country": source_rep_country,
    }

    return {
        "priority": issue_priority(issues),
        "issues": "|".join(issues),
        "notes": "|".join(notes),
        "manual_search_url": manual_search_url(athlete),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fast local audit for athlete birth and residence country fields. No web calls."
    )
    parser.add_argument("--source", default=ATHLETES_CSV)
    parser.add_argument("--processed", default=str(DEFAULT_PROCESSED))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--only-review",
        action="store_true",
        help="Write only rows with high/review priority issues.",
    )
    args = parser.parse_args()

    source_df = pd.read_csv(args.source)
    processed_by_code = load_processed(args.processed)

    rows = []
    counts = {}
    for _, source in source_df.iterrows():
        code = str(source["code"])
        processed = processed_by_code.get(code, {})
        audit = audit_row(source, processed)
        counts[audit["priority"]] = counts.get(audit["priority"], 0) + 1

        if args.only_review and audit["priority"] == "low":
            continue

        rows.append({
            "priority": audit["priority"],
            "code": source.get("code"),
            "name": source.get("name"),
            "sport": processed.get("sport", ""),
            "rep_country": source.get("country"),
            "birth_place": clean(source.get("birth_place")),
            "birth_country_source": clean(source.get("birth_country")),
            "birth_country_processed": processed.get("birth_country"),
            "residence_place": clean(source.get("residence_place")),
            "residence_country_source": clean(source.get("residence_country")),
            "residence_country_processed": processed.get("residence_country"),
            "nationality": clean(source.get("nationality")),
            "issues": audit["issues"],
            "notes": audit["notes"],
            "manual_search_url": audit["manual_search_url"],
        })

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "priority",
        "code",
        "name",
        "sport",
        "rep_country",
        "birth_place",
        "birth_country_source",
        "birth_country_processed",
        "residence_place",
        "residence_country_source",
        "residence_country_processed",
        "nationality",
        "issues",
        "notes",
        "manual_search_url",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows):,} audit rows to {output_path}")
    print(
        "Priority counts: "
        + ", ".join(f"{priority}={count:,}" for priority, count in sorted(counts.items()))
    )


if __name__ == "__main__":
    main()
