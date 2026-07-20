# World Cup Discourse Project Handoff

Last updated: 2026-07-16

## Project Summary

`worldcup_discourse` is a research and reporting pipeline for World Cup discourse around players, immigration, national identity, sensitive language, sentiment, and match-level effects. It is separate from the root Swearing World Cup ranking pipeline, although the root dashboard output also lives in this folder.

The project collects or reads Reddit and Bluesky records, extracts player mentions and identity-discourse keyword matches, detects language, runs transformer sentiment scoring, scans sensitive-language patterns, exports flagged comments, audits flagged context, and generates CSV/SVG/HTML reports.

## Tech Stack

- Runtime: Python 3.12-compatible scripts.
- Data format: JSONL for raw and processed records; CSV/SVG/HTML/TXT for reports.
- Reddit archival data: Arctic Shift API.
- Reddit live data: optional PRAW client.
- Bluesky data: AT Protocol `app.bsky.feed.searchPosts`.
- Language detection: `lingua-language-detector`.
- Sentiment model: `cardiffnlp/twitter-xlm-roberta-base-sentiment` through Hugging Face `transformers`.
- ML/NLP dependencies: `torch`, `transformers`, `datasets`, `scikit-learn`, `wordfreq`, `sentencepiece`, `protobuf`, `tiktoken`.
- Statistical testing: `scipy` is imported by the analysis scripts but is not listed in `requirements.txt`.
- Static reporting: generated SVG charts and generated HTML pages.

Install listed dependencies from inside `worldcup_discourse/`:

```bash
python -m pip install -r requirements.txt
```

Recommended extra dependencies used by scripts:

```bash
python -m pip install scipy praw
```

## Important Environment Variables

Bluesky collector:

- `BSKY_IDENTIFIER` or `BLUESKY_IDENTIFIER`
- `BSKY_PASSWORD` or `BLUESKY_PASSWORD`
- Alternate username variables recognized: `BSKY_HANDLE`, `BLUESKY_USERNAME`

Reddit live collector:

- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`

If credentials are missing, those collectors skip rather than crashing.

## Directory Layout

```text
worldcup_discourse/
|-- requirements.txt
|-- scheduler.py
|-- run_phase2.py
|-- run_groupstage_sentiment.py
|-- run_new_games_sentiment.py
|-- run_gd3_backlog_sentiment.py
|-- run_metrics_pipeline.py
|-- run_snapshot_pipeline.py
|-- arctic_shift_batch.py
|-- collect_since_gw2.py
|-- generate_basic_results.py
|-- generate_sensitive_language_scan.py
|-- export_flagged_comments.py
|-- generate_flagged_context_audit.py
|-- generate_research_explorer.py
|-- build_match_table.py
|-- test_flag_sentiment.py
|-- test_group_effects.py
|-- test_outcome_effect.py
|-- config/
|-- collectors/
|-- processing/
|-- data/
|   |-- raw/
|   |-- processed/
|   |-- events/
|   `-- matches/
|-- reports/
|   |-- phase2_basic_results/
|   |-- analysis/
|   `-- research_explorer/
`-- tests/
```

## Configuration Files

- `config/schedule.json`: match IDs, kickoff times, nation/opponent metadata, and subreddit targets.
- `config/squads.json`: player names and aliases used for mention extraction.
- `config/tracked_countries.json`: countries included by the Phase 2 scheduler logic.
- `config/match_url_map.json`: match IDs used by `scheduler.py` for mapped collection runs.
- `config/keywords.py`: generated immigration/national-identity keyword lists plus helper functions:
  - `get_all_keywords(lang)`
  - `get_hostile_keywords(lang)`

## Data Flow

### Raw Data

Raw files live under:

- `data/raw/*.jsonl`
- `data/raw/reddit/*.jsonl`
- `data/matches/<match_id>/raw/*.jsonl`

Raw records can come from:

- Arctic Shift post/comment search.
- Bluesky search posts.
- Live Reddit collection through PRAW.

### Processed Data

Processed files live under `data/processed/`:

