# Swearing World Cup Caveats And Fix Triage

## Current Usable Outputs

- Leaderboard CSV: `data/processed/leaderboard/swearing_leaderboard.csv`
- Leaderboard JSON: `data/processed/leaderboard/swearing_leaderboard.json`
- Final collected comments after dedupe: 457,898
- Attributed comments used for country rankings: 262,328
- Ranking threshold currently used: at least 1,000 attributed comments and 10,000 attributed words

## Caveats To Mention In Methodology

### Speaker Attribution Is Mostly Subreddit-Based

- 262,198 comments were attributed by Tier 1 subreddit.
- Only 130 comments were attributed by Tier 2 unique-language inference.
- 195,570 comments, or 42.7%, remained unattributed.
- The unattributed bucket is mostly neutral `soccer` / `worldcup` comments in shared languages, especially English.

This means the leaderboard should be described as a subreddit-identity fanbase ranking, not a universal ranking of all match-thread commenters.

### Neutral Threads Are Mostly Dropped

- Shared languages are intentionally excluded from Tier 2 attribution.
- English, Spanish, Arabic, French, and Portuguese comments from neutral subreddits mostly remain unattributed.
- This avoids guessing who is speaking based on language, but it also means neutral mega-thread comments are underused.

### Duplicate Removal Was Large

- Raw collected rows before dedupe: 814,198
- Rows after dedupe: 457,898
- Duplicate rows removed: 356,300
- Remaining cross-match duplicate comment IDs: 0

The dedupe rule kept the first occurrence by `worldcup2026_match_config.json` match order. This is deterministic, but same-day neutral-thread comments may be assigned to the earliest matching game window and removed from later match files.

### Collection Had Many Arctic Shift Timeout Stops

- Many subreddit queries stopped with `HTTP 422: Timeout. Maybe slow down a bit`.
- Most still collected some comments before stopping.
- Some country-specific subreddits returned zero rows, likely because the subreddit was quiet, unavailable in Arctic Shift, or a weak subreddit choice.
- Notable example: `arg_vs_sui_qf / r/argentina` stopped after 1,800 comments.

This is acceptable for exploratory analysis but should be disclosed as incomplete archival collection.

### Low-Sample Countries Are Unranked

The leaderboard keeps low-sample teams in the output but does not assign them a rank. Examples:

- Sweden: 53 comments, 791 words
- Switzerland: 18 comments, 234 words
- Ivory Coast: 1 comment, 1 word
- South Korea: 456 comments
- Ecuador: 571 comments

This prevents tiny samples from winning on unstable rates.

### Profanity Lexicons Are Starter Lists

- English is strongest.
- Non-English lexicons were added for the major detected languages, but they are starter lists, not publication-grade dictionaries.
- The scorer avoids identity slurs and focuses on general profanity.
- Cross-language profanity rates can still be uneven because slang intensity and tokenization differ by language.

## Simple Fixes Worth Considering

### Add A Methodology Report

Create a short generated report that records:

- collection totals
- duplicate totals
- attribution totals
- ranking thresholds
- low-sample teams
- known collection timeouts
- profanity lexicon caveat

This is low effort and makes the project much easier to explain.

### Improve The Collection Status Summary

Generate a compact CSV from `data/collected/collection_status.csv` with one row per match:

- total collected comments
- number of error subreddits
- number of empty subreddits
- whether any team-specific subreddit was empty

This helps identify matches that are thin or lopsided.

### Add Lexicon Audit Files

Move profanity lists out of `swearing_pipeline.py` into a reviewable config file, for example:

- `profanity_lexicons.json`

Then add a script that reports swear hits by language and term. This would make it easier to spot false positives or missing common words.

### Add A Minimum-Sample View And Full View

The current leaderboard includes both qualified and unqualified rows in one file. A simple improvement is to output:

- `swearing_leaderboard_qualified.csv`
- `swearing_leaderboard_all.csv`

This prevents visualization code from accidentally using low-sample teams as ranked competitors.

### Add Per-Country Confidence Flags

Add fields such as:

- `sample_warning`
- `attribution_warning`
- `collection_warning`

This would let the bracket visualization display a small caution marker for countries with thin data or collection issues.

## Bigger Fixes Not Worth Doing Right Now

### Rerun Collection For Timeout Queries

Possible, but likely not worth it. The dataset is already large enough, and rerunning Arctic Shift could take hours.

### Infer Speaker From Mentions Or Team Names

Do not do this for this project. It violates the core speaker-identity rule: mentions identify who is being talked about, not who is speaking.

### Attribute Shared-Language Neutral Comments

Not recommended unless using a much stronger speaker-identity signal. Language alone cannot distinguish USA, England, Canada, Australia, Ghana, etc.

## Recommended Next Step

Before building the final visualization, add:

1. a compact methodology/report artifact, and
2. qualified-only leaderboard output.

Those two changes are simple and would make the visualization much harder to misread.
