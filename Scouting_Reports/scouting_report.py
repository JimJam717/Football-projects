import os
import json
import pandas as pd
from scipy.stats import percentileofscore


import numpy as np

# Step 1: Fix Unknown teams for players who appear as 'Unknown' in match data
MANUAL_TEAM_MAP = {
    "A Nortje":          "Kolkata Knight Riders",
    "A Zampa":           "Sunrisers Hyderabad",
    "Akash Singh":       "Lucknow Super Giants",
    "Ashwani Kumar":     "Mumbai Indians",
    "E Malinga":         "Sunrisers Hyderabad",
    "I Sharma":          "Gujarat Titans",
    "JD Unadkat":        "Sunrisers Hyderabad",
    "K Khejroliya":      "Gujarat Titans",
    "M Pathirana":       "Chennai Super Kings",
    "M Prasidh Krishna": "Gujarat Titans",
    "Mukesh Choudhary":  "Chennai Super Kings",
    "Mukesh Kumar":      "Delhi Capitals",
    "N Thushara":        "Royal Challengers Bengaluru",
    "NT Ellis":          "Chennai Super Kings",
    "Rasikh Salam":      "Royal Challengers Bengaluru",
    "Suyash Sharma":     "Royal Challengers Bengaluru",
    "T Natarajan":       "Delhi Capitals",
    "YS Chahal":         "Rajasthan Royals",
    "Yash Thakur":       "Punjab Kings",
    "Yudhvir Singh":     "Rajasthan Royals",
    "Zeeshan Ansari":    "Sunrisers Hyderabad",
}

def load_and_process_data(data_dir):
    all_matches_data = []
    output_filename = 'all_players_data.json'
    for filename in os.listdir(data_dir):
        if filename.endswith(".json") and filename != output_filename:
            filepath = os.path.join(data_dir, filename)
            match_id = filename.split('.')[0]
            with open(filepath, 'r') as f:
                try:
                    match_data = json.load(f)
                except json.JSONDecodeError:
                    continue

                if not isinstance(match_data, dict):
                    continue

                # Filter for 2025 matches
                match_dates = match_data.get('info', {}).get('dates', [])
                if not any(date.startswith('2025') for date in match_dates):
                    continue
                print(f"Processing: {filename}", end='\r')
                match_data['match_id'] = match_id
                all_matches_data.append(match_data)
    
    player_batting_stats = {}
    player_bowling_stats = {}

    for match in all_matches_data:
        for inning in match['innings']:
            for over_data in inning['overs']:
                try:
                    current_batting_team = inning['team'] # Get the team for the current inning
                except KeyError:
                    continue
                for delivery in over_data['deliveries']:
                    # --- Batting Stats Collection ---
                    batter = delivery['batter']
                    if batter not in player_batting_stats:
                        player_batting_stats[batter] = {
                            'runs': 0,
                            'balls_faced': 0,
                            'wickets': 0, #outs
                            'fours': 0,
                            'sixes': 0,
                            'dot_balls': 0,
                            'matches_played': set(),
                            'team': None # Initialize team to None
                        }
                    
                    player_batting_stats[batter]['team'] = current_batting_team # Assign the team
                    player_batting_stats[batter]['runs'] += delivery['runs']['batter']
                    player_batting_stats[batter]['balls_faced'] += 1
                    player_batting_stats[batter]['matches_played'].add(match.get('match_id', 'Unknown'))
                    
                    if 'wickets' in delivery:
                        for wicket in delivery['wickets']:
                            if (wicket.get('player_out') == batter and
                                    wicket.get('kind') not in ['run out', 'retired hurt', 'obstructing the field']):
                                player_batting_stats[batter]['wickets'] += 1
                    
                    if delivery['runs']['batter'] == 4:
                        player_batting_stats[batter]['fours'] += 1
                    elif delivery['runs']['batter'] == 6:
                        player_batting_stats[batter]['sixes'] += 1
                    
                    if delivery['runs']['total'] == 0: # Check total runs for dot ball
                        extras_data = delivery.get('extras', {})
                        is_wide = extras_data.get('wides', 0) > 0
                        if not is_wide: # A wide is not a dot ball
                            player_batting_stats[batter]['dot_balls'] += 1

