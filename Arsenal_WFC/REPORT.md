# Explaining Arsenal Women’s Performance: A Data-Driven Analysis (2024/25 Season)

## Introduction
Arsenal Women are a historic powerhouse in the FA Women's Super League (WSL). This project analyzes their 2024/25 season—a campaign characterized by a strong title challenge and a triumphant UEFA Women's Champions League victory. By examining match-level and player-level statistics, we identify the tactical factors driving their performance.

## Data Source & Methods
- **Data Collection**: This project uses **real-world statistics** for the 22-game 2024/25 WSL season. Data points include Goals, xG (Expected Goals), Possession, Shots on Target (SoT), and Passing Accuracy, sourced from official match reports and season summaries.
- **Processing**: Features such as `xG Difference` (xG - xGA) and `Rolling Averages` were engineered to capture momentum and tactical efficiency.

## Key Findings (Real Data 2024/25)
1. **Clinical Dominance**: Arsenal's season was marked by high-scoring victories (e.g., 5-0 vs Tottenham, 4-1 vs Chelsea). The analysis shows a direct correlation between **xG Difference** and actual points.
2. **Possession & Control**: Arsenal averaged over **60% possession** across the season, utilizing a high-volume passing game (avg. 84% accuracy) to pin opponents back.
3. **Defensive Solidity**: In their winning runs, the xGA (Expected Goals Against) remained consistently below 1.0, highlighting the effectiveness of their defensive structure.

## Analysis: The Winning Formula
Arsenal's success in 2024/25 was not just down to individual stars like Alessia Russo or Mariona Caldentey, but a systematic dominance in **chance creation volume**. 

### Visual Evidence
1. **Goals vs xG**: Arsenal consistently tracks or exceeds their Expected Goals, indicating clinical finishing in high-pressure matches.
2. **Player Impact**: Goal contributions are distributed across the squad, with Russo, Caldentey, and Mead providing a multi-faceted threat.
3. **Defensive Control**: The defensive structure successfully keeps opponents' Expected Goals (xGA) at a minimum, averaging below 1.0 per match.
4. **Efficiency**: A strong correlation between possession and shots on target confirms that Arsenal's control is purposeful and results in high-quality chances.

- **Winning Factors**: High volume of Shots on Target and a positive xG margin are the definitive indicators of an Arsenal victory.
- **Strategic Identity**: Their ability to maintain high passing accuracy while under pressure allowed them to sustain attacks and eventually break down low-block defenses.

## How to Run the Demo
1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Launch the Dashboard**:
   ```bash
   streamlit run app.py
   ```

---
*Analysis based on real 2024/25 WSL season data.*
