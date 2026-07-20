# Swearing World Cup Project Handoff

Last updated: 2026-07-16

## Project Summary

The Swearing World Cup is a Python data pipeline and browser dashboard that ranks 2026 FIFA World Cup fanbases by profanity density in Reddit comments. It intentionally treats the output as a subreddit-identity fanbase ranking, not a universal ranking of every commenter in every match thread.

The main pipeline:

1. Validates tournament and team attribution configuration.
2. Collects Reddit comments from Arctic Shift.
3. Deduplicates collected comments across match files.
4. Detects comment language with Lingua.
5. Attributes comments to countries using subreddit identity first and unique-language inference second.
6. Scores comments against multilingual starter profanity lexicons.
7. Builds a ranked leaderboard.
8. Generates FIFA-style group, knockout, awards, and dashboard data.

## Repository Layout

```text
.
|-- swearing_pipeline.py
|-- validate_swearing_inputs.py
|-- collect_swearing_data.py
|-- dedupe_collected_comments.py
|-- detect_language.py
|-- attribute_speaker.py
|-- score_swearing.py
|-- rank_champion.py
|-- swearing_tournament.py
|-- generate_swearing_world_cup_dashboard.py
|-- worldcup2026_match_config.json
|-- worldcup2026_team_attribution_config.json
|-- SWEARING_WORLD_CUP_CAVEATS.md
|-- data/
|   |-- collected/
|   |-- processed/
|   |   |-- language/
|   |   |-- attributed/
|   |   |-- scored/
|   |   |-- leaderboard/
|   |   `-- reports/
|   `-- context/
|-- tests/
`-- worldcup_discourse/
```

## Tech Stack

- Runtime: Python 3.12-compatible scripts.
- Storage format: JSONL for row-level data; JSON and CSV for summaries; standalone HTML for visualization.
- Network source: Arctic Shift Reddit API at `https://arctic-shift.photon-reddit.com/api/comments/search`.
- Language detection: `lingua-language-detector`.
- Visualization: generated static HTML, CSS, and vanilla JavaScript in `worldcup_discourse/swearing_world_cup_dashboard.html`.
- Tests: `pytest` tests under `tests/`.

Root pipeline dependencies are mostly Python standard library plus:

```bash
python -m pip install lingua-language-detector pytest
```

## Core Configuration

### `worldcup2026_match_config.json`

Defines tournament scope and match metadata. Current scope is:

- Tournament: 2026 FIFA World Cup
- Generated on: 2026-07-12
- Scope: `group_stage_through_quarterfinals`
- Expected scoped matches in validation: 100
- Semifinals are intentionally blocked by validation.

Important fields:

- `team_codes`: country display name to short code.
- `matches`: match rows with `match_id`, `phase`, `round`, `date`, `team_a`, and `team_b`.

### `worldcup2026_team_attribution_config.json`

Defines attribution metadata by team code:

- `country_name`
- `country_subreddits`
- `language_codes`
- `neutral_subreddits`

Attribution depends heavily on this file. Country-specific subreddits enable Tier 1 attribution; unique language codes can enable Tier 2 attribution.

## Main Data Model

### Collected Comment Row

Produced by `collect_swearing_data.py` in `data/collected/*.jsonl`.

```json
{
  "match_id": "eng_vs_cro_gl_md1",
  "subreddit": "soccer",
  "comment_id": "...",
  "author": "...",
  "timestamp": 1781620000,
  "text": "..."
}
```

### Language Row

Produced by `detect_language.py` in `data/processed/language/*.jsonl`.

Adds:

- `detected_language`
- `detected_language_confidence`
- `language_confidence_margin`
- `language_detection_model`

### Attributed Row

Produced by `attribute_speaker.py` in `data/processed/attributed/*.jsonl`.

Adds:

- `attributed_country`
- `attribution_tier`

### Scored Row

Produced by `score_swearing.py` in `data/processed/scored/*.jsonl`.

Adds:

- `swear_count`
- `word_count`

### Leaderboard Row

Produced by `rank_champion.py` in `data/processed/leaderboard/`.

Key metrics:

- `comments`
- `words`
- `swear_hits`
- `swears_per_1000_words`
- `swears_per_100_comments`
- `qualified_for_rank`
- `sample_status`
- `rank`

## Pipeline Commands

Run from the repository root.

### 1. Validate Inputs

```bash
python validate_swearing_inputs.py --write-reports --show-subreddits
```

Writes optional reports under `data/processed/reports/`:

- `attribution_coverage.csv`
- `language_lookup.json`
- `collection_subreddits_by_match.csv`

### 2. Dry Run Collection Targets

```bash
python collect_swearing_data.py --dry-run
```

Writes:

- `data/collected/collection_dry_run_subreddits.csv`

### 3. Collect Reddit Comments

All matches:

```bash
python collect_swearing_data.py
```

Single match:

```bash
python collect_swearing_data.py --match-id eng_vs_cro_gl_md1
```

Useful options:

- `--window-hours 36`
- `--per-subreddit-cap 5000`
- `--quiet-progress`
- `--status-path data/collected/collection_status.csv`
- `--duplicates-path data/collected/duplicate_comment_ids.csv`

Default collection window starts at match date midnight UTC and runs for 36 hours.

### 4. Deduplicate Collected Comments

Preview:

```bash
python dedupe_collected_comments.py --dry-run
```

Apply:

```bash
python dedupe_collected_comments.py
```

Writes:

- `data/collected/dedupe_report.json`
- `data/collected/duplicate_comment_ids.csv`

The dedupe rule keeps the first occurrence by `worldcup2026_match_config.json` match order.

### 5. Detect Language

All files:

```bash
python detect_language.py
```

Single match:

```bash
python detect_language.py --match-id eng_vs_cro_gl_md1
```

Sharded run:

```bash
python detect_language.py --shard-count 4 --shard-index 0
```

Important defaults:

- `--min-confidence 0.65`
- `--min-margin 0.12`
- Text shorter than 20 characters is marked `short_text`.

### 6. Attribute Speaker Country

```bash
python attribute_speaker.py
```

Single match:

```bash
python attribute_speaker.py --match-id eng_vs_cro_gl_md1
```

The script blocks if the unattributed rate is at or above 30 percent unless this option is used:

```bash
python attribute_speaker.py --allow-high-unattributed
```

Writes:

- `data/processed/attributed/*.jsonl`
- `data/processed/reports/attribution_summary.json`
- `data/processed/reports/attribution_country_counts.csv`

### 7. Score Profanity

```bash
python score_swearing.py
```

Single match:

```bash
python score_swearing.py --match-id eng_vs_cro_gl_md1
```

Writes:

- `data/processed/scored/*.jsonl`

The profanity lexicons live in `swearing_pipeline.py` and currently cover English, Spanish, French, German, Portuguese, Dutch, Italian, Turkish, Arabic, Czech, Bosnian, Croatian, Norwegian, Swedish, Afrikaans, Persian, and Zulu starter lists.

### 8. Build Leaderboard

```bash
python rank_champion.py
```

Defaults:

- `--min-comments 1000`
- `--min-words 10000`

Writes:

- `data/processed/leaderboard/swearing_leaderboard.csv`
- `data/processed/leaderboard/swearing_leaderboard.json`

### 9. Build Tournament Data

```bash
python swearing_tournament.py
```

Writes:

- `data/processed/leaderboard/swearing_tournament.json`
- `data/processed/leaderboard/swearing_match_metrics.json`

### 10. Generate Dashboard

```bash
python generate_swearing_world_cup_dashboard.py
```

Writes:

- `data/processed/leaderboard/swearing_tournament.json`
- `data/processed/leaderboard/swearing_match_metrics.json`
- `worldcup_discourse/swearing_world_cup_dashboard.html`

The dashboard is a static HTML file. It can be opened directly in a browser.

## Current Usable Outputs

From `SWEARING_WORLD_CUP_CAVEATS.md`:

- Leaderboard CSV: `data/processed/leaderboard/swearing_leaderboard.csv`
- Leaderboard JSON: `data/processed/leaderboard/swearing_leaderboard.json`
- Final collected comments after dedupe: 457,898
- Attributed comments used for country rankings: 262,328
- Ranking threshold: at least 1,000 attributed comments and 10,000 attributed words

## Methodology Notes

### Ranking Metric

Primary rank ordering is:

1. Qualified samples first.
2. `swears_per_1000_words`, descending.
3. `swears_per_100_comments`, descending.
4. Comment count, descending.
5. Country name, ascending.

### Attribution Logic

Tier 1 attribution uses a unique country subreddit mapping. Example: a country-specific subreddit can map comments to that country.

Tier 2 attribution uses unique language-to-country inference only when a detected language maps to exactly one configured country. Shared languages are intentionally excluded from Tier 2.

The following shared languages are not used for unique Tier 2 attribution:

- Arabic
- English
- Spanish
- French
- Portuguese

### Tournament Logic

`swearing_tournament.py` turns the leaderboard into:

- Groups A through L.
- Top two per group.
- Best eight third-place qualifiers.
- Round of 32 through final.
- Awards such as Golden Ball, Golden Glove, Fair Play, Breakthrough, Passion Index, Top Swear Match, and Top Swear Word.

Semifinal input matches are not part of the scoped source dataset, but the generated profanity bracket includes semifinal and final rounds derived from leaderboard outcomes.

## Caveats To Carry Forward

- This is a subreddit-identity fanbase ranking, not a full speaker-identity census.
- 262,198 attributed comments were Tier 1 subreddit attribution.
- Only 130 attributed comments were Tier 2 unique-language inference.
- 195,570 comments, or 42.7 percent, remained unattributed.
- Neutral `soccer` and `worldcup` comments in shared languages are mostly dropped.
- Duplicate removal was large: 814,198 raw collected rows to 457,898 rows after dedupe.
- Remaining cross-match duplicate comment IDs after dedupe: 0.
- Many Arctic Shift queries stopped with timeout-related errors.
- Low-sample countries remain visible but unranked.
- Profanity lexicons are starter lists and are not publication-grade multilingual dictionaries.
- The scorer focuses on general profanity and avoids identity slurs.

## Tests

Run root tests with:

```bash
pytest tests
```

Existing tests cover tournament and pipeline behavior:

- `tests/test_swearing_pipeline.py`
- `tests/test_swearing_tournament.py`

## Recommended Next Work

1. Move profanity lexicons from `swearing_pipeline.py` into a reviewable JSON or CSV config.
2. Generate a compact methodology report from the current artifacts.
3. Split leaderboard outputs into qualified-only and all-teams views.
4. Add per-country confidence flags for sample size, attribution coverage, and collection health.
5. Summarize `data/collected/collection_status.csv` by match to identify thin or lopsided collection.
6. Add a one-command orchestration script after the methodology and output naming settle.

## Operational Warnings

- Do not rerun collection casually; Arctic Shift runs can be slow and may produce timeouts.
- Rerunning dedupe mutates `data/collected/*.jsonl`.
- `attribute_speaker.py` will fail without `--allow-high-unattributed` when unattributed rate is high.
- `generate_swearing_world_cup_dashboard.py` writes into `worldcup_discourse/`, even though it belongs to the root project pipeline.
- The generated dashboard embeds the tournament JSON directly into the HTML.
