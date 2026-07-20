import json
try:
    with open('all_players_data.json') as f:
        data = json.load(f)
    print(f"Total players: {len(data)}")
    found = False
    for p in data:
        if 'Gill' in p['player_name']:
            found = True
            print(f"Name: {p['player_name']}")
            print(f"Team: {p['team']}")
            print(f"Runs: {p['batting']['runs']}")
            print(f"Balls faced: {p['batting']['balls_faced']}")
            print(f"Dismissals: {p['batting']['wickets']}")
            for m in p['batting']['metrics']:
                print(f"  {m['name']}: {m['raw_value']} (p{m['percentile']})")
            break
    if not found:
        print("Shubman Gill not found in the data.")
except Exception as e:
    print(f"Error during validation: {e}")