# --- (NEW) Bowling Stats Collection per match ---
                    # Commenting out old bowling collection logic as requested:
                    # bowler = delivery['bowler']
                    # if bowler not in player_bowling_stats:
                    #     player_bowling_stats[bowler] = {
                    #         'runs_conceded': 0,
                    #         'balls_bowled': 0,
                    #         'wides': 0,
                    #         'no_balls': 0,
                    #         'wickets_taken': 0,
                    #         'dot_balls_bowled': 0,
                    #         'fours_conceded': 0,
                    #         'sixes_conceded': 0,
                    #         'matches_bowled': set(),
                    #         'team': None
                    #     }
                    
                    # bowling_team = next((team_name for team_name in match['info']['teams'] if team_name != current_batting_team), None)
                    # if bowling_team:
                    #     player_bowling_stats[bowler]['team'] = bowling_team
                    
                    # total_runs_delivery = delivery['runs']['total']
                    # extras_data = delivery.get('extras', {})
                    # is_wide_delivery = extras_data.get('wides', 0) > 0
                    # is_no_ball_delivery = extras_data.get('noballs', 0) > 0
                    
                    # leg_byes = extras_data.get('legbyes', 0)
                    # byes = extras_data.get('byes', 0)
                    # player_bowling_stats[bowler]['runs_conceded'] += total_runs_delivery - leg_byes - byes
                    
                    # if not is_wide_delivery and not is_no_ball_delivery:
                    #     player_bowling_stats[bowler]['balls_bowled'] += 1
                    
                    # if is_wide_delivery:
                    #     player_bowling_stats[bowler]['wides'] += 1
                    # if is_no_ball_delivery:
                    #     player_bowling_stats[bowler]['no_balls'] += 1
                    
                    # if 'wickets' in delivery:
                    #     for wicket in delivery['wickets']:
                    #         if wicket.get('kind') not in ['run out', 'retired hurt', 'obstructing the field']:
                    #             player_bowling_stats[bowler]['wickets_taken'] += 1
                    
                    # if total_runs_delivery == 0 and not is_wide_delivery:
                    #     player_bowling_stats[bowler]['dot_balls_bowled'] += 1
                    
                    # if delivery['runs']['batter'] == 4:
                    #     player_bowling_stats[bowler]['fours_conceded'] += 1
                    # elif delivery['runs']['batter'] == 6:
                    #     player_bowling_stats[bowler]['sixes_conceded'] += 1
                        
                    # player_bowling_stats[bowler]['matches_bowled'].add(match_id)
        # Wire Step 4: After existing batting loop, still inside the per-match loop:
        match_id_current = match.get('match_id', 'Unknown')
        match_bowling = collect_bowling_stats(match['innings'], match_id_current)
        for bowler, stats in match_bowling.items():
            if bowler not in player_bowling_stats:
                player_bowling_stats[bowler] = {
                    'runs_conceded': 0, 'balls_bowled': 0, 'wickets': 0,
                    'wides': 0, 'no_balls': 0, 'dot_balls': 0,
                    'fours_conceded': 0, 'sixes_conceded': 0, 'matches': set(),
                    'team': None
                }
            pb = player_bowling_stats[bowler]
            pb['runs_conceded']   += stats['runs_conceded']
            pb['balls_bowled']    += stats['balls_bowled']
            pb['wickets']         += stats['wickets']
            pb['wides']           += stats['wides']
            pb['no_balls']        += stats['no_balls']
            pb['dot_balls']       += stats['dot_balls']
            pb['fours_conceded']  += stats['fours_conceded']
            pb['sixes_conceded']  += stats['sixes_conceded']
            pb['matches'].update([match_id])

        # Step 1 Fix: Assign teams to players who haven't had them set yet
        if 'players' in match.get('info', {}):
            for team_name, player_list in match['info']['players'].items():
                for player in player_list:
                    if player in player_batting_stats and not player_batting_stats[player].get('team'):
                        player_batting_stats[player]['team'] = team_name
                    if player in player_bowling_stats and not player_bowling_stats[player].get('team'):
                        player_bowling_stats[player]['team'] = team_name
    
    # Final override pass from MANUAL_TEAM_MAP
    for player in player_batting_stats:
        if player in MANUAL_TEAM_MAP:
            player_batting_stats[player]['team'] = MANUAL_TEAM_MAP[player]
        elif not player_batting_stats[player].get('team'):
            player_batting_stats[player]['team'] = "Unknown"

    for player in player_bowling_stats:
        if player in MANUAL_TEAM_MAP:
            player_bowling_stats[player]['team'] = MANUAL_TEAM_MAP[player]
        elif not player_bowling_stats[player].get('team'):
            player_bowling_stats[player]['team'] = "Unknown"

    batting_df = pd.DataFrame.from_dict(player_batting_stats, orient='index')
    if not batting_df.empty:
        batting_df['games_played'] = batting_df['matches_played'].apply(len)
        batting_df = batting_df.drop(columns=['matches_played'])
        batting_df.index.name = 'player_name'
        batting_df = batting_df.reset_index()
        
        # Calculate batting metrics
        batting_df['batting_average'] = batting_df.apply(
            lambda row: row['runs'] / row['wickets'] if row['wickets'] > 0 else row['runs'],
            axis=1
        )
        # Ensure balls_faced is not zero to avoid division by zero
        batting_df['strike_rate'] = batting_df.apply(
            lambda row: (row['runs'] / row['balls_faced']) * 100 if row['balls_faced'] > 0 else 0,
            axis=1
        )
        batting_df['boundary_percentage'] = batting_df.apply(
            lambda row: ((row['fours'] + row['sixes']) / row['balls_faced']) * 100 if row['balls_faced'] > 0 else 0,
            axis=1
        )
        batting_df['hard_hit_rate'] = batting_df.apply(
            lambda row: (row['sixes'] / row['balls_faced']) * 100 if row['balls_faced'] > 0 else 0,
            axis=1
        )
        batting_df['dot_ball_percentage'] = batting_df.apply(
            lambda row: (row['dot_balls'] / row['balls_faced']) * 100 if row['balls_faced'] > 0 else 0,
            axis=1
        )
    else:
        batting_df = pd.DataFrame(columns=['player_name', 'runs', 'balls_faced', 'wickets', 'fours', 'sixes', 'dot_balls', 'team', 'games_played', 'batting_average', 'strike_rate', 'boundary_percentage', 'hard_hit_rate', 'dot_ball_percentage'])

    # Final pass after match loop - Step 4: Convert matches set to count
    for bowler in player_bowling_stats:
        player_bowling_stats[bowler]['matches'] = len(player_bowling_stats[bowler]['matches'])

    # Convert to DataFrame using new Step 2 function
    new_bowling_df = calculate_bowling_metrics(player_bowling_stats)
    return batting_df, new_bowling_df

