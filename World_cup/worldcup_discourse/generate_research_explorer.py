import csv
import html
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
BASIC_REPORT_DIR = BASE_DIR / "reports" / "phase2_basic_results"
REPORT_DIR = BASE_DIR / "reports" / "research_explorer"

IDENTITY_CATEGORIES = {
    "immigration": {"immigrant", "immigrants", "immigration", "migrant", "migrants", "refugee", "refugees", "asylum"},
    "nationality": {"nationality", "nation", "national", "country", "english", "french", "german", "australian", "canadian"},
    "race": {"race", "racism", "racist", "black", "white", "asian", "african", "asians"},
    "religion": {"religion", "religious", "muslim", "islam", "christian", "jewish"},
    "foreignness": {"foreign", "foreigner", "foreigners", "outsider"},
    "citizenship": {"citizen", "citizenship", "passport", "born", "naturalized", "naturalised"},
    "belonging": {"belong", "belongs", "home", "represent", "representation", "heritage"},
    "ethnicity": {"ethnic", "ethnicity", "diaspora", "origin", "roots"},
}


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def norm_text(value):
    return str(value or "").strip()


def percent(part, whole):
    return 0 if not whole else round((part / whole) * 100, 2)


def rate100(part, whole):
    return 0 if not whole else round((part / whole) * 100, 2)


def signed_sentiment(label, score):
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0
    if label == "positive":
        return score
    if label == "negative":
        return -score
    return 0


def frame_terms(terms, categories):
    found = set()
    haystack = {term.lower() for term in terms}
    for category, lexicon in IDENTITY_CATEGORIES.items():
        if haystack & lexicon:
            found.add(category)
    category_text = " ".join(categories).lower()
    if "identity" in category_text and not found:
        found.add("belonging")
    if "racism" in category_text or "discrimination" in category_text:
        found.add("race")
    return sorted(found) or ["identity"]


def load_sentiment():
    sentiment = {}
    rows = []
    for path in sorted(PROCESSED_DIR.glob("*_sentiment.jsonl")):
        for record in read_jsonl(path):
            record_id = norm_text(record.get("record_id") or record.get("id"))
            if not record_id:
                continue
            label = record.get("sentiment_label") or "unknown"
            item = {
                "label": label,
                "score": record.get("sentiment_score") or 0,
                "signed": signed_sentiment(label, record.get("sentiment_score")),
            }
            sentiment[record_id] = item
            rows.append(item)
    return sentiment, rows


def load_identity_audit():
    path = BASIC_REPORT_DIR / "flagged_context_audit" / "flagged_context_audit.csv"
    by_record = {}
    rows = []
    for row in read_csv(path):
        record_id = norm_text(row.get("record_id"))
        terms = [term.strip().lower() for term in norm_text(row.get("matched_words")).split(";") if term.strip()]
        categories = [term.strip() for term in norm_text(row.get("categories")).split(";") if term.strip()]
        frames = frame_terms(terms, categories)
        item = {
            "record_id": record_id,
            "match_id": norm_text(row.get("match_id")),
            "community": norm_text(row.get("source")),
            "categories": categories,
            "terms": terms,
            "frames": frames,
            "likely": norm_text(row.get("likely_about_player")).lower(),
            "players": [name.strip() for name in norm_text(row.get("players_mentioned")).split(";") if name.strip()],
            "text": norm_text(row.get("text_preview")),
            "url": norm_text(row.get("url")),
            "language": "",
        }
        if record_id:
            by_record[record_id] = item
        rows.append(item)
    return by_record, rows


def blank_group(name):
    return {
        "name": name,
        "mentions": 0,
        "sentimentScored": 0,
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "avgSentiment": 0,
        "_sentimentSum": 0,
        "identity": 0,
        "immigration": 0,
        "abusive": 0,
        "communities": Counter(),
        "languages": Counter(),
        "matches": Counter(),
        "players": Counter(),
        "terms": Counter(),
        "frames": Counter(),
        "examples": [],
    }


def add_example(group, record, identity=None):
    if len(group["examples"]) >= 8:
        return
    text = norm_text(record.get("text")) or norm_text(record.get("body")) or (identity or {}).get("text", "")
    if not text:
        return
    group["examples"].append(
        {
            "text": text[:420],
            "player": "",
            "match": record.get("match_id", ""),
            "community": record.get("subreddit") or record.get("source") or "",
            "language": record.get("lang") or "",
            "sentiment": (record.get("_sentiment") or {}).get("label", "not scored"),
            "keywords": ", ".join((identity or {}).get("terms", [])[:6]),
            "url": record.get("permalink") or (identity or {}).get("url", ""),
        }
    )


