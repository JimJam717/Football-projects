import pandas as pd
import numpy as np

def preprocess_match_data(input_file, output_file):
    print(f"Preprocessing {input_file}...")
    df = pd.read_csv(input_file)
    
    # 1. Handle missing values
    df = df.fillna(0)
    
    # 2. Derived features
    df['Goal_Diff'] = df['GF'] - df['GA']
    df['xG_Diff'] = df['xG'] - df['xGA']
    
    # Points per match (already in raw, but re-calculating for safety)
    def get_points(result):
        if result == 'W': return 3
        if result == 'D': return 1
        return 0
    df['Points'] = df['Result'].apply(get_points)
    
    # 3. Rolling averages (last 5 matches) per team
    df = df.sort_values(['Team', 'Date'])
    df['Rolling_xG'] = df.groupby('Team')['xG'].transform(lambda x: x.rolling(window=5, min_periods=1).mean())
    df['Rolling_xGA'] = df.groupby('Team')['xGA'].transform(lambda x: x.rolling(window=5, min_periods=1).mean())
    df['Rolling_Goals'] = df.groupby('Team')['GF'].transform(lambda x: x.rolling(window=5, min_periods=1).mean())
    df['Rolling_Possession'] = df.groupby('Team')['Possession'].transform(lambda x: x.rolling(window=5, min_periods=1).mean())
    
    # 4. Standardize numeric features (Optional here, often done before ML)
    # But we'll save the cleaned version with derived features first
    
    df.to_csv(output_file, index=False)
    print(f"Saved cleaned data to {output_file}")

if __name__ == "__main__":
    preprocess_match_data("raw_match_data.csv", "cleaned_match_data.csv")