def generate_report(player_name, all_batting_metrics_df, all_bowling_metrics_df=None, min_batting_balls_faced=50, min_bowling_balls_bowled=12):
    # --- Batting Report ---
    batting_report = None
    player_batting_data = all_batting_metrics_df[all_batting_metrics_df['player_name'] == player_name]
    
    if not player_batting_data.empty:
        player_batting_data = player_batting_data.iloc[0]
        batting_metrics_list = ['batting_average', 'strike_rate', 'boundary_percentage', 'hard_hit_rate', 'dot_ball_percentage']
        batting_percentiles = []

        for metric in batting_metrics_list:
            eligible_batters = all_batting_metrics_df[all_batting_metrics_df['balls_faced'] >= min_batting_balls_faced]
            if not eligible_batters.empty and metric in eligible_batters.columns:
                metric_values = eligible_batters[metric].dropna()
                if not metric_values.empty:
                    player_metric_value = player_batting_data[metric]
                    if pd.isna(player_metric_value):
                        batting_percentiles.append(np.nan)
                    else:
                        percentile = percentileofscore(metric_values, player_metric_value, kind='weak')
                        # Invert percentile for Dot Ball % (Lower is better for batters)
                        if metric == 'dot_ball_percentage':
                            percentile = 100 - percentile
                        batting_percentiles.append(percentile)
                else:
                    batting_percentiles.append(np.nan)
            else:
                batting_percentiles.append(np.nan)
        
        # Assemble batting report
        batting_report = {
            "matches": player_batting_data['games_played'],
            "runs": player_batting_data['runs'],
            "balls_faced": player_batting_data['balls_faced'],
            "wickets": player_batting_data['wickets'],
            "metrics": []
        }
        
        # Bug 5 - Map internal metric names to friendly names
        metric_name_mapping = {
            'batting_average': 'Batting Average',
            'strike_rate': 'Strike Rate',
            'boundary_percentage': 'Boundary Percentage',
            'hard_hit_rate': 'Six-Hitting Rate',
            'dot_ball_percentage': 'Dot Ball %'
        }
        
        for i, metric in enumerate(batting_metrics_list):
            friendly_name = metric_name_mapping.get(metric, metric.replace('_', ' ').title())
            batting_report["metrics"].append({
                "name": friendly_name,
                "raw_value": player_batting_data[metric],
                "percentile": batting_percentiles[i] if not pd.isna(batting_percentiles[i]) else None
            })

    # --- Final Report Assembly ---
    if player_batting_data.empty:
        return None # Only concerned with batters per Bug 5 structure
    
    final_report = {
        "player_name": player_name,
        "team": player_batting_data['team'] if not player_batting_data.empty else "Unknown",
        "comparison_group": f"IPL 2025 Batters (Min {min_batting_balls_faced} balls faced)",
        "batting": batting_report
    }

    return final_report