- `<match_id>_mentions.jsonl`
- `<match_id>_lang.jsonl`
- `<match_id>_sentiment.jsonl`

The processing stages are:

1. Normalize raw records.
2. Deduplicate where supported by the script.
3. Extract player mentions from full names or aliases.
4. Match identity-discourse keywords.
5. Assign `track` as `player` or `discourse`.
6. Detect language.
7. Filter to supported sentiment languages.
8. Score sentiment.

Supported sentiment language set in the sentiment-runner scripts:

- English: `en`
- French: `fr`
- Dutch: `nl`
- German: `de`
- Spanish: `es`
- Portuguese: `pt`
- Arabic: `ar`

### Reports

Primary generated report locations:

- `reports/phase2_basic_results/`
- `reports/phase2_basic_results/flagged_comments/`
- `reports/phase2_basic_results/flagged_context_audit/`
- `reports/analysis/`
- `reports/research_explorer/`

Static dashboards already present:

- `worldcup_discourse_dashboard.html`
- `swearing_world_cup_dashboard.html`
- `swearing_world_cup_ui.html`
- `reports/phase2_basic_results/index.html`
- `reports/research_explorer/index.html`

## Core Scripts And Commands

Run commands from `worldcup_discourse/` unless noted otherwise.

### `scheduler.py`

Runs collection for all match IDs in `config/match_url_map.json`.

```bash
python scheduler.py
```

For each match, it:

1. Looks up kickoff from `config/schedule.json`.
2. Runs an event window from kickoff minus 1 hour to kickoff plus 6 hours.
3. Starts Bluesky, Arctic Shift, and Reddit live collectors with a 5-minute timeout per collector.
4. Logs to `scheduler.log`.

### `run_phase2.py`

End-to-end Phase 2 flow for qualifying matches after the third unique schedule date and involving tracked countries.

```bash
python run_phase2.py
```

Stages:

1. Load schedule, squads, tracked countries.
2. Find finished qualifying matches.
3. Fetch or load match events.
4. Run event collection.
5. Extract mentions.
6. Detect language.
7. Sample and score sentiment.
8. Print a summary.

### `run_groupstage_sentiment.py`

Runs mention extraction, language detection, and sentiment scoring for hardcoded group-stage matches.

```bash
python run_groupstage_sentiment.py
```

Limit to one or more matches:

```bash
python run_groupstage_sentiment.py --match can_vs_bih_gd1 --match eng_vs_cro_gd1
```

Overwrite existing sentiment output:

```bash
python run_groupstage_sentiment.py --force
```

Hardcoded group-stage match IDs:

- `can_vs_bih_gd1`
- `eng_vs_cro_gd1`
- `fra_vs_sen_gd1`
- `ger_vs_cur_gd1`
- `ned_vs_jpn_gd1`
- `sco_vs_hai_gd1`

### `run_new_games_sentiment.py`

Processes post-GW2 collected games from `collect_since_gw2.MATCH_TARGETS`.

```bash
python run_new_games_sentiment.py
```

Options:

```bash
python run_new_games_sentiment.py --match eng_vs_cod_r32 --force
```

### `run_gd3_backlog_sentiment.py`

Processes GD3 backlog matches when raw Reddit files exist.

```bash
python run_gd3_backlog_sentiment.py
```

Options:

```bash
python run_gd3_backlog_sentiment.py --match sui_vs_can_gd3 --force
python run_gd3_backlog_sentiment.py --include-empty
```

Hardcoded backlog match IDs:

- `ecu_vs_ger_gd3`
- `sco_vs_bra_gd3`
- `sui_vs_can_gd3`
- `tun_vs_ned_gd3`

### `arctic_shift_batch.py`

Backfills selected match/subreddit pairs from Arctic Shift.

```bash
python arctic_shift_batch.py
```

It searches both posts and comments, filters by match, team, player, and discourse keywords, and writes to:

- `data/raw/reddit/<match_id>_<subreddit>.jsonl`

### `collect_since_gw2.py`

