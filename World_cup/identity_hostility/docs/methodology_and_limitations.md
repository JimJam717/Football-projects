# Methodology and Limitations

## What this is

This dashboard shows rates of model-detected identity-based hostile language
across 457,898 Reddit comments collected from World Cup 2026 match threads.

**Model-detected means a keyword match or a toxicity model score above a threshold
flagged the comment. It does not mean the comment has been read, verified, or
classified by a human reviewer as racist or xenophobic.**

---

## Data source

- 457,898 deduplicated comments collected from Reddit via the Arctic Shift archive,
  spanning 100+ World Cup 2026 group-stage through quarterfinal match threads.
- Comments come from match-window discussion in subreddits including r/soccer,
  r/worldcup, and country-specific football communities.
- This describes Reddit comment behaviour in these specific threads only — not the
  behaviour of any country's general population, fanbase, or the World Cup audience
  as a whole.

---

## Flag method

Each comment is evaluated by two signals:

1. **Keyword lexicon** — a private list of racial/ethnic and nationality/xenophobia
   terms. The lexicon file is not shown in any output. Category labels are neutral
   (e.g. "racial_ethnic_flagged", "nationality_flagged"). No slur text appears anywhere.

2. **Detoxify multilingual model** — `unitary/multilingual-toxic-xlm-roberta`,
   a free/local transformer model scoring identity-based hostility on a 0–1 scale.
   A comment is model-flagged when its score is at or above the configured threshold
   (default 0.5, tunable in `config/flag_config.json`).

A comment is flagged if **either** signal triggers. `flag_source` records whether the
flag came from the lexicon, the model, or both.

---

## Language coverage

Detoxify multilingual supports: **en, fr, es, it, pt, tr, ru**.

Comments in other detected languages receive no model score. They are marked
`model_unsupported`. The lexicon still applies to these comments, but if neither
signal fires, the comment is reported as `model_unsupported` — not as `unflagged`.
This distinction is visible in the by-language panel and in the headline coverage figure.

English is by far the largest language in this corpus. Non-English rates should be
read cautiously; multilingual models can have uneven recall across languages, and
some languages in this corpus were too sparse for stable rate estimates.

---

## What is not shown

- No individual comment text, usernames, or comment IDs appear anywhere in this
  dashboard or any public output file.
- No slurs appear in any label, column name, or category.
- No "most hostile" ranking of countries, fanbases, or subreddits. All panels show
  detected rates, not competitive orderings.
- Profanity (`swear_count > 0`) appears only in the overlap panel as a secondary
  descriptive signal, not as a standalone indicator of hostility.

---

## Calibration

Thresholds were calibrated against a ~200-row manual review of flagged and unflagged
comments. This was a noise-check pass — not a research annotation study. No
codebook, second reviewer, or inter-rater reliability was computed.

The threshold (default 0.5) is configurable in `config/flag_config.json`. If the
rate looks implausible, the threshold is the first thing to adjust.

---

## Known limitations

- **Attribution by subreddit, not speaker.** Subreddit identity is used for match
  attribution, not speaker nationality. r/soccer, r/worldcup, and other neutral
  subreddits contain commenters from many countries.
- **Collection coverage is uneven.** Some matches have thousands of comments; some
  have under 100. Rates on thin samples are unreliable and are shown at reduced
  opacity in the dashboard.
- **Lexicon coverage is imperfect.** The lexicon reflects English and common-word
  patterns in other languages. It will miss novel phrasing, dog whistles, coded
  language, and non-Latin script variants.
- **Model recall varies by language.** The multilingual model performs best on the
  languages it was trained on. Arabic, East Asian, and African language comments
  are outside the model's supported set entirely.
- **No sarcasm, irony, or context.** Neither the lexicon nor the model distinguishes
  reporting about hostility from expression of hostility, sarcasm from sincerity, or
  quotation from endorsement.
- **This is not a hate-speech classifier.** It is a triage-level detection pipeline
  suitable for descriptive analytics and portfolio demonstration. Do not present
  these rates as ground-truth hate-speech prevalence.
