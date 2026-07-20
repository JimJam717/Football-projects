import json
with open('all_players_data.json') as f:
    data = json.load(f)

# Check a known bowler — Rashid Khan
found = False
for p in data:
    if 'Rashid' in p['player_name']:
        found = True
        print(f"Name: {p['player_name']}")
        print(f"Bowling data: {p['bowling'] is not None}")
        if p['bowling']:
            print(f"  Wickets: {p['bowling']['wickets']}")
            print(f"  Balls bowled: {p['bowling']['balls_bowled']}")
            print(f"  Runs conceded: {p['bowling']['runs_conceded']}")
            for m in p['bowling']['metrics']:
                print(f"  {m['name']}: {m['raw_value']} (p{m['percentile']})")
        break

if not found:
    print("Rashid Khan not found in the data.")

# Count how many players have bowling data
has_bowling = sum(1 for p in data if p['bowling'] is not None)
print(f"\nPlayers with bowling data: {has_bowling}/{len(data)}")