Collects configured post-GW2 match targets. This script is imported by multiple reporting and sentiment scripts to discover new match IDs.

```bash
python collect_since_gw2.py
```

### `run_snapshot_pipeline.py`

Runs the snapshot-report pipeline:

1. `generate_sensitive_language_scan.py`
2. `export_flagged_comments.py`
3. `generate_flagged_context_audit.py`
4. `generate_basic_results.py`

```bash
python run_snapshot_pipeline.py
```

At the end it prints modification timestamps and row counts for:

- `raw_volume_by_match.csv`
- `sensitive_language_overview.csv`
- `sentiment_by_match.csv`

### `run_metrics_pipeline.py`

Runs post-sentiment metric refresh:

1. `generate_basic_results.py`
2. `build_match_table.py`
3. `test_flag_sentiment.py`

```bash
python run_metrics_pipeline.py
```

Optional:

```bash
python run_metrics_pipeline.py --include-group-effects
```

Only use `--include-group-effects` after manually filling `outcome` and `nation` in `reports/analysis/match_table.csv`. `build_match_table.py` rewrites those columns blank.

## Reporting Scripts

### `generate_basic_results.py`

Generates aggregate CSVs, SVG charts, and an HTML index under `reports/phase2_basic_results/`.

Typical outputs include:

- `raw_volume_by_match.csv`
- `raw_volume_by_match.svg`
- `comment_volume_by_source.csv`
- `platform_distribution.csv`
- `language_distribution.csv`
- `mention_rows_by_match.csv`
- `top_player_mentions.csv`
- `sentiment_by_match.csv`
- `sentiment_by_track.csv`
- `sentiment_distribution.csv`
- `index.html`

### `generate_sensitive_language_scan.py`

Runs regex-based sensitive-language scanning over raw JSONL records. It writes overview CSVs and SVGs under `reports/phase2_basic_results/`.

Pattern groups:

- `racism_or_discrimination_discussion`
- `severe_identity_slur`
- `identity_targeted_context`
- `abusive_or_hard_language`
- `negative_match_tone`

These are keyword flags, not classifier labels.

### `export_flagged_comments.py`

Exports flagged raw records into:

- `reports/phase2_basic_results/flagged_comments/flagged_comments_full.jsonl`
- `reports/phase2_basic_results/flagged_comments/flagged_comments_preview.csv`
- one CSV per flag level

It includes spreadsheet-safe CSV escaping for fields that might be interpreted as formulas.

### `generate_flagged_context_audit.py`

Builds a context audit around flagged records and writes:

- `flagged_context_audit.csv`
- match, term, target type, player-link, and review-priority summaries
- SVG charts under `reports/phase2_basic_results/flagged_context_audit/`

### `generate_research_explorer.py`

Builds a standalone research explorer:

```bash
python generate_research_explorer.py
```

Writes:

- `reports/research_explorer/index.html`

It combines processed sentiment with flagged context audit data.

## Analysis Scripts

### `build_match_table.py`

Builds:

- `reports/analysis/match_table.csv`

This is used by downstream statistical tests.

### `test_flag_sentiment.py`

Tests whether flagged records have a different sentiment-label distribution than unflagged records.

```bash
python test_flag_sentiment.py
```

Writes:

- `reports/analysis/flag_sentiment_test.txt`

Statistical method:

- Chi-square test of independence.
- Cramer's V effect size.
- Negative-share difference.

If no flagged record overlaps sentiment output, it writes a data-gap diagnostic instead.

### `test_group_effects.py`

Tests flag-rate differences across outcome groups and source/subreddit groups.

```bash
python test_group_effects.py
```

Requires `reports/analysis/match_table.csv` to have nonblank `outcome` and `nation` columns. Uses chi-square or Fisher's exact test depending on expected cell counts.

Writes:

- `reports/analysis/group_effects_test.txt`

### `test_outcome_effect.py`

Tests association between match outcome and:

- sentiment-label distribution
- flagged-comment rates

```bash
python test_outcome_effect.py
```

