import json
import os
import pandas as pd
from scouting_report import load_and_process_data, generate_report

import numpy as np

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return round(float(obj), 4)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super().default(obj)

def generate_all_reports_json(data_dir='c:\\Users\\Pratham\\Desktop\\projects\\Scouting_Reports', output_filename='all_players_data.json', min_batting_balls_faced=50, min_bowling_balls_bowled=12):
    all_batting_metrics_df, all_bowling_metrics_df = load_and_process_data(data_dir)
    
    # Update player name collection - Step 5
    all_player_names = pd.concat([
        all_batting_metrics_df['player_name'],
        all_bowling_metrics_df['bowler']
    ]).unique()

    if len(all_player_names) == 0:
        return

    all_reports = []
    
    from scouting_report import generate_bowling_report

    for player_name in all_player_names:
        # Step 5 - Existing batting report
        report = generate_report(player_name, all_batting_metrics_df)
        
        # Step 5 - New bowling report
        bowling_report = generate_bowling_report(player_name, all_bowling_metrics_df)
        
        if report:
            report['bowling'] = bowling_report
            all_reports.append(report)
        elif bowling_report:
            # For pure bowlers, use team from bowling report
            all_reports.append({
                "player_name": player_name,
                "team": bowling_report.get('team', "Unknown"),
                "comparison_group": "IPL 2025 Player Report",
                "batting": None,
                "bowling": bowling_report
            })

    output_path = os.path.join(data_dir, output_filename)
    with open(output_path, 'w') as f:
        json.dump(all_reports, f, indent=2, cls=NumpyEncoder)

    print(f"\nDone. {len(all_reports)} players written.")

def convert_numpy_types(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(elem) for elem in obj]
    elif isinstance(obj, (int, float, bool, str)):
        return obj
    elif hasattr(obj, 'item'): # For numpy scalars
        return obj.item()
    elif hasattr(obj, 'tolist'): # For numpy arrays
        return obj.tolist()
    else:
        return obj # Return as is if type is not handled

if __name__ == "__main__":
    # Assuming Cricsheet JSON files are in a 'data' subdirectory
    # Adjust data_dir if your JSON files are elsewhere
    generate_all_reports_json(data_dir='c:\\Users\\Pratham\\Desktop\\projects\\Scouting_Reports', output_filename='all_players_data.json', min_batting_balls_faced=50, min_bowling_balls_bowled=12)
