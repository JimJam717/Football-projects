import json

schedule = [
  {
    "match_id": "can_vs_bih_gd1",
    "nation": "canada",
    "opponent": "Bosnia and Herzegovina",
    "kickoff_utc": "2026-06-12T18:00:00Z",
    "subreddits": ["soccer", "worldcup", "CanadaSoccer"]
  },
  {
    "match_id": "usa_vs_par_gd1",
    "nation": "usa",
    "opponent": "Paraguay",
    "kickoff_utc": "2026-06-13T18:00:00Z",
    "subreddits": ["soccer", "worldcup", "ussoccer"]
  },
  {
    "match_id": "ned_vs_jpn_gd1",
    "nation": "netherlands",
    "opponent": "Japan",
    "kickoff_utc": "2026-06-14T18:00:00Z",
    "subreddits": ["soccer", "worldcup", "Eredivisie"]
  },
  {
    "match_id": "ger_vs_mex_gd1",
    "nation": "germany",
    "opponent": "Mexico",
    "kickoff_utc": "2026-06-15T18:00:00Z",
    "subreddits": ["soccer", "worldcup", "bundesliga"]
  },
  {
    "match_id": "fra_vs_sen_gd1",
    "nation": "france",
    "opponent": "Senegal",
    "kickoff_utc": "2026-06-16T18:00:00Z",
    "subreddits": ["soccer", "worldcup", "Ligue1"]
  },
  {
    "match_id": "eng_vs_cro_gd1",
    "nation": "england",
    "opponent": "Croatia",
    "kickoff_utc": "2026-06-17T18:00:00Z",
    "subreddits": ["soccer", "worldcup", "ThreeLions"]
  },
  {
    "match_id": "sui_vs_tbd_gd1",
    "nation": "switzerland",
    "opponent": "TBD",
    "kickoff_utc": "2026-06-15T21:00:00Z",
    "subreddits": ["soccer", "worldcup", "SwissFootball"]
  },
  {
    "match_id": "sco_vs_tbd_gd1",
    "nation": "scotland",
    "opponent": "TBD",
    "kickoff_utc": "2026-06-16T21:00:00Z",
    "subreddits": ["soccer", "worldcup", "ScottishFootball"]
  },
  {
    "match_id": "aus_vs_tbd_gd1",
    "nation": "australia",
    "opponent": "TBD",
    "kickoff_utc": "2026-06-17T21:00:00Z",
    "subreddits": ["soccer", "worldcup", "Aleague"]
  }
]

with open('config/schedule.json', 'w', encoding='utf-8') as f:
    json.dump(schedule, f, indent=2)

print("Generated schedule.json successfully!")
