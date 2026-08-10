# Olympic Representation and Birthplace

An interactive Paris 2024 visualization tool for exploring Olympic representation, migration corridors, birthplace data, and athlete residence patterns.

The project compares each athlete's recorded birth country with the NOC or country they represented. It enriches that cross-border representation signal with nationality, residence, medal outcomes, and corridor typology. The frontend is a static visualization layer that presents the processed data through maps, tables, charts, and detail drawers.

## Current Headline

| Metric | Value |
| --- | ---: |
| Total athletes | 11,113 |
| Athletes with known birthplaces | 9,475 |
| Athletes with missing birth-country data | 1,638 |
| Cross-border / diaspora athletes | 975 |
| Share of known-birthplace athletes | 10.29% |
| Distinct medal-winning athletes | 2,013 |
| Diaspora medal-winning athletes | 138 |
| Diaspora share of medal winners | 6.86% |
| Medalist share gap vs all known-birthplace athletes | -3.43 pts |
| Directional migration corridors | 548 |

Excluding EOR and AIN, the diaspora share is 9.72% of known-birthplace athletes and 6.58% of medal-winning athletes.

## Residence headline

The source dataset records athlete residence, not a verified training location. The dashboard therefore treats residence country as a clearly labeled training-base proxy:

| Metric | Value |
| --- | ---: |
| Athletes with known residence country | 8,288 |
| Reside in represented country | 6,774 |
| Reside outside represented country | 1,514 |
| Abroad share of known residences | 18.27% |
| Recorded abroad-residence host countries | 119 |
| Residence corridors | 651 |

The largest recorded host is the **United States**, with 507 athletes residing there while representing another team.

## What Changed

The project has moved beyond the original country/city map into a fuller migration analysis:

- Dynamic headline strip built from athlete data instead of hard-coded text.
- Corridor tab for directional birthplace-to-represented-country flows.
- Corridor taxonomy: `post-colonial`, `neighbor`, `refugee-or-neutral`, `talent-market`, `heritage-return`, `post-soviet`, `intra-sovereign`, and `unclassified`.
- Corridor asymmetry metrics and medal counts.
- Corridor map layer with typed arcs.
- Residence & Training tab with home/abroad counts, host rankings, team dependency, residence corridors, and a host-focused map.
- Small-nation dependency scatter plot.
- Diaspora share versus medalist share dumbbell chart.
- Pipeline joins medal data and adds nationality, residence, training-abroad, age, identity-profile, diaspora-type, and medal fields.
- `summary_stats.json` and `insights.json` are first-class data outputs. `insights.json` is a research output consumed by the findings document, not loaded by the frontend.
- The residence map defaults to the top 20 host countries as proportional bubbles. Selecting a host reveals only its five largest incoming representation routes.

## Repository Structure

```text
Olympics/
|-- app.js
|-- index.html
|-- insights.py
|-- pipeline.py
|-- README.md
|-- styles.css
|-- audit_birth_residence.py
|-- verify_residence_birth.py
`-- data/
    |-- city_coords_cache.json
    |-- city_stats.json
    |-- corridor_stats.json
    |-- country_stats.json
    |-- insights.json
    |-- olympics_diaspora.json
    |-- sport_stats.json
    |-- stories.json
    |-- summary_stats.json
    `-- training_stats.json
```

## Dashboard Features

### Header Insight Strip

The top strip summarizes the main cross-border representation count and decomposes diaspora athletes by `diaspora_type`.

Current diaspora-type athlete counts:

| Type | Athletes |
| --- | ---: |
| Unclassified | 409 |
| Talent-market | 174 |
| Heritage-return | 92 |
| Post-colonial | 86 |
| Neighbor | 86 |
| Refugee-or-neutral | 60 |
| Post-soviet | 39 |
| Intra-sovereign | 29 |

### Rankings Tab

The default tab includes:

- Highest foreign-born share by represented team.
- Most foreign-born athletes by represented team.
- Small-nation dependency scatter plot.
- Diaspora share versus medalist share dumbbell chart.
- Largest birthplace diaspora hubs table.

The country share chart uses a minimum known-birthplace threshold to avoid ranking tiny delegations purely on denominator noise. EOR and AIN are treated as special cases because they are foreign-born by construction in this framing.

### By Sport Tab

The sport view compares sports by:

- Diaspora share.
- Diaspora athlete count.

Sport rows also carry medal fields when present, including total medal-winning athletes, diaspora medal-winning athletes, and diaspora medalist share.

### Corridors Tab

The corridors tab is the main research feature.

It loads `data/corridor_stats.json` and shows directional flows:

```text
birth_country -> represented_country
```

The table supports sorting by:

- Corridor.
- Corridor type.
- Athlete count.
- Medal count.
- Asymmetry.

The default minimum corridor size is 3 athletes. Clicking a corridor opens a drawer with type, athletes, medal information, top sports, reverse-flow context, and roster details.

### Residence & Training Tab

