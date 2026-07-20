import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "reports" / "phase2_basic_results"


COMMENT_DEDUPE_FIELDS = {"match_id", "created_utc", "text_preview"}


def normalized(value):
    return " ".join((value or "").split()).strip().lower()


def row_key(row, fieldnames):
    fields = set(fieldnames or [])
    if COMMENT_DEDUPE_FIELDS.issubset(fields):
        return (
            "comment",
            normalized(row.get("match_id")),
            normalized(row.get("created_utc")),
            normalized(row.get("text_preview")),
        )
    return tuple((field, row.get(field, "")) for field in fieldnames or [])


def dedupe_csv(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    seen = set()
    deduped = []
    for row in rows:
        key = row_key(row, fieldnames)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    if len(deduped) == len(rows):
        return 0, len(rows)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(deduped)

    return len(rows) - len(deduped), len(deduped)


def main():
    total_removed = 0
    locked = []
    for path in sorted(REPORT_DIR.rglob("*.csv")):
        try:
            removed, remaining = dedupe_csv(path)
        except PermissionError:
            locked.append(path)
            print(f"{path.relative_to(BASE_DIR)}: skipped, file is locked")
            continue
        total_removed += removed
        if removed:
            print(f"{path.relative_to(BASE_DIR)}: removed {removed:,}, kept {remaining:,}")

    print(f"Total duplicate rows removed: {total_removed:,}")
    if locked:
        print("Locked files still need to be closed and rerun:")
        for path in locked:
            print(f"- {path}")


if __name__ == "__main__":
    main()
