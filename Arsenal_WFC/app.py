import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Set page config
st.set_page_config(
    page_title="Arsenal Women Analysis 2024/25",
    page_icon="⚽",
    layout="wide"
)

# Custom CSS for Arsenal theme
st.markdown("""
    <style>
    .main {
        background-color: #f5f5f5;
    }
    .stApp {
        background-color: #ffffff;
    }
    h1, h2, h3 {
        color: #DB0007;
    }
    .reportview-container .main .block-container {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #DB0007;
    }
    </style>
    """, unsafe_allow_html=True)

# Load data
@st.cache_data
def load_data():
    df = pd.read_csv("cleaned_match_data.csv")
    players = pd.read_csv("raw_player_data.csv")
    return df, players

try:
    df, players = load_data()
    arsenal_df = df[df['Team'] == 'Arsenal-Women'].sort_values('Date')
except Exception as e:
    st.error(f"Error loading data: {e}. Please run data_collection.py and data_processing.py first.")
    st.stop()

# Header
st.title("⚽ Arsenal Women Performance Analysis")
st.subheader("Data-Driven Insights into the 2024/25 Season")

# Sidebar
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/1200px-Arsenal_FC.svg.png", width=100)
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Season Overview", "Tactical Analysis", "Player Performance", "Conclusion"])

if page == "Season Overview":
    st.header("📊 Season Overview")
    
    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Matches", len(arsenal_df))
    with col2:
        wins = len(arsenal_df[arsenal_df['Result'] == 'W'])
        st.metric("Wins", wins)
    with col3:
        avg_pos = arsenal_df['Possession'].mean()
        st.metric("Avg Possession", f"{avg_pos:.1f}%")
    with col4:
        total_goals = arsenal_df['GF'].sum()
        st.metric("Total Goals", total_goals)

    st.markdown("---")
    
    # Goals vs xG Plot
    st.subheader("Clinical Finishing: Goals vs Expected Goals (xG)")
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(arsenal_df['Date'], arsenal_df['GF'], marker='o', label='Actual Goals', color='#DB0007', linewidth=2)
    ax1.plot(arsenal_df['Date'], arsenal_df['xG'], marker='x', linestyle='--', label='Expected Goals (xG)', color='#063672', alpha=0.7)
    ax1.set_xlabel("Match Date")
    ax1.set_ylabel("Goals")
    plt.xticks(rotation=45)
    ax1.legend()
    st.pyplot(fig1)
    
    st.info("💡 **Insight:** When the red line is above the blue dashed line, Arsenal is 'over-performing' their xG, indicating world-class finishing.")

elif page == "Tactical Analysis":
    st.header("🛡️ Tactical Deep Dive")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Defensive Suppression (xGA)")
        fig_def, ax_def = plt.subplots(figsize=(10, 6))
        ax_def.plot(arsenal_df['Date'], arsenal_df['xGA'], marker='s', color='#063672', label='xG Against')
        ax_def.axhline(arsenal_df['xGA'].mean(), color='red', linestyle='--', label='Avg xGA')
        ax_def.set_title("Expected Goals Against (xGA) Trend")
        plt.xticks(rotation=45)
        ax_def.legend()
        st.pyplot(fig_def)
        st.write("Arsenal maintains a low xGA, typically keeping opponents below 1.0 expected goals.")

    with col2:
        st.subheader("Possession vs Efficiency")
        fig_pos, ax_pos = plt.subplots(figsize=(10, 6))
        sns.regplot(data=arsenal_df, x='Possession', y='SoT', ax=ax_pos, color='#DB0007')
        ax_pos.set_title("Possession % vs Shots on Target")
        st.pyplot(fig_pos)
        st.write("A clear positive correlation shows that Arsenal's possession is purposeful and leads to shots.")

    st.markdown("---")
    st.subheader("Performance Correlation Heatmap")
    fig_corr, ax_corr = plt.subplots(figsize=(10, 8))
    numeric_cols = ['GF', 'GA', 'xG', 'xGA', 'Possession', 'Shots', 'SoT', 'Passing_Accuracy']
    sns.heatmap(arsenal_df[numeric_cols].corr(), annot=True, cmap='Reds', fmt=".2f", ax=ax_corr)
    st.pyplot(fig_corr)

elif page == "Player Performance":
    st.header("🌟 Star Performers")
    
    st.subheader("Goals and Assists Contribution")
    fig_players, ax_players = plt.subplots(figsize=(12, 6))
    players_melted = players.melt(id_vars='Player', value_vars=['Goals', 'Assists'], var_name='Type', value_name='Count')
    sns.barplot(data=players_melted.sort_values('Count', ascending=False), x='Player', y='Count', hue='Type', palette=['#DB0007', '#063672'], ax=ax_players)
    plt.xticks(rotation=45)
    st.pyplot(fig_players)
    
    st.markdown("### Squad Depth")
    st.write("The 2024/25 campaign saw significant contributions from across the frontline, reducing dependency on any single individual.")
    
    # Show player table
    st.dataframe(players.sort_values('Goals', ascending=False), use_container_width=True)

elif page == "Conclusion":
    st.header("🏁 The Winning Formula")
    
    st.markdown("""
    ### Why Arsenal Dominates:
    1. **Sustained Offensive Pressure**: As seen in the *Possession vs Efficiency* chart, Arsenal's high-volume passing game is designed to create high-quality shooting opportunities.
    2. **Clinical Finishing**: The team consistently meets or exceeds its Expected Goals (xG) in high-stakes matches.
    3. **Elite Defensive Structure**: By suppressing opponent xG (typically below 1.0), Arsenal ensures that their offensive output is almost always enough to secure points.
    4. **Multi-Faceted Attack**: With players like Russo, Caldentey, and Mead all contributing goals and assists, opponents cannot focus on marking just one threat.
    
    ---
    *Analysis based on real 2024/25 WSL season data.*
    """)

# Footer
st.markdown("---")
st.caption("Data Science Project: Arsenal Women Performance Analysis | Powered by Streamlit")