The source dataset does not identify an athlete's actual training facility. This tab uses recorded `residence_country` as a clearly labeled proxy for training location.

It shows:

- Home-versus-abroad residence counts.
- Major host countries for athletes residing abroad.
- Teams with high abroad-residence shares.
- Directional `represented_country -> residence_country` corridors.
- A focused host map with Top 10, Top 20, and All controls.
- The five largest incoming routes after selecting a host.

Routes are intentionally hidden on the default map to keep the global view readable. Residence is not proof of an athlete's training facility, club, camp, or day-to-day training location.

Top current corridors by athlete count:

| Corridor | Athletes | Type | Medals |
| --- | ---: | --- | ---: |
| United States -> Puerto Rico | 24 | Intra-sovereign | 2 |
| Great Britain -> Ireland | 22 | Post-colonial | 3 |
| United States -> Nigeria | 18 | Talent-market | 0 |
| IR Iran -> EOR | 15 | Refugee-or-neutral | 0 |
| Russian Federation -> AIN | 13 | Refugee-or-neutral | 2 |
| Great Britain -> Australia | 10 | Post-colonial | 4 |
| Belarus -> AIN | 9 | Refugee-or-neutral | 3 |
| United States -> Canada | 9 | Neighbor | 0 |
| Great Britain -> New Zealand | 8 | Post-colonial | 0 |
| France -> Mali | 7 | Post-colonial | 0 |

### Identity Profiles (data field)

The pipeline classifies each athlete with an `identity_profile` field, which surfaces in the corridor drawer rosters:

| Profile | Athletes | Meaning |
| --- | ---: | --- |
| `aligned` | 8,456 | Birthplace, nationality, and represented team align or can be treated as aligned. |
| `unknown` | 1,638 | Missing data prevents classification. |
| `naturalized` | 862 | Born abroad, but nationality aligns with represented team. |
| `passport_only` | 144 | Representation is supported by eligibility/passport data, but birth country differs. |
| `triple_mismatch` | 13 | Birth country, nationality, and represented team are all different. |

### Explore Map Tab

The map uses Leaflet with CARTO tiles and supports:

- Represented-team bubbles.
- Birthplace-city bubbles.
- Corridor arcs.
- Two documentary-style animated corridor scenes: all 975 cross-border athletes and the 138 cross-border medal-winning athletes.
- Play, pause, restart, progress narration, and clickable routes after each scene completes.
- Marker sizing by count or share.
- City filter for only cross-border birthplace hubs.
- Clickable markers and arcs with detail drawers.

City coordinates come from a static map, a local cache, and fallback country centroids. Invalid sentinel coordinates are excluded from map rendering.

## Data Pipeline

`pipeline.py` is the main data-generation script.

It reads the Paris 2024 Kaggle dataset from this local cache path:

```text
C:\Users\Pratham\.cache\kagglehub\datasets\piterfm\paris-2024-olympic-summer-games\versions\27
```

Expected input files include:

- `athletes.csv`
- `nocs.csv`
- `medallists.csv`
- `medals_total.csv`

The pipeline:

1. Loads athlete records.
2. Normalizes country, NOC, nationality, residence, and birthplace fields.
3. Extracts birth year and age at the Games when possible.
4. Classifies diaspora/cross-border representation.
5. Classifies identity profiles.
6. Joins medal information by athlete.
7. Tags diaspora athletes with corridor-derived diaspora types.
8. Aggregates country, city, sport, and corridor statistics.
9. Computes reverse corridor counts and asymmetry.
10. Writes dashboard JSON files into `data/`.

### Classification Logic

The core rule is:

> An athlete is treated as cross-border / diaspora when their recorded birth country differs from the NOC or country they represented after NOC, territory, and country-alias rules are applied.

Special cases include:

- Great Britain constituent countries and selected territories.
- France and French overseas territories.
- Kingdom of the Netherlands cases.
- Denmark, Faroe Islands, and Greenland.
- United States and U.S. territories.
- Puerto Rico native athletes.
- Hong Kong, Chinese Taipei, Taiwan, and China.
- Common aliases such as USA, United Kingdom, Turkey/Trkiye, Korea, Iran, UAE, Moldova, Hong Kong, and Chinese Taipei.

The current reason-code counts are:

| Reason | Count |
| --- | ---: |
| `direct_match` | 8,492 |
| `missing_birth_data` | 1,638 |
| `diaspora` | 975 |
| `den_kingdom` | 2 |
| `fra_territory` | 2 |
| `ned_kingdom` | 2 |
| `gbr_constituent` | 1 |
| `usa_territory` | 1 |

## Insight Mining

`insights.py` reads the generated JSON files and writes `data/insights.json`.

It detects and ranks findings such as:

- Large training-abroad host countries.
- Refugee/neutral team caveats.
- Medal overperformance among diaspora athletes by NOC or sport.
- One-way corridor asymmetry.
- Sport outliers.
- Small-NOC dependency.
- Split birthplace cities.
- Triple mismatches.
- Training-abroad patterns.
- Age gaps.
- Potential family/dynasty patterns.