Requires `match_outcomes.py` to contain non-placeholder `MATCH_OUTCOMES` and `MATCH_NATIONS` values.

Writes:

- `reports/analysis/outcome_effect_test.txt`

## Processing Modules

### `processing/mention_extractor.py`

Matches player full names or aliases using regex word boundaries. Returns:

```json
[
  {"nation": "england", "name": "Bukayo Saka"}
]
```

### `processing/lang_detector.py`

Uses Lingua with English, French, Dutch, Arabic, Spanish, Portuguese, and German.

Rules:

- Text shorter than 20 characters returns `short_text`.
- English, Dutch, German, and Afrikaans-like detections require confidence of at least 0.85 or return `unknown`.

### `processing/sentiment.py`

Loads:

```text
cardiffnlp/twitter-xlm-roberta-base-sentiment
```

Maps:

- `LABEL_0` to `negative`
- `LABEL_1` to `neutral`
- `LABEL_2` to `positive`

The module also contains `sample_for_scoring(records)`, although the newer runner scripts score all eligible rows and set `scored_all_eligible = True`.

## Collector Modules

### `collectors/arctic_shift_collector.py`

Collects posts and comments from Arctic Shift for each subreddit and writes:

- `data/raw/<match_id>_<subreddit>_posts.jsonl`
- `data/raw/<match_id>_<subreddit>_comments.jsonl`

### `collectors/bluesky_collector.py`

Uses Bluesky search to collect posts matching player names, aliases, and discourse keywords. Writes:

- `data/raw/<match_id>_bluesky_posts.jsonl`

### `collectors/reddit_live_collector.py`

Uses PRAW to collect new subreddit posts and comments within the requested window. Writes:

- `data/raw/<match_id>_<subreddit>_live_posts.jsonl`
- `data/raw/<match_id>_<subreddit>_live_comments.jsonl`

## Test Commands

From `worldcup_discourse/`:

```bash
python -m unittest discover tests
```

Or run individual smoke files:

```bash
python tests/test_sentiment.py
python tests/test_mention_extractor.py
python tests/test_lang_detector.py
python tests/test_arctic_shift.py
```

Several top-level files named `test_*.py` are analysis scripts, not unit tests.

## Current Output Inventory

Notable existing report artifacts:

- `reports/phase2_basic_results/index.html`
- `reports/research_explorer/index.html`
- `reports/analysis/match_table.csv`
- `reports/analysis/flag_sentiment_test.txt`
- `reports/analysis/outcome_effect_test.txt`
- `reports/phase2_basic_results/flagged_comments/flagged_comments_full.jsonl`
- `reports/phase2_basic_results/flagged_context_audit/flagged_context_audit.csv`

Notable static dashboards:

- `worldcup_discourse_dashboard.html`
- `swearing_world_cup_dashboard.html`
- `swearing_world_cup_ui.html`

## Known Gotchas

- `requirements.txt` does not list every imported dependency. `scipy` is needed for statistical tests and `praw` is needed for live Reddit collection.
- The transformer model may download on first use and can be slow without a warm cache.
- `processing/sentiment.py` loads the model at import time.
- `build_match_table.py` rewrites `outcome` and `nation` blank, so run it before manual outcome annotation, not after.
- Sensitive-language scans are regex/keyword flags, not final moderation labels.
- Some scripts have hardcoded match sets; check the constants before assuming all files are included.
- Several scripts should be run from `worldcup_discourse/` because they use relative paths.
- Raw data can contain sensitive or abusive text. Use previews and audit files carefully.

## Recommended Next Work

1. Add `scipy` and optional `praw` to `requirements.txt` or document them in a separate dev requirements file.
2. Create one canonical CLI entry point for collection, sentiment processing, snapshot reports, and metrics reports.
3. Move hardcoded match sets into config files.
4. Add deterministic sampling seeds where `sample_for_scoring` is used.
5. Add an explicit data dictionary for raw, mentions, language, sentiment, flagged, and audit rows.
6. Separate root Swearing World Cup dashboard outputs from discourse outputs to avoid project-boundary confusion.
