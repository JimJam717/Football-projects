# Soccer Recruitment Decision Engine

A prescriptive analytics tool that generates structured player recommendation dossiers for MLS-oriented soccer recruitment. Built to mimic the output an analyst would hand to a sporting director.

## Overview

The engine scrapes player data from FBref (via `soccerdata`), ranks players on role-specific metric bundles, identifies similar successful MLS players using a KNN cosine-similarity model, and produces markdown dossier files with composite scores, risk flags, and acquisition recommendations.

## Target Leagues (2024-25 Season)

| League | Tier Weight | Rationale |
|--------|------------|-----------|
| Championship (ENG) | 1.10 | Strong competitive depth, proven pathway |
| Eredivisie (NED) | 1.05 | Good development league, technical quality |
| MLS (USA) | 1.00 | Baseline — target league |
| Belgian Pro League (BEL) | 1.00 | Comparable to MLS in quality |
| Liga MX (MEX) | 0.95 | Slight discount for defensive style variance |

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Scrape data from FBref (Phase 1 — takes ~5 minutes)
python main.py --scrape

# 3. Compute percentile rankings (Phase 2)
python main.py --rank

# 4. Generate a player dossier
python main.py --player "Player Name" --role forward --budget 300000

# 5. View top targets for a role
python main.py --top-targets --role midfielder --budget 300000 --n 5
```

## Roles & Metric Bundles

| Role | Metrics |
|------|---------|
| **Forward** | npxG/90, Shots/90, xA/90, Progressive Carries/90, Touches in Att Pen/90 |
| **Winger** | xA/90, Progressive Carries/90, Dribbles Completed/90, Crosses/90, Progressive Passes/90 |
| **Midfielder** | Progressive Passes/90, Progressive Carries/90, Pressures/90, Tackles/90, xA/90, Pass Completion % |
| **Fullback** | Progressive Carries/90, Crosses/90, Tackles/90, Interceptions/90, xA/90 |
| **Defender (CB)** | Aerials Won/90, Tackles/90, Interceptions/90, Progressive Passes/90, Clearances/90 |

## Dossier Output

Each dossier includes:
- **Composite Score** (0-100) with tier label (Elite / Strong Profile / Solid Option / Monitor Only)
- **Metric Breakdown** — per-90 value, percentile rank, and plain-English interpretation for each role metric
- **Similar MLS Players** — top 3 cosine-similar successful MLS anchors
- **Risk Flags** — age (>28), sample size (<1500 min), league discount (<1.0 tier)
- **Recommendation Verdict** — RECOMMEND / CONDITIONAL / MONITOR
- **Budget Assessment** — fit against MLS salary benchmarks

## Project Structure

```
soccer-recruitment-engine/
  data/
    players_cleaned.csv      # Phase 1 output
    players_ranked.csv       # Phase 2 output
  output/
    dossiers/                # Generated markdown dossiers
  src/
    pipeline.py              # Phase 1: FBref scraping & cleaning
    ranking.py               # Phase 2: Percentile ranking engine
    similarity.py            # Phase 3: KNN similarity model
    dossier.py               # Phase 4: Dossier generator
  main.py                    # Phase 5: CLI interface
  requirements.txt
  README.md
```

## Notes

- FBref rate-limits aggressively — the pipeline adds a 4-second delay between requests
- Data is cached locally by `soccerdata` in `~/soccerdata/data/FBref/`
- If pressures data is unavailable from FBref, ball recoveries are used as a proxy
- Players with <900 minutes are excluded; duplicate entries (mid-season transfers) keep the higher-minutes row
- All per-90 counting stats are multiplied by the league tier weight
