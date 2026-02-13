import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Set style
sns.set_theme(style="whitegrid")

def run_analysis():
    print("Running EDA and Visualization...")
    df = pd.read_csv("cleaned_match_data.csv")
    players = pd.read_csv("raw_player_data.csv")
    
    # 1. Line chart: Goals vs xG (Arsenal only)
    plt.figure(figsize=(12, 6))
    arsenal = df[df['Team'] == 'Arsenal-Women'].sort_values('Date')
    plt.plot(arsenal['Date'], arsenal['GF'], marker='o', label='Goals Scored', color='red')
    plt.plot(arsenal['Date'], arsenal['xG'], marker='x', linestyle='--', label='Expected Goals (xG)', color='black')
    plt.title("Arsenal Women: Goals vs Expected Goals (xG) - 2024/25 Season")
    plt.xlabel("Match Date")
    plt.ylabel("Goals")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.savefig("goals_vs_xg.png")
    plt.close()
    
    # 2. Bar chart: Arsenal vs Rivals (Note: Now only Arsenal data available in real set)
    metrics = ['GF', 'xG', 'Possession', 'SoT']
    avg_stats = df.groupby('Team')[metrics].mean().reset_index()
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle("Arsenal Women: Performance Metrics Summary (Real 24/25 Data)")
    
    for i, metric in enumerate(metrics):
        ax = axes[i//2, i%2]
        sns.barplot(data=avg_stats, x='Team', y=metric, ax=ax, palette='Reds')
        ax.set_title(f"Average {metric}")
        
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig("rival_comparison.png")
    plt.close()
    
    # 3. Heatmap: Correlation Matrix (Arsenal only)
    plt.figure(figsize=(10, 8))
    numeric_cols = ['GF', 'GA', 'xG', 'xGA', 'Possession', 'Shots', 'SoT', 'Passing_Accuracy', 'Points']
    corr = arsenal[numeric_cols].corr()
    sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f")
    plt.title("Correlation Matrix: Performance Factors vs Outcomes (Arsenal)")
    plt.tight_layout()
    plt.savefig("correlation_heatmap.png")
    plt.close()
    
    # 4. Scatter plot: xG Difference vs Match Result
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='xG_Diff', y='Goal_Diff', hue='Result', style='Team', s=100)
    plt.axhline(0, color='black', linestyle='--')
    plt.axvline(0, color='black', linestyle='--')
    plt.title("xG Difference vs Goal Difference by Match Result")
    plt.xlabel("xG Difference (xG - xGA)")
    plt.ylabel("Actual Goal Difference")
    plt.tight_layout()
    plt.savefig("xg_diff_vs_result.png")
    plt.close()

    # 5. Player Impact: Goals and Assists
    plt.figure(figsize=(12, 6))
    players_melted = players.melt(id_vars='Player', value_vars=['Goals', 'Assists'], var_name='Type', value_name='Count')
    sns.barplot(data=players_melted.sort_values('Count', ascending=False), x='Player', y='Count', hue='Type', palette='Reds')
    plt.title("Key Player Contributions: Goals & Assists (2024/25)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("player_impact.png")
    plt.close()

    # 6. Defensive Solidity: xGA Trend
    plt.figure(figsize=(12, 6))
    plt.plot(arsenal['Date'], arsenal['xGA'], marker='s', color='blue', label='Expected Goals Against (xGA)')
    plt.axhline(arsenal['xGA'].mean(), color='blue', linestyle='--', label='Avg xGA')
    plt.title("Arsenal Women: Defensive Solidity (xGA per Match)")
    plt.xlabel("Match Date")
    plt.ylabel("xGA")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.savefig("defensive_solidity.png")
    plt.close()

    # 7. Possession vs Efficiency
    plt.figure(figsize=(10, 6))
    sns.regplot(data=arsenal, x='Possession', y='SoT', color='darkred')
    plt.title("Relationship: Possession % vs Shots on Target")
    plt.xlabel("Possession %")
    plt.ylabel("Shots on Target")
    plt.tight_layout()
    plt.savefig("possession_efficiency.png")
    plt.close()

    print("Visualizations saved as PNG files.")

if __name__ == "__main__":
    run_analysis()
