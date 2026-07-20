"""
generate_identity_dashboard.py
Step 6: Generate the Identity-Hostility Dashboard static HTML.

Reads aggregate_results.parquet and embeds all data as JSON.
Output is a single self-contained HTML file — no external dependencies at runtime.

USER RUNS THIS:
    python generate_identity_dashboard.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from identity_common import OUTPUT_DIR, log, abort

DASHBOARD_OUT = Path(__file__).parent / "dashboard" / "identity_hostility_dashboard.html"
METHODOLOGY_DOC = Path(__file__).parent / "docs" / "methodology_and_limitations.md"


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_aggregate(path: Path) -> dict:
    """Load aggregate_results.parquet and reshape into panel-friendly dicts."""
    if not path.exists():
        abort(f"aggregate_results.parquet not found at {path}. Run aggregate_results.py first.")
    df = pd.read_parquet(path)

    def _bd(name: str) -> list[dict]:
        sub = df[df["breakdown"] == name].copy()
        return sub.to_dict(orient="records")

    return {
        "headline": _bd("headline"),
        "by_match": _bd("by_match"),
        "by_stage": _bd("by_stage"),
        "by_subreddit": _bd("by_subreddit"),
        "by_language": _bd("by_language"),
        "overlap": _bd("overlap"),
    }


def load_methodology(md_path: Path) -> str:
    if md_path.exists():
        return md_path.read_text(encoding="utf-8")
    return "Methodology document not found. Run generate_identity_dashboard.py after creating docs/methodology_and_limitations.md."


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Identity-Hostility Dashboard — World Cup 2026</title>
  <style>
    @import url("https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,600;0,700;0,800;0,900;1,800&family=IBM+Plex+Mono:wght@400;500;600&family=Space+Grotesk:wght@400;500;600;700&display=swap");

    :root {
      color-scheme: light;
      --pitch-haze: #C7D7B1;
      --ink: #17231E;
      --paper: #F2F0E8;
      --signal-blue: #1E5AA8;
      --card-yellow: #F4C542;
      --card-red: #D93632;
      --line: 3px solid var(--ink);
      --shadow: 6px 6px 0 var(--ink);
      --shadow-sm: 3px 3px 0 var(--ink);
    }

    * { box-sizing: border-box; }
    html { background: var(--pitch-haze); }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(rgba(23,35,30,0.055) 3px, transparent 3px),
        linear-gradient(90deg, rgba(23,35,30,0.055) 3px, transparent 3px),
        var(--pitch-haze);
      background-size: 28px 28px;
      color: var(--ink);
      font-family: "Space Grotesk", ui-sans-serif, system-ui, sans-serif;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      z-index: 1000;
      pointer-events: none;
      background: repeating-linear-gradient(0deg, rgba(23,35,30,0.09) 0, rgba(23,35,30,0.09) 1px, transparent 1px, transparent 5px);
      mix-blend-mode: multiply;
      opacity: 0.22;
    }
    main { width: min(1440px, calc(100vw - 32px)); margin: 0 auto; padding: 28px 0 56px; }
    h1,h2,h3,p { margin: 0; }
    h1 {
      font-size: clamp(28px, 4vw, 52px);
      line-height: 0.92;
      font-family: "Barlow Condensed", ui-sans-serif, sans-serif;
      font-weight: 900;
      text-transform: uppercase;
      color: var(--ink);
      text-shadow: 4px 4px 0 var(--signal-blue);
    }
    h2 {
      font-family: "Barlow Condensed", ui-sans-serif, sans-serif;
      font-size: 22px;
      line-height: 0.95;
      font-weight: 800;
      text-transform: uppercase;
    }
    h3 {
      color: var(--ink);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    /* ---- Hero ---- */
    .hero {
      position: relative;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 22px;
      align-items: start;
      padding: 20px;
      border: var(--line);
      background: var(--paper);
      box-shadow: var(--shadow);
      margin-bottom: 22px;
    }
    .hero .lede {
      margin-top: 12px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 13px;
      line-height: 1.6;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      max-width: 780px;
    }
    .hero-numbers {
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-width: 200px;
    }
    .stat-card {
      border: var(--line);
      background: var(--card-yellow);
      box-shadow: var(--shadow-sm);
      padding: 12px 16px;
    }
    .stat-card.blue { background: var(--signal-blue); color: var(--paper); }
    .stat-card.red { background: var(--card-red); color: var(--paper); }
    .stat-label {
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      opacity: 0.8;
    }
    .stat-value {
      font-family: "Barlow Condensed", ui-sans-serif, sans-serif;
      font-size: 36px;
      font-weight: 900;
      line-height: 1;
      margin-top: 2px;
    }

    /* ---- Panels ---- */
    .panels {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
      gap: 22px;
    }
    .panel {
      border: var(--line);
      background: var(--paper);
      box-shadow: var(--shadow);
      padding: 18px;
    }
    .panel-title {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 14px;
      border-bottom: 2px solid var(--ink);
      padding-bottom: 10px;
    }
    .panel-full { grid-column: 1 / -1; }

    /* ---- Bar chart ---- */
    .bar-list { display: grid; gap: 7px; }
    .bar-row { display: grid; gap: 4px; }
    .bar-row-label {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 13px;
      font-weight: 600;
    }
    .bar-row-label .pct {
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 12px;
      color: var(--signal-blue);
    }
    .bar-track {
      height: 14px;
      background: rgba(23,35,30,0.12);
      border: 1px solid rgba(23,35,30,0.25);
      position: relative;
      overflow: hidden;
    }
    .bar-fill {
      position: absolute;
      top: 0; left: 0;
      height: 100%;
      transition: width 600ms cubic-bezier(.4,0,.2,1);
    }
    .bar-fill.racial-ethnic { background: var(--card-red); }
    .bar-fill.nationality { background: var(--signal-blue); }
    .bar-fill.any-flag { background: var(--ink); }
    .bar-fill.unsupported { background: rgba(23,35,30,0.35); }
    .bar-n {
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 10px;
      color: rgba(23,35,30,0.55);
    }

    /* ---- 2x2 overlap ---- */
    .overlap-grid {
      display: grid;
      grid-template-columns: auto 1fr 1fr;
      gap: 4px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 12px;
    }
    .overlap-cell {
      border: 2px solid var(--ink);
      padding: 12px;
      text-align: center;
    }
    .overlap-cell.header {
      background: var(--ink);
      color: var(--paper);
      font-weight: 600;
      font-size: 11px;
    }
    .overlap-cell.high { background: var(--card-red); color: var(--paper); }
    .overlap-cell.mid { background: var(--card-yellow); }
    .overlap-cell.low { background: var(--paper); }
    .overlap-n { font-size: 20px; font-weight: 700; display: block; }
    .overlap-pct { font-size: 11px; opacity: 0.75; }

    /* ---- Methodology panel ---- */
    .methodology {
      background: var(--ink);
      color: var(--paper);
      border: var(--line);
      box-shadow: var(--shadow);
      padding: 20px;
      grid-column: 1 / -1;
    }
    .methodology h2 { color: var(--card-yellow); margin-bottom: 12px; }
    .methodology ul {
      margin: 0; padding-left: 18px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 13px;
      line-height: 1.7;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .methodology li { margin-bottom: 4px; }
    .caveat-badge {
      display: inline-block;
      background: var(--card-red);
      color: var(--paper);
      border: 2px solid var(--paper);
      padding: 3px 8px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 10px;
    }

    /* ---- Legend ---- */
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 14px;
    }
    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
    }
    .legend-swatch {
      width: 14px;
      height: 14px;
      border: 2px solid var(--ink);
      flex-shrink: 0;
    }
    .legend-swatch.racial-ethnic { background: var(--card-red); }
    .legend-swatch.nationality { background: var(--signal-blue); }
    .legend-swatch.unsupported { background: rgba(23,35,30,0.35); }

    .filter-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }
    .filter-btn {
      border: 2px solid var(--ink);
      background: var(--paper);
      color: var(--ink);
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      padding: 5px 10px;
      cursor: pointer;
      box-shadow: 2px 2px 0 var(--ink);
    }
    .filter-btn.active, .filter-btn:hover {
      background: var(--ink);
      color: var(--paper);
    }

    @keyframes barIn {
      from { width: 0 !important; }
    }

    @media (max-width: 760px) {
      .hero { grid-template-columns: 1fr; }
      .hero-numbers { flex-direction: row; flex-wrap: wrap; }
      .panels { grid-template-columns: 1fr; }
      .panel-full { grid-column: 1; }
    }
  </style>
</head>
<body>
<main>

  <!-- Hero -->
  <div class="hero">
    <div>
      <h1>Identity-Hostility<br>Detected Rates</h1>
      <p class="lede">
        Model-flagged analysis of racial/ethnic and nationality-based hostile language
        in 457,898 Reddit comments across 100+ World Cup 2026 match threads.
        All rates are model-detected — not human-verified.
        No individual comments, usernames, or slurs are shown.
      </p>
    </div>
    <div class="hero-numbers" id="hero-numbers">
      <!-- Populated by JS -->
    </div>
  </div>

  <!-- All panels -->
  <div class="panels" id="panels">

    <!-- Panel 1: By stage -->
    <div class="panel">
      <div class="panel-title"><h2>By tournament stage</h2></div>
      <div class="legend">
        <div class="legend-item"><div class="legend-swatch racial-ethnic"></div> Racial/ethnic</div>
        <div class="legend-item"><div class="legend-swatch nationality"></div> Nationality</div>
      </div>
      <div class="bar-list" id="stage-bars"></div>
    </div>

    <!-- Panel 2: By subreddit -->
    <div class="panel">
      <div class="panel-title"><h2>By subreddit</h2></div>
      <div class="filter-bar" id="subreddit-filter"></div>
      <div class="bar-list" id="subreddit-bars"></div>
    </div>

    <!-- Panel 3: By language -->
    <div class="panel">
      <div class="panel-title"><h2>By detected language</h2></div>
      <div class="legend">
        <div class="legend-item"><div class="legend-swatch racial-ethnic"></div> Racial/ethnic</div>
        <div class="legend-item"><div class="legend-swatch nationality"></div> Nationality</div>
        <div class="legend-item"><div class="legend-swatch unsupported"></div> Model unsupported lang</div>
      </div>
      <div class="bar-list" id="language-bars"></div>
    </div>

    <!-- Panel 4: Profanity × identity overlap -->
    <div class="panel">
      <div class="panel-title"><h2>Profanity ✕ identity flag overlap</h2></div>
      <p style="font-family:'IBM Plex Mono',monospace;font-size:12px;text-transform:uppercase;opacity:0.7;margin-bottom:14px;">
        Profanity = swear_count &gt; 0 (from Swearing WC scorer)
      </p>
      <div class="overlap-grid" id="overlap-grid"></div>
    </div>

    <!-- Panel 5: By match (full width) -->
    <div class="panel panel-full">
      <div class="panel-title"><h2>By match</h2></div>
      <div class="legend">
        <div class="legend-item"><div class="legend-swatch racial-ethnic"></div> Racial/ethnic rate</div>
        <div class="legend-item"><div class="legend-swatch nationality"></div> Nationality rate</div>
      </div>
      <p style="font-family:'IBM Plex Mono',monospace;font-size:11px;opacity:0.6;text-transform:uppercase;margin-bottom:12px;">
        Matches with n &lt; 100 comments shown with reduced opacity.
      </p>
      <div class="bar-list" id="match-bars"></div>
    </div>

    <!-- Panel 6: Methodology (always visible) -->
    <div class="methodology">
      <div class="caveat-badge">⚠ Methodology &amp; Limitations — always visible</div>
      <h2>How to read these numbers</h2>
      <ul id="methodology-list"></ul>
    </div>

  </div>
</main>

<script>
// ---- Embedded aggregate data (injected at generation time) ----
const AGGREGATE = __AGGREGATE_JSON__;
const METHODOLOGY_POINTS = __METHODOLOGY_POINTS_JSON__;

// ---- Helpers ----
const pct = (r) => (r == null ? "—" : (r * 100).toFixed(2) + "%");
const fmt = (n) => n == null ? "—" : n.toLocaleString();

function bar(fillClass, widthPct, title) {
  const w = Math.min(widthPct * 100, 100);
  return `<div class="bar-track" title="${title}"><div class="bar-fill ${fillClass}" style="width:${w}%;animation:barIn 600ms ease"></div></div>`;
}

// ---- Panel: headline stat cards ----
function renderHero() {
  const h = AGGREGATE.headline[0] || {};
  const container = document.getElementById("hero-numbers");
  const cards = [
    { label: "Total comments", value: fmt(h.n), cls: "" },
    { label: "Racial/ethnic detected rate", value: pct(h.racial_ethnic_rate), cls: "red" },
    { label: "Nationality detected rate", value: pct(h.nationality_rate), cls: "blue" },
    { label: "Model-unsupported language share", value: pct(h.model_unsupported_rate), cls: "" },
  ];
  container.innerHTML = cards.map(c =>
    `<div class="stat-card ${c.cls}">
       <div class="stat-label">${c.label}</div>
       <div class="stat-value">${c.value}</div>
     </div>`
  ).join("");
}

// ---- Generic horizontal bar list ----
function renderBarList(containerId, rows, labelKey, rate1Key, rate1Class, rate1Label, rate2Key, rate2Class, rate2Label, minN) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const html = rows.map(row => {
    const thin = (row.n || 0) < (minN || 100);
    return `<div class="bar-row" style="opacity:${thin ? 0.45 : 1}">
      <div class="bar-row-label">
        <span>${row[labelKey] || "unknown"}</span>
        <span class="pct">${pct(row[rate1Key])} RE / ${pct(row[rate2Key])} NAT <span class="bar-n">n=${fmt(row.n)}</span></span>
      </div>
      ${bar(rate1Class, row[rate1Key] || 0, `${rate1Label}: ${pct(row[rate1Key])}`)}
      ${bar(rate2Class, row[rate2Key] || 0, `${rate2Label}: ${pct(row[rate2Key])}`)}
    </div>`;
  }).join("");
  container.innerHTML = html;
}

// ---- Panel: by stage ----
function renderStage() {
  const rows = (AGGREGATE.by_stage || []).slice().sort((a,b) => (b.any_flagged_rate||0)-(a.any_flagged_rate||0));
  renderBarList("stage-bars", rows, "group", "racial_ethnic_rate", "racial-ethnic", "Racial/ethnic", "nationality_rate", "nationality", "Nationality", 0);
}

// ---- Panel: by subreddit ----
let subredditShowAll = false;
function renderSubreddit() {
  let rows = (AGGREGATE.by_subreddit || []).slice().sort((a,b)=>(b.n||0)-(a.n||0));
  const filterBar = document.getElementById("subreddit-filter");
  if (!subredditShowAll) rows = rows.slice(0, 12);
  filterBar.innerHTML = `
    <button class="filter-btn ${subredditShowAll ? "" : "active"}" onclick="subredditShowAll=false;renderSubreddit()">Top 12</button>
    <button class="filter-btn ${subredditShowAll ? "active" : ""}" onclick="subredditShowAll=true;renderSubreddit()">All</button>`;
  renderBarList("subreddit-bars", rows, "group", "racial_ethnic_rate", "racial-ethnic", "Racial/ethnic", "nationality_rate", "nationality", "Nationality", 50);
}

// ---- Panel: by language ----
function renderLanguage() {
  const rows = (AGGREGATE.by_language || []).slice().sort((a,b)=>(b.n||0)-(a.n||0));
  const container = document.getElementById("language-bars");
  const html = rows.map(row => {
    const isUnsup = row.group === "unknown" || row.model_unsupported_n === row.n;
    const thin = (row.n || 0) < 50;
    return `<div class="bar-row" style="opacity:${thin ? 0.4 : 1}">
      <div class="bar-row-label">
        <span>${row.group || "unknown"}${isUnsup ? " <small style='opacity:.6'>(model unsupported)</small>" : ""}</span>
        <span class="pct">${pct(row.racial_ethnic_rate)} RE / ${pct(row.nationality_rate)} NAT <span class="bar-n">n=${fmt(row.n)}</span></span>
      </div>
      ${bar("racial-ethnic", row.racial_ethnic_rate||0, "Racial/ethnic: "+pct(row.racial_ethnic_rate))}
      ${bar("nationality", row.nationality_rate||0, "Nationality: "+pct(row.nationality_rate))}
    </div>`;
  }).join("");
  container.innerHTML = html;
}

// ---- Panel: overlap 2x2 ----
function renderOverlap() {
  const cells = AGGREGATE.overlap || [];
  const lookup = {};
  cells.forEach(c => { lookup[c.group] = c; });

  const total = cells.reduce((s,c)=>s+(c.n||0),0);
  function cellClass(n) {
    const r = total > 0 ? n/total : 0;
    if (r > 0.1) return "high";
    if (r > 0.02) return "mid";
    return "low";
  }

  function cell(profanity, identity) {
    const key = `profanity=${profanity ? "yes" : "no"}_identity=${identity ? "yes" : "no"}`;
    const c = lookup[key] || { n: 0, rate: 0 };
    return `<div class="overlap-cell ${cellClass(c.n)}">
      <span class="overlap-n">${fmt(c.n)}</span>
      <span class="overlap-pct">${pct(c.rate)}</span>
    </div>`;
  }

  document.getElementById("overlap-grid").innerHTML = `
    <div class="overlap-cell header"></div>
    <div class="overlap-cell header">No identity flag</div>
    <div class="overlap-cell header">Identity flagged</div>
    <div class="overlap-cell header">No profanity</div>
    ${cell(false, false)}${cell(false, true)}
    <div class="overlap-cell header">Has profanity</div>
    ${cell(true, false)}${cell(true, true)}`;
}

// ---- Panel: by match ----
function renderMatch() {
  const rows = (AGGREGATE.by_match || []).slice().sort((a,b)=>(b.any_flagged_rate||0)-(a.any_flagged_rate||0));
  renderBarList("match-bars", rows, "group", "racial_ethnic_rate", "racial-ethnic", "Racial/ethnic", "nationality_rate", "nationality", "Nationality", 100);
}

// ---- Panel: methodology ----
function renderMethodology() {
  const ul = document.getElementById("methodology-list");
  ul.innerHTML = METHODOLOGY_POINTS.map(p => `<li>${p}</li>`).join("");
}

// ---- Init ----
renderHero();
renderStage();
renderSubreddit();
renderLanguage();
renderOverlap();
renderMatch();
renderMethodology();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Methodology bullet points (mirrors what's in docs/methodology_and_limitations.md)
# ---------------------------------------------------------------------------

METHODOLOGY_POINTS = [
    "All rates are MODEL-DETECTED — not human-verified. A flag means the model or lexicon matched; it does not confirm a racist or xenophobic incident.",
    "Data source: 457,898 deduplicated Reddit comments from World Cup 2026 match threads collected via Arctic Shift. This describes Reddit comment behaviour in these threads only — not any country's fanbase, team, or general population.",
    "Flag method: two-signal combination — (1) a private keyword lexicon for racial/ethnic and nationality/xenophobia terms; (2) Detoxify multilingual model (unitary/multilingual-toxic-xlm-roberta) scoring identity-based hostility. A comment is flagged if either signal exceeds the configured threshold.",
    "Language coverage: Detoxify multilingual supports en, fr, es, it, pt, tr, ru. Comments in other detected languages are marked 'model_unsupported' — the lexicon still applies, but no model score is generated. Model-unsupported comments that are not lexicon hits are neither flagged nor unflagged; they are reported separately.",
    "Attribution: flag rates are shown by match, stage, subreddit, and language — not by country or fanbase. Subreddit identity is not the same as speaker nationality.",
    "Profanity is a secondary signal only. The swear_count field comes from the Swearing World Cup scorer and is shown in the overlap panel to illustrate co-occurrence, not to imply that profanity equals hostility.",
    "No individual comments, usernames, or raw text are shown anywhere in this dashboard.",
    "No slurs appear in any output, label, or category name.",
    "No 'most hostile' rankings. All panels show rates, not competitive orderings.",
    "Thresholds are configurable in config/flag_config.json. Defaults were calibrated against a ~200-row manual review sample.",
]


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate(aggregate_path: Path, out_path: Path) -> None:
    log(f"[dashboard] Loading aggregate from {aggregate_path} ...")
    agg = load_aggregate(aggregate_path)

    methodology = METHODOLOGY_POINTS  # always use code-controlled list

    agg_json = json.dumps(agg, ensure_ascii=False, indent=None)
    meth_json = json.dumps(methodology, ensure_ascii=False)

    html = HTML_TEMPLATE.replace("__AGGREGATE_JSON__", agg_json)
    html = html.replace("__METHODOLOGY_POINTS_JSON__", meth_json)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    log(f"[dashboard] Wrote -> {out_path}")
    log("Open the HTML file directly in a browser — no server required.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate identity-hostility dashboard HTML.")
    p.add_argument(
        "--aggregate", default=str(OUTPUT_DIR / "aggregate_results.parquet"),
    )
    p.add_argument("--out", default=str(DASHBOARD_OUT))
    return p.parse_args()


def main() -> int:
    args = parse_args()
    generate(Path(args.aggregate), Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