def collect_bowling_stats(innings_list, match_id):
    """
    Collect raw bowling stats from a match's innings list.
    Returns a dict keyed by bowler name.
    """
    stats = {}

    for inning in innings_list:
        for over in inning['overs']:
            for delivery in over['deliveries']:
                bowler = delivery['bowler']
                if bowler not in stats:
                    stats[bowler] = {
                        'runs_conceded': 0,
                        'balls_bowled': 0,
                        'wickets': 0,
                        'wides': 0,
                        'no_balls': 0,
                        'dot_balls': 0,
                        'fours_conceded': 0,
                        'sixes_conceded': 0,
                        'matches': set()
                    }

                s = stats[bowler]
                s['matches'].add(match_id)
                extras = delivery.get('extras', {})
                is_wide = 'wides' in extras
                is_noball = 'noballs' in extras

                # Runs conceded = total minus byes and legbyes
                runs_total = delivery['runs']['total']
                byes = extras.get('byes', 0)
                legbyes = extras.get('legbyes', 0)
                s['runs_conceded'] += runs_total - byes - legbyes

                # Legal deliveries only
                if not is_wide and not is_noball:
                    s['balls_bowled'] += 1
                    if delivery['runs']['total'] == 0:
                        s['dot_balls'] += 1

                if is_wide:
                    s['wides'] += 1
                if is_noball:
                    s['no_balls'] += 1

                batter_runs = delivery['runs']['batter']
                if batter_runs == 4:
                    s['fours_conceded'] += 1
                elif batter_runs == 6:
                    s['sixes_conceded'] += 1

                # Wickets attributed to bowler
                if 'wickets' in delivery:
                    for wicket in delivery['wickets']:
                        if wicket.get('kind') not in [
                            'run out', 'retired hurt', 'obstructing the field'
                        ]:
                            s['wickets'] += 1

    # Convert matches set to count
    for bowler in stats:
        stats[bowler]['matches'] = len(stats[bowler]['matches'])

    return stats

def calculate_bowling_metrics(stats):
    """
    Convert raw bowling stats dict into a DataFrame of derived metrics.
    Only includes bowlers with >= 12 balls bowled.
    """
    rows = []
    for bowler, s in stats.items():
        if s['balls_bowled'] < 12:
            continue
        balls = s['balls_bowled']
        wkts = s['wickets']
        runs = s['runs_conceded']
        economy = (runs / balls) * 6 if balls > 0 else None
        bowl_avg = (runs / wkts) if wkts > 0 else 9999
        bowl_sr = (balls / wkts) if wkts > 0 else 9999
        dot_pct = (s['dot_balls'] / balls) * 100 if balls > 0 else None
        boundary_pct = ((s['fours_conceded'] + s['sixes_conceded']) / balls) * 100 if balls > 0 else None
        extra_rate = ((s['wides'] + s['no_balls']) / (balls + s['wides'] + s['no_balls'])) * 100

        rows.append({
            'bowler': bowler,
            'team': s.get('team', "Unknown"),
            'matches': s['matches'],
            'balls_bowled': balls,
            'wickets': wkts,
            'runs_conceded': runs,
            'economy': economy,
            'bowling_average': bowl_avg,
            'bowling_sr': bowl_sr,
            'dot_ball_pct': dot_pct,
            'boundary_pct': boundary_pct,
            'extra_rate': extra_rate
        })

    return pd.DataFrame(rows)

def generate_bowling_report(player_name, bowling_df):
    """
    Generate percentile-ranked bowling metrics for a single player.
    Returns None if player not found or below threshold.
    """
    if bowling_df.empty or player_name not in bowling_df['bowler'].values:
        return None

    row = bowling_df[bowling_df['bowler'] == player_name].iloc[0]

    # Metrics where LOWER is better — invert percentile
    lower_is_better = ['economy', 'bowling_average', 'bowling_sr', 'boundary_pct', 'extra_rate']
    # Metrics where HIGHER is better — normal percentile
    higher_is_better = ['dot_ball_pct']

    metric_display = {
        'economy':          'Economy Rate',
        'bowling_average':  'Bowling Average',
        'bowling_sr':       'Bowling Strike Rate',
        'dot_ball_pct':     'Dot Ball %',
        'boundary_pct':     'Boundary %',
        'extra_rate':       'Extra Rate'
    }

    metrics = []
    for col, display_name in metric_display.items():
        raw = row[col]
        values = bowling_df[col].dropna().values

        # Skip sentinel values from percentile pool
        values_clean = values[values != 9999]

        if raw == 9999 or len(values_clean) == 0:
            percentile = None
        elif col in lower_is_better:
            percentile = round(100 - percentileofscore(values_clean, raw, kind='weak'), 4)
        else:
            percentile = round(float(percentileofscore(values_clean, raw, kind='weak')), 4)

        metrics.append({
            'name': display_name,
            'raw_value': None if raw == 9999 else round(float(raw), 4),
            'percentile': percentile
        })

    return {
        'team': row['team'],
        'matches': int(row['matches']),
        'balls_bowled': int(row['balls_bowled']),
        'wickets': int(row['wickets']),
        'runs_conceded': int(row['runs_conceded']),
        'metrics': metrics
    }