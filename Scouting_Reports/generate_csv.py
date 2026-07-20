import json
import csv

def generate_player_images_csv(input_json='all_players_data.json', output_csv='player_images.csv'):
    # 1. Load the data
    with open(input_json, 'r') as f:
        data = json.load(f)

    # 2. Extract player info and unique teams
    players = []
    teams = set()
    
    for player in data:
        name = player.get('player_name', 'Unknown')
        team = player.get('team', 'Unknown')
        players.append({'player_name': name, 'team': team, 'image_url': ''})
        teams.add(team)
    
    # Sort teams alphabetically
    sorted_teams = sorted(list(teams))
    
    # 3. Create logo rows
    logo_rows = []
    for team in sorted_teams:
        if team != 'Unknown':
            logo_rows.append({'player_name': f"{team} Logo", 'team': team, 'image_url': ''})
            
    # 4. Sort player rows (by team, then player name)
    players.sort(key=lambda x: (x['team'], x['player_name']))
    
    # 5. Combine: Logo rows first, then player rows
    final_rows = logo_rows + players
    
    # 6. Write to CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['player_name', 'team', 'image_url'])
        writer.writeheader()
        writer.writerows(final_rows)
    
    print(f"Generated {output_csv} with {len(final_rows)} rows ({len(logo_rows)} logos, {len(players)} players).")

if __name__ == '__main__':
    generate_player_images_csv()