Current top generated insight:

```text
United States is the largest recorded training-abroad host country:
507 athletes with residence_country present and trains_abroad true.
```

`data/insights.json` currently contains 86 insight records.

## Data Outputs

### `data/olympics_diaspora.json`

One processed record per athlete.

Fields include:

- `code`
- `name`
- `gender`
- `rep_noc`
- `rep_country`
- `nationality`
- `nationality_code`
- `birth_place`
- `birth_country`
- `residence_country`
- `residence_place`
- `residence_status`
- `trains_abroad`
- `birth_year`
- `age_at_games`
- `sport`
- `is_diaspora`
- `diaspora_reason`
- `identity_profile`
- `diaspora_type`
- `medals`
- `medal_count`

### `data/country_stats.json`

One entry per represented NOC/country.

Fields include:

- `noc`
- `country`
- `total_athletes`
- `total_records_with_birthplace_data`
- `total_classified_birthplace_records`
- `inferred_homegrown_count`
- `homegrown_count`
- `foreign_born_count`
- `foreign_born_pct`
- `medal_count`
- `medal_winning_athletes`
- `diaspora_medal_count`
- `diaspora_medal_pct`
- `top_source_countries`
- `coords`

### `data/city_stats.json`

One entry per birth city group.

Fields include:

- `id`
- `city`
- `birth_country`
- `coords`
- `total_born`
- `diaspora_count`
- `homegrown_count`
- `diaspora_pct`
- `represented_nocs`
- `represented_countries`
- `sports`
- `diaspora_athletes`
- `all_athletes`

### `data/sport_stats.json`

One entry per sport.

Fields include:

- `sport`
- `total_athletes`
- `total_records_with_birthplace_data`
- `total_classified_birthplace_records`
- `inferred_homegrown_count`
- `homegrown_count`
- `diaspora_count`
- `diaspora_pct`
- `medal_count`
- `medal_winning_athletes`
- `diaspora_medal_count`
- `diaspora_medal_pct`
- `top_source_countries`
- `top_represented_countries`

### `data/corridor_stats.json`

One entry per directional corridor.

Fields include:

- `birth_country`
- `rep_country`
- `athlete_count`
- `corridor_type`
- `reverse_count`
- `asymmetry`
- `medal_count`
- `sports`
- `athletes`

### `data/summary_stats.json`

Project-level summary metrics used for reporting and QA.

Fields include:

- `total_athletes`
- `known_birthplace_athletes`
- `diaspora_athletes`
- `diaspora_share_all_athletes`
- `total_medal_winning_athletes`
- `diaspora_medal_winning_athletes`
- `diaspora_share_medal_winners`
- `diaspora_medalist_vs_all_delta`
- `excluding_eor_ain`
- `medal_reconciliation`

### `data/insights.json`

Generated research findings (86 records). Consumed by [`FINDINGS.md`](FINDINGS.md), not loaded by the frontend.

### `data/training_stats.json`

Residence-based training proxy summaries, including coverage, host countries, represented-team home/abroad shares, sport summaries, and represented-country-to-residence-country corridors.

### `data/stories.json`

Hand-curated headline stories retained as a research artifact. Not generated by the pipeline and not loaded by the frontend.

Each insight includes:

- `id`
- `category`
- `headline`
- `value`
- `baseline`
- `score`
- `evidence`

### `data/city_coords_cache.json`

Local coordinate cache used by the pipeline and frontend city mapping logic.

## Run the Dashboard

The dashboard loads JSON with `fetch()`, so serve the project through a local web server. Opening `index.html` directly with a `file://` URL may block data loading.

From the project root:

```powershell
py -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

If `py` or `python` is misconfigured, the bundled Codex Python runtime works on this machine:

```powershell
C:\Users\Pratham\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m http.server 8000
```

## Regenerate Data

Install dependencies if needed:

```powershell
pip install pandas numpy geopy
```

Run the pipeline:

```powershell
py pipeline.py
```

Run insight mining:

```powershell
py insights.py
```

If the default Python launcher is broken, use the bundled runtime:

```powershell
C:\Users\Pratham\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe pipeline.py
C:\Users\Pratham\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe insights.py
```

## Dependencies

Frontend:

- Leaflet 1.9.4 from CDN.
- CARTO dark map tiles.
- Plain HTML, CSS, and JavaScript.

Pipeline:

- Python.
- pandas.
- numpy.
- geopy.
- Local Paris 2024 Kaggle CSV files.

## Data and interpretation notes

- The repository contains generated dashboard JSON outputs, not the original Kaggle source cache.
- Re-running the pipeline requires the expected Paris 2024 CSV files and may produce different counts if the source data changes.
- Missing birthplace or residence values are excluded from the corresponding known-data denominators.
- Residence country is a proxy for likely training base; it is not verified training-location data.
- EOR and AIN are structurally foreign-born in this framing and should be interpreted separately.
- Country, territory, and NOC equivalence rules prevent administrative label differences from being treated as international movement.