def finalize_group(group):
    mentions = group["mentions"]
    scored = group["sentimentScored"]
    group["positivePct"] = percent(group["positive"], scored)
    group["neutralPct"] = percent(group["neutral"], scored)
    group["negativePct"] = percent(group["negative"], scored)
    group["identityRate"] = rate100(group["identity"], mentions)
    group["immigrationRate"] = rate100(group["immigration"], mentions)
    group["abusiveRate"] = rate100(group["abusive"], mentions)
    group["avgSentiment"] = round(group["_sentimentSum"] / scored, 3) if scored else 0
    group["communityConcentration"] = concentration(group["communities"])
    group["languageDiversity"] = diversity(group["languages"])
    for key in ["communities", "languages", "matches", "players", "terms", "frames"]:
        group[key] = [{"name": name, "value": value} for name, value in group[key].most_common(10)]
    group.pop("_sentimentSum", None)
    return group


def concentration(counter):
    total = sum(counter.values())
    if not total:
        return 0
    return round(max(counter.values()) / total, 3)


def diversity(counter):
    total = sum(counter.values())
    if not total:
        return 0
    entropy = 0
    for value in counter.values():
        p = value / total
        entropy -= p * math.log(p)
    max_entropy = math.log(max(len(counter), 1))
    return round(entropy / max_entropy, 3) if max_entropy else 0


def apply_record(group, record, sentiment, identity):
    group["mentions"] += 1
    community = record.get("subreddit") or record.get("source") or "unknown"
    language = record.get("lang") or "unknown"
    match_id = record.get("match_id") or "unknown"
    group["communities"][community] += 1
    group["languages"][language] += 1
    group["matches"][match_id] += 1
    if sentiment:
        label = sentiment["label"]
        if label in {"positive", "neutral", "negative"}:
            group["sentimentScored"] += 1
            group[label] += 1
            group["_sentimentSum"] += sentiment["signed"]
    if identity:
        group["identity"] += 1
        for term in identity["terms"]:
            group["terms"][term] += 1
        for frame in identity["frames"]:
            group["frames"][frame] += 1
        if "immigration" in identity["frames"]:
            group["immigration"] += 1
        if "abusive_or_hard_language" in " ".join(identity["categories"]):
            group["abusive"] += 1
        add_example(group, record, identity)


def load_research_data():
    sentiment_by_record, sentiment_rows = load_sentiment()
    identity_by_record, identity_rows = load_identity_audit()

    players = defaultdict(lambda: blank_group(""))
    matches = defaultdict(lambda: blank_group(""))
    communities = defaultdict(lambda: blank_group(""))
    languages = defaultdict(lambda: blank_group(""))
    records_seen = {}
    all_matches = set()
    all_languages = set()

    for path in sorted(PROCESSED_DIR.glob("*_lang.jsonl")):
        match_id = path.stem[: -len("_lang")]
        for record in read_jsonl(path):
            record["match_id"] = record.get("match_id") or match_id
            record_id = norm_text(record.get("record_id") or record.get("id"))
            if not record_id:
                continue
            sentiment = sentiment_by_record.get(record_id)
            if sentiment:
                record["_sentiment"] = sentiment
            identity = identity_by_record.get(record_id)
            community = record.get("subreddit") or record.get("source") or "unknown"
            language = record.get("lang") or "unknown"
            all_matches.add(record["match_id"])
            all_languages.add(language)
            records_seen[record_id] = record

            mentions = record.get("mentions") or record.get("matched_players") or []
            if not mentions:
                continue
            for mention in mentions:
                player = norm_text(mention.get("name"))
                if not player:
                    continue
                players[player]["name"] = player
                matches[record["match_id"]]["name"] = record["match_id"]
                communities[community]["name"] = community
                languages[language]["name"] = language
                players[player]["players"][player] += 1
                matches[record["match_id"]]["players"][player] += 1
                communities[community]["players"][player] += 1
                languages[language]["players"][player] += 1
                apply_record(players[player], record, sentiment, identity)
                apply_record(matches[record["match_id"]], record, sentiment, identity)
                apply_record(communities[community], record, sentiment, identity)
                apply_record(languages[language], record, sentiment, identity)

    for identity in identity_rows:
        record = records_seen.get(identity["record_id"], {
            "match_id": identity["match_id"],
            "subreddit": identity["community"],
            "lang": identity.get("language") or "unknown",
            "text": identity["text"],
            "_sentiment": sentiment_by_record.get(identity["record_id"], {"label": "not scored"}),
        })
        for player in identity["players"]:
            if player in players:
                players[player]["frames"].update(identity["frames"])
                players[player]["terms"].update(identity["terms"])

    player_list = sorted((finalize_group(v) for v in players.values()), key=lambda row: (row["identityRate"], row["mentions"]), reverse=True)
    match_list = sorted((finalize_group(v) for v in matches.values()), key=lambda row: (row["identityRate"], row["mentions"]), reverse=True)
    community_list = sorted((finalize_group(v) for v in communities.values()), key=lambda row: (row["identityRate"], row["mentions"]), reverse=True)
    language_list = sorted((finalize_group(v) for v in languages.values()), key=lambda row: (row["identityRate"], row["mentions"]), reverse=True)

    identity_frames = []
    frame_counts = Counter()
    frame_examples = defaultdict(list)
    for row in identity_rows:
        for frame in row["frames"]:
            frame_counts[frame] += 1
            if len(frame_examples[frame]) < 5:
                frame_examples[frame].append({
                    "text": row["text"][:420],
                    "player": "; ".join(row["players"][:4]),
                    "match": row["match_id"],
                    "community": row["community"],
                    "keywords": ", ".join(row["terms"][:6]),
                })
    for frame, count in frame_counts.most_common():
        identity_frames.append({"name": frame, "count": count, "examples": frame_examples[frame]})

    scored = [row for row in sentiment_rows if row["label"] in {"positive", "neutral", "negative"}]
    summary = {
        "totalComments": sum(int(row.get("comments") or 0) for row in read_csv(BASIC_REPORT_DIR / "raw_volume_by_match.csv")),
        "totalMatches": len(all_matches),
        "playersMentioned": len(player_list),
        "languages": len([lang for lang in all_languages if lang not in {"unknown", "short_text"}]),
        "identityCandidateComments": len(identity_rows),
        "averageSentiment": round(sum(row["signed"] for row in scored) / len(scored), 3) if scored else 0,
    }

    return {
        "summary": summary,
        "players": player_list[:80],
        "matches": match_list,
        "communities": community_list,
        "languages": language_list,
        "identityFrames": identity_frames,
    }


