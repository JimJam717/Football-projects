import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from scouting_report import generate_report, load_and_process_data

st.set_page_config(layout="wide")
st.title("IPL 2025 Player Scouting Report")

# Load data once
@st.cache_data
def get_league_df():
    return load_and_process_data('c:\\Users\\Pratham\\Desktop\\projects\\Scouting_Reports')

league_df = get_league_df()
all_player_names = league_df['player_name'].tolist()

player_name = st.sidebar.text_input("Enter Player Name", "Virat Kohli")
min_balls_faced = st.sidebar.slider("Minimum Balls Faced", 1, 200, 50)

if player_name:
    st.subheader(f"Report for {player_name}")
    
    report_data = generate_report(player_name)

    if report_data:
        st.json(report_data)
    else:
        st.write("No data found for this player or not enough data to generate a report.")

else:
    st.info("Please enter a player name to generate a scouting report.")