def write_index(data):
    payload = json.dumps(data, ensure_ascii=False)
    payload_script = payload.replace("</", "<\\/")
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>World Cup Research Explorer</title>
  <style>
    :root {{
      --bg:#f6f7f9; --panel:#ffffff; --ink:#17202a; --muted:#667085; --line:#d8dee8;
      --green:#2f9e44; --gray:#8b95a5; --red:#d94848; --purple:#7c3aed; --blue:#2563eb; --orange:#e86f25;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--bg); font-family:Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }}
    .shell {{ display:grid; grid-template-columns:230px minmax(0,1fr); min-height:100vh; }}
    aside {{ position:sticky; top:0; height:100vh; padding:22px 16px; background:#111827; color:#f8fafc; }}
    .brand {{ display:grid; gap:4px; margin-bottom:22px; }}
    .brand strong {{ font-size:18px; line-height:1.05; }}
    .brand span {{ color:#aab4c4; font-size:12px; }}
    nav {{ display:grid; gap:6px; }}
    nav button, .link-button {{ width:100%; min-height:36px; border:0; border-radius:7px; padding:0 10px; color:#cbd5e1; background:transparent; text-align:left; cursor:pointer; font:inherit; font-size:13px; }}
    nav button.active {{ color:#fff; background:#263244; }}
    .overview-link {{ display:block; margin-top:18px; padding:10px; border:1px solid #38455a; border-radius:7px; color:#dce5f5; text-decoration:none; font-size:13px; }}
    main {{ padding:26px 30px 46px; }}
    header {{ display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:22px; }}
    h1 {{ margin:0; font-size:30px; line-height:1.05; letter-spacing:0; }}
    .subtitle {{ margin:7px 0 0; max-width:780px; color:var(--muted); font-size:14px; line-height:1.45; }}
    .filters {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; }}
    select, input, textarea {{ border:1px solid var(--line); border-radius:7px; min-height:36px; padding:0 10px; color:var(--ink); background:#fff; font:inherit; font-size:13px; }}
    textarea {{ min-height:82px; padding:10px; resize:vertical; width:100%; }}
    .view[hidden] {{ display:none; }}
    .kpis {{ display:grid; grid-template-columns:repeat(6,minmax(120px,1fr)); gap:12px; margin-bottom:18px; }}
    .kpi, .panel, .card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; box-shadow:0 10px 24px rgba(15,23,42,.06); }}
    .kpi {{ padding:14px 13px; }}
    .kpi span {{ display:block; color:var(--muted); font-size:12px; white-space:nowrap; }}
    .kpi strong {{ display:block; margin-top:5px; font-size:24px; line-height:1; }}
    .grid {{ display:grid; grid-template-columns:1.2fr .8fr; gap:14px; }}
    .three {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
    .panel {{ padding:16px; min-width:0; }}
    .panel h2, .card h3 {{ margin:0 0 12px; font-size:16px; line-height:1.2; }}
    .question {{ margin:-4px 0 14px; color:var(--muted); font-size:13px; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th, td {{ padding:9px 8px; border-bottom:1px solid #edf0f5; text-align:left; vertical-align:top; }}
    th {{ color:#526072; font-size:12px; font-weight:700; }}
    td.num, th.num {{ text-align:right; }}
    tr.clickable {{ cursor:pointer; }}
    tr.clickable:hover {{ background:#f2f5fa; }}
    .stack {{ display:flex; width:100%; height:14px; overflow:hidden; border-radius:3px; background:#eef1f5; }}
    .pos {{ background:var(--green); }} .neu {{ background:var(--gray); }} .neg {{ background:var(--red); }}
    .bar-row {{ display:grid; grid-template-columns:150px minmax(0,1fr) 58px; align-items:center; gap:10px; min-height:28px; font-size:13px; }}
    .bar {{ height:14px; width:var(--w); max-width:100%; border-radius:3px; background:var(--purple); }}
    .bar.blue {{ background:var(--blue); }} .bar.orange {{ background:var(--orange); }} .bar.red {{ background:var(--red); }}
    .chips {{ display:flex; flex-wrap:wrap; gap:6px; }}
    .chip {{ border-radius:999px; padding:4px 8px; background:#eef2ff; color:#3730a3; font-size:12px; }}
    .comments {{ display:grid; gap:8px; }}
    .comment {{ padding:10px; border:1px solid #e6ebf2; border-radius:7px; background:#fbfcfe; }}
    .comment p {{ margin:0 0 7px; font-size:13px; line-height:1.4; }}
    .meta {{ color:var(--muted); font-size:12px; }}
    .heatmap {{ display:grid; gap:4px; overflow:auto; }}
    .heat-row {{ display:grid; grid-template-columns:170px repeat(8,72px); gap:4px; align-items:stretch; }}
    .heat-cell {{ min-height:32px; display:grid; place-items:center; border-radius:5px; color:#111827; background:rgba(124,58,237,var(--a)); font-size:12px; }}
    .heat-label {{ display:flex; align-items:center; color:#475569; font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .bubble-wrap {{ min-height:330px; position:relative; border:1px solid #edf0f5; border-radius:8px; overflow:hidden; background:#fbfcff; }}
    .bubble {{ position:absolute; width:var(--s); height:var(--s); left:var(--x); top:var(--y); transform:translate(-50%,-50%); display:grid; place-items:center; border-radius:50%; background:rgba(124,58,237,.78); color:#fff; font-size:11px; text-align:center; padding:6px; cursor:pointer; }}
    .detail {{ display:grid; grid-template-columns:.75fr 1.25fr; gap:14px; }}
    .metric-list {{ display:grid; gap:8px; }}
    .metric {{ display:flex; justify-content:space-between; gap:10px; padding:8px 0; border-bottom:1px solid #edf0f5; font-size:13px; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }}
    button.primary {{ border:0; border-radius:7px; min-height:36px; padding:0 12px; color:#fff; background:#111827; cursor:pointer; font:inherit; font-size:13px; }}
    button.secondary {{ border:1px solid var(--line); border-radius:7px; min-height:36px; padding:0 12px; color:#111827; background:#fff; cursor:pointer; font:inherit; font-size:13px; }}
    .notebook-list {{ display:grid; gap:10px; margin-top:12px; }}
    .finding {{ padding:12px; border:1px solid #e6ebf2; border-radius:7px; background:#fbfcfe; }}
    .finding strong {{ display:block; margin-bottom:5px; }}
    @media (max-width:1100px) {{ .shell{{grid-template-columns:1fr}} aside{{position:static;height:auto}} nav{{grid-template-columns:repeat(3,minmax(0,1fr))}} .kpis{{grid-template-columns:repeat(3,minmax(0,1fr))}} .grid,.three,.detail{{grid-template-columns:1fr}} }}
    @media (max-width:720px) {{ main{{padding:18px 14px 34px}} header{{display:grid}} .filters{{justify-content:flex-start}} .kpis{{grid-template-columns:repeat(2,minmax(0,1fr))}} nav{{grid-template-columns:1fr 1fr}} .heat-row{{grid-template-columns:130px repeat(8,64px)}} }}
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <div class="brand"><strong>Research Explorer</strong><span>Player x Match x Community x Context</span></div>
      <nav id="nav"></nav>
      <a class="overview-link" href="../phase2_basic_results/index.html">Data Collection Overview</a>
    </aside>
    <main>
      <header>
        <div>
          <h1>World Cup Player Discourse</h1>
          <p class="subtitle">Explore how discussion varies by player, match, community, language, sentiment, and identity-related context. Rates are normalized per 100 player-mention records; no pre/post-match claims are made.</p>
        </div>
        <div class="filters">
          <select id="playerSelect"></select>
          <select id="matchSelect"></select>
          <select id="communitySelect"></select>
        </div>
      </header>
      <section id="overview" class="view"></section>
      <section id="players" class="view" hidden></section>
      <section id="matches" class="view" hidden></section>
      <section id="communities" class="view" hidden></section>
      <section id="identity" class="view" hidden></section>
      <section id="relationships" class="view" hidden></section>
      <section id="playerDetail" class="view" hidden></section>
      <section id="matchDetail" class="view" hidden></section>
      <section id="compare" class="view" hidden></section>
      <section id="notebook" class="view" hidden></section>
    </main>
  </div>
  <script id="data" type="application/json">{payload_script}</script>
  <script>
    try {{
    const DATA = JSON.parse(document.getElementById("data").textContent);
    const VIEWS = [
      ["overview", "Research Overview"], ["players", "Player Analysis"], ["matches", "Match Analysis"],
      ["communities", "Community Analysis"], ["identity", "Identity Discourse"], ["relationships", "Relationship Explorer"],
      ["playerDetail", "Player Detail"], ["matchDetail", "Match Detail"], ["compare", "Statistical Comparison"], ["notebook", "Notebook"]
    ];
    const state = {{ player: DATA.players[0]?.name || "", match: DATA.matches[0]?.name || "", community: DATA.communities[0]?.name || "" }};
    const fmt = new Intl.NumberFormat();
    const pct = v => `${{Number(v || 0).toFixed(1)}}%`;
    const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
    const byName = (arr, name) => arr.find(d => d.name === name) || arr[0] || {{}};
    function top(arr, n=8) {{ return (arr || []).slice(0, n); }}
    function nav() {{
      document.getElementById("nav").innerHTML = VIEWS.map(([id, label]) => `<button data-view="${{id}}" class="${{id==="overview" ? "active" : ""}}">${{label}}</button>`).join("");
      document.querySelectorAll("nav button").forEach(btn => btn.onclick = () => show(btn.dataset.view));
    }}
    function show(id) {{
      document.querySelectorAll(".view").forEach(v => v.hidden = v.id !== id);
      document.querySelectorAll("nav button").forEach(b => b.classList.toggle("active", b.dataset.view === id));
      render(id);
      history.replaceState(null, "", `#${{id}}`);
    }}
    function fillSelect(id, rows, value, label) {{
      const select = document.getElementById(id);
      select.innerHTML = rows.map(row => `<option value="${{esc(row.name)}}">${{esc(row.name)}}</option>`).join("");
      select.value = value;
      select.onchange = () => {{ state[label] = select.value; renderAllDetails(); }};
    }}
    function kpis() {{
      const s = DATA.summary;
      return `<div class="kpis">
        <div class="kpi"><span>Total Comments</span><strong>${{fmt.format(s.totalComments)}}</strong></div>
        <div class="kpi"><span>Total Matches</span><strong>${{fmt.format(s.totalMatches)}}</strong></div>
        <div class="kpi"><span>Players Mentioned</span><strong>${{fmt.format(s.playersMentioned)}}</strong></div>
        <div class="kpi"><span>Languages</span><strong>${{fmt.format(s.languages)}}</strong></div>
        <div class="kpi"><span>Identity Candidate Comments</span><strong>${{fmt.format(s.identityCandidateComments)}}</strong></div>
        <div class="kpi"><span>Average Sentiment</span><strong>${{s.averageSentiment}}</strong></div>
      </div>`;
    }}
    function sentimentStack(row) {{
      const total = Math.max(row.sentimentScored || 0, 1);
      return `<div class="stack" title="positive / neutral / negative">
        <span class="pos" style="width:${{(row.positive || 0) / total * 100}}%"></span>
        <span class="neu" style="width:${{(row.neutral || 0) / total * 100}}%"></span>
        <span class="neg" style="width:${{(row.negative || 0) / total * 100}}%"></span>
      </div>`;
    }}
    function rankingTable(rows, kind) {{
      return `<table><thead><tr><th>${{kind}}</th><th class="num">Mentions</th><th>Sentiment</th><th class="num">Identity / 100</th><th class="num">Immigration / 100</th><th class="num">Negative</th></tr></thead>
      <tbody>${{rows.map(row => `<tr class="clickable" data-kind="${{kind}}" data-name="${{esc(row.name)}}"><td>${{esc(row.name)}}</td><td class="num">${{fmt.format(row.mentions)}}</td><td>${{sentimentStack(row)}}</td><td class="num">${{pct(row.identityRate)}}</td><td class="num">${{pct(row.immigrationRate)}}</td><td class="num">${{pct(row.negativePct)}}</td></tr>`).join("")}}</tbody></table>`;
    }}
    function bars(rows, metric, cls="", suffix="%") {{
      const max = Math.max(...rows.map(r => Number(r[metric] || 0)), 1);
      return rows.map(r => `<div class="bar-row"><span>${{esc(r.name)}}</span><span class="bar ${{cls}}" style="--w:${{Number(r[metric] || 0) / max * 100}}%"></span><strong>${{Number(r[metric] || 0).toFixed(1)}}${{suffix}}</strong></div>`).join("");
    }}
    function comments(examples) {{
      return `<div class="comments">${{(examples || []).slice(0, 6).map(e => `<div class="comment"><p>${{esc(e.text)}}</p><div class="meta">${{esc(e.player || "")}} ${{esc(e.match)}} | ${{esc(e.community)}} | ${{esc(e.language || "")}} | ${{esc(e.sentiment || "")}} | ${{esc(e.keywords || "")}}</div></div>`).join("") || `<p class="question">No linked examples available for this selection.</p>`}}</div>`;
    }}
    function renderOverview() {{
      document.getElementById("overview").innerHTML = `${{kpis()}}<div class="grid">
        <div class="panel"><h2>Players with Highest Identity Context Rate</h2><p class="question">Which players attract identity-related discussion after normalizing by mention volume?</p>${{rankingTable(top(DATA.players, 12), "Player")}}</div>
        <div class="panel"><h2>Identity Frames</h2><p class="question">What kinds of identity discourse are most visible in candidate comments?</p>${{bars(DATA.identityFrames.slice(0, 8), "count", "", "")}}</div>
      </div>`;
      attachRows();
    }}
    function renderPlayers() {{
      document.getElementById("players").innerHTML = `<div class="panel"><h2>Player Analysis</h2><p class="question">Rates use player-mention records as the denominator, making high-volume and low-volume players more comparable.</p>${{rankingTable(DATA.players, "Player")}}</div>`;
      attachRows();
    }}
    function renderMatches() {{
      document.getElementById("matches").innerHTML = `<div class="grid"><div class="panel"><h2>Matches Ranked by Identity Discourse Rate</h2>${{rankingTable(DATA.matches, "Match")}}</div><div class="panel"><h2>Highest Immigration Context Rate</h2>${{bars(top(DATA.matches, 10), "immigrationRate", "orange")}}</div></div>`;
      attachRows();
    }}
    function renderCommunities() {{
      document.getElementById("communities").innerHTML = `<div class="grid"><div class="panel"><h2>Community Comparison</h2>${{rankingTable(DATA.communities, "Community")}}</div><div class="panel"><h2>Community Concentration</h2><p class="question">Higher values mean discourse is concentrated in fewer players.</p>${{bars(top(DATA.communities, 10), "communityConcentration", "orange", "")}}</div></div>`;
      attachRows();
    }}
    function renderIdentity() {{
      document.getElementById("identity").innerHTML = `<div class="three">${{DATA.identityFrames.map(frame => `<div class="card panel"><h3>${{esc(frame.name)}}</h3><div class="metric"><span>Candidate comments</span><strong>${{fmt.format(frame.count)}}</strong></div>${{comments(frame.examples)}}</div>`).join("")}}</div>`;
    }}
    function heatmap(rows, cols, accessor) {{
      const values = rows.flatMap(r => cols.map(c => accessor(r, c)));
      const max = Math.max(...values, 1);
      return `<div class="heatmap"><div class="heat-row"><span></span>${{cols.map(c => `<span class="heat-label">${{esc(c)}}</span>`).join("")}}</div>${{rows.map(r => `<div class="heat-row"><span class="heat-label">${{esc(r.name)}}</span>${{cols.map(c => {{ const v = accessor(r, c); return `<span class="heat-cell" style="--a:${{Math.max(.08, v / max)}}">${{v ? Number(v).toFixed(1) : ""}}</span>`; }}).join("")}}</div>`).join("")}}</div>`;
    }}
    function renderRelationships() {{
      const players = top(DATA.players, 12);
      const communities = top(DATA.communities, 8).map(d => d.name);
      const frames = top(DATA.identityFrames, 8).map(d => d.name);
      document.getElementById("relationships").innerHTML = `<div class="grid">
        <div class="panel"><h2>Player x Community</h2><p class="question">Cells show mention counts, highlighting where each player is discussed.</p>${{heatmap(players, communities, (p,c) => (p.communities.find(x => x.name === c) || {{value:0}}).value)}}</div>
        <div class="panel"><h2>Player x Identity Frame</h2><p class="question">Cells show frame counts in linked identity contexts.</p>${{heatmap(players, frames, (p,c) => (p.frames.find(x => x.name === c) || {{value:0}}).value)}}</div>
        <div class="panel"><h2>Language x Sentiment</h2>${{rankingTable(DATA.languages, "Language")}}</div>
        <div class="panel"><h2>Bubble Plot: Identity Rate x Negative Sentiment</h2>${{bubble(players)}}</div>
      </div>`;
      attachRows();
    }}
    function bubble(rows) {{
      return `<div class="bubble-wrap">${{rows.map(r => {{
        const x = 10 + Math.min(80, r.identityRate * 3);
        const y = 90 - Math.min(75, r.negativePct);
        const s = 34 + Math.min(54, Math.sqrt(r.mentions));
        return `<div class="bubble" data-player="${{esc(r.name)}}" style="--x:${{x}}%;--y:${{y}}%;--s:${{s}}px">${{esc(r.name.split(" ").slice(-1)[0])}}</div>`;
      }}).join("")}}</div>`;
    }}
    function detailMetrics(row) {{
      return `<div class="metric-list">
        <div class="metric"><span>Total mentions</span><strong>${{fmt.format(row.mentions || 0)}}</strong></div>
        <div class="metric"><span>Positive / Neutral / Negative</span><strong>${{pct(row.positivePct)}} / ${{pct(row.neutralPct)}} / ${{pct(row.negativePct)}}</strong></div>
        <div class="metric"><span>Identity context</span><strong>${{pct(row.identityRate)}}</strong></div>
        <div class="metric"><span>Immigration context</span><strong>${{pct(row.immigrationRate)}}</strong></div>
        <div class="metric"><span>Average sentiment</span><strong>${{row.avgSentiment || 0}}</strong></div>
        <div class="metric"><span>Language diversity</span><strong>${{row.languageDiversity || 0}}</strong></div>
      </div>`;
    }}
    function listChips(rows) {{ return `<div class="chips">${{top(rows, 10).map(x => `<span class="chip">${{esc(x.name)}}: ${{fmt.format(x.value)}}</span>`).join("") || `<span class="chip">No data</span>`}}</div>`; }}
    function renderPlayerDetail() {{
      const row = byName(DATA.players, state.player);
      document.getElementById("playerDetail").innerHTML = `<div class="detail"><div class="panel"><h2>${{esc(row.name)}}</h2>${{detailMetrics(row)}}<div class="actions"><button class="primary" onclick="saveFinding('Player detail', '${{esc(row.name)}} has an identity context rate of ${{pct(row.identityRate)}}.')">Save Finding</button></div></div><div class="panel"><h2>Representative Comments</h2>${{comments(row.examples)}}</div></div>
      <div class="three" style="margin-top:14px"><div class="panel"><h2>Communities</h2>${{listChips(row.communities)}}</div><div class="panel"><h2>Languages</h2>${{listChips(row.languages)}}</div><div class="panel"><h2>Keyword Contexts</h2>${{listChips(row.terms)}}</div></div>`;
    }}
    function renderMatchDetail() {{
      const row = byName(DATA.matches, state.match);
      document.getElementById("matchDetail").innerHTML = `<div class="detail"><div class="panel"><h2>${{esc(row.name)}}</h2>${{detailMetrics(row)}}<div class="actions"><button class="primary" onclick="saveFinding('Match detail', '${{esc(row.name)}} has an identity context rate of ${{pct(row.identityRate)}}.')">Save Finding</button></div></div><div class="panel"><h2>Representative Comments</h2>${{comments(row.examples)}}</div></div>
      <div class="three" style="margin-top:14px"><div class="panel"><h2>Players Discussed</h2>${{listChips(row.players)}}</div><div class="panel"><h2>Communities</h2>${{listChips(row.communities)}}</div><div class="panel"><h2>Language Composition</h2>${{listChips(row.languages)}}</div></div>`;
    }}
    function renderCompare() {{
      const opts = DATA.players.map(p => `<option>${{esc(p.name)}}</option>`).join("");
      document.getElementById("compare").innerHTML = `<div class="panel"><h2>Statistical Comparison Panel</h2><p class="question">Compare absolute counts and normalized percentages. Effect sizes use simple percentage-point differences for currently available metrics.</p><div class="filters" style="justify-content:flex-start"><select id="cmpA">${{opts}}</select><select id="cmpB">${{opts}}</select></div><div id="cmpOut" style="margin-top:14px"></div></div>`;
      document.getElementById("cmpA").value = DATA.players[0]?.name || "";
      document.getElementById("cmpB").value = DATA.players[1]?.name || "";
      document.getElementById("cmpA").onchange = renderCmp;
      document.getElementById("cmpB").onchange = renderCmp;
      renderCmp();
    }}
    function renderCmp() {{
      const a = byName(DATA.players, document.getElementById("cmpA").value);
      const b = byName(DATA.players, document.getElementById("cmpB").value);
      const rows = [["Mentions", a.mentions, b.mentions, a.mentions - b.mentions], ["Identity rate", a.identityRate, b.identityRate, a.identityRate - b.identityRate], ["Negative rate", a.negativePct, b.negativePct, a.negativePct - b.negativePct], ["Immigration rate", a.immigrationRate, b.immigrationRate, a.immigrationRate - b.immigrationRate]];
      document.getElementById("cmpOut").innerHTML = `<table><thead><tr><th>Metric</th><th class="num">${{esc(a.name)}}</th><th class="num">${{esc(b.name)}}</th><th class="num">Difference</th></tr></thead><tbody>${{rows.map(r => `<tr><td>${{r[0]}}</td><td class="num">${{Number(r[1]).toFixed(2)}}</td><td class="num">${{Number(r[2]).toFixed(2)}}</td><td class="num">${{Number(r[3]).toFixed(2)}}</td></tr>`).join("")}}</tbody></table>`;
    }}
    function renderNotebook() {{
      document.getElementById("notebook").innerHTML = `<div class="panel"><h2>Research Notebook Mode</h2><p class="question">Bookmarks are stored in this browser via localStorage and include the current filters plus your note.</p><textarea id="noteText" placeholder="Write a finding, hypothesis, or Results-section note..."></textarea><div class="actions"><button class="primary" onclick="saveFinding('Notebook note', document.getElementById('noteText').value)">Save Finding</button><button class="secondary" onclick="localStorage.removeItem('worldcupFindings'); renderNotebook()">Clear</button></div><div class="notebook-list">${{notebookItems()}}</div></div>`;
    }}
    function notebookItems() {{
      const items = JSON.parse(localStorage.getItem("worldcupFindings") || "[]");
      return items.map(item => `<div class="finding"><strong>${{esc(item.title)}}</strong><div>${{esc(item.note)}}</div><div class="meta">Player: ${{esc(item.filters.player)}} | Match: ${{esc(item.filters.match)}} | Community: ${{esc(item.filters.community)}} | ${{esc(item.savedAt)}}</div></div>`).join("") || `<p class="question">No saved findings yet.</p>`;
    }}
    window.saveFinding = function(title, note) {{
      if (!String(note || "").trim()) return;
      const items = JSON.parse(localStorage.getItem("worldcupFindings") || "[]");
      items.unshift({{ title, note, filters: {{...state}}, savedAt: new Date().toLocaleString() }});
      localStorage.setItem("worldcupFindings", JSON.stringify(items.slice(0, 80)));
      renderNotebook();
    }}
    function attachRows() {{
      document.querySelectorAll("tr.clickable").forEach(tr => tr.onclick = () => {{
        const name = tr.dataset.name;
        if (tr.dataset.kind === "Player") {{ state.player = name; document.getElementById("playerSelect").value = name; show("playerDetail"); }}
        if (tr.dataset.kind === "Match") {{ state.match = name; document.getElementById("matchSelect").value = name; show("matchDetail"); }}
      }});
      document.querySelectorAll(".bubble").forEach(b => b.onclick = () => {{ state.player = b.dataset.player; document.getElementById("playerSelect").value = state.player; show("playerDetail"); }});
    }}
    function render(id) {{
      if (id === "overview") renderOverview();
      if (id === "players") renderPlayers();
      if (id === "matches") renderMatches();
      if (id === "communities") renderCommunities();
      if (id === "identity") renderIdentity();
      if (id === "relationships") renderRelationships();
      if (id === "playerDetail") renderPlayerDetail();
      if (id === "matchDetail") renderMatchDetail();
      if (id === "compare") renderCompare();
      if (id === "notebook") renderNotebook();
    }}
    function renderAllDetails() {{
      const active = [...document.querySelectorAll(".view")].find(v => !v.hidden)?.id || "overview";
      render(active);
    }}
    nav();
    fillSelect("playerSelect", DATA.players, state.player, "player");
    fillSelect("matchSelect", DATA.matches, state.match, "match");
    fillSelect("communitySelect", DATA.communities, state.community, "community");
    show(location.hash?.slice(1) || "overview");
    }} catch (error) {{
      window.__researchExplorerError = String(error && (error.stack || error.message || error));
      const target = document.getElementById("overview");
      if (target) {{
        const safeError = String(window.__researchExplorerError).replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
        target.innerHTML = `<div class="panel"><h2>Research Explorer failed to initialize</h2><p class="question">${{safeError}}</p></div>`;
      }}
    }}
  </script>
</body>
</html>
"""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "index.html").write_text(page, encoding="utf-8")


def main():
    data = load_research_data()
    write_index(data)
    print(f"Wrote research explorer to {REPORT_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
