#!/usr/bin/env python3
import streamlit as st
import altair as alt
from db import init_db
from models import DatabaseManager
from streamlit_js_eval import streamlit_js_eval

CURRENT_VERSION = "1.1.0"

@st.dialog("🚀 What's New")
def show_release_notes():
    st.markdown(f"""
    ### Version {CURRENT_VERSION}
    Welcome to the new update! Here are the main changes:
    
    1.  **Advanced Scoring Algorithm**:
        *   **Continuous K-Factor**: Your score now adapts constantly to your experience. The more you play, the more stable your rating becomes, without abrupt jumps.
        *   **Individual Scoring**: Each player receives points based on their own experience level. Teammates can now get different points in the same match!
    2.  **Anti-Farming System**:
        *   Dynamic threshold introduced (50% of the total leaderboard spread).
        *   Unbalanced matches are penalized: favored team win = halved points; favored team loss = heavy penalty (+50%).
        *   "Underdogs" are protected: they lose fewer points against top players and gain much more if they pull off an upset.
    3.  **Decimal Precision**: Scores now show one decimal place to accurately reflect small changes and individual differences.
    """)
    if st.button("Got it!"):
        st.session_state['notes_dismissed'] = True
        st.rerun()

def run_web_app():
    # Initialize database tables
    init_db()

    # --- Release Popup Logic ---
    if 'notes_dismissed' not in st.session_state:
        st.session_state['notes_dismissed'] = False

    # Get version from localStorage
    stored_version = streamlit_js_eval(js_expressions="localStorage.getItem('app_version')", key="get_ver")
    
    # If we just clicked "Got it!", save to browser and don't show anymore
    if st.session_state['notes_dismissed']:
        streamlit_js_eval(js_expressions=f"localStorage.setItem('app_version', '{CURRENT_VERSION}')", key="set_ver")
        st.session_state['notes_dismissed'] = False # Reset for next session/version
        st.session_state['notes_active'] = False
    
    # Show popup only if:
    # 1. JS component responded (stored_version is not None as in "loading")
    # 2. Stored version is different from current
    # 3. Not already shown/closed in this session
    if stored_version is not None and stored_version != CURRENT_VERSION:
        if 'notes_shown' not in st.session_state:
            st.session_state['notes_shown'] = True
            show_release_notes()
    elif stored_version is None:
        # This handles the first time visit (empty localStorage)
        # but we must be careful since streamlit_js_eval returns None while loading.
        # We use a small trick: if after one refresh it's still None, it's truly empty.
        if 'first_check_done' not in st.session_state:
            st.session_state['first_check_done'] = True
        else:
            if 'notes_shown' not in st.session_state:
                st.session_state['notes_shown'] = True
                show_release_notes()

    # --- Session State / Auth ---
    if 'user' not in st.session_state:
        st.session_state['user'] = None

    st.sidebar.title("Account")

    if st.session_state['user'] is None:
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login"):
            user = DatabaseManager.check_login(username, password)
            if user:
                st.session_state['user'] = {
                    "id": user[0], 
                    "username": user[1], 
                    "role": user[2]
                }
                st.success(f"Welcome {user[1]}!")
                st.rerun()
            else:
                st.error("Login failed")
    else:
        st.sidebar.write(
            f"Logged in as {st.session_state['user']['username']} "
            f"({st.session_state['user']['role']})"
        )
        if st.sidebar.button("Logout"):
            st.session_state['user'] = None
            st.rerun()

    st.title("⚽ Calcio Balilla - Elo Leaderboard")

    # --- Sidebar Navigation ---
    st.sidebar.title("Actions")
    action = st.sidebar.selectbox(
        "Choose", 
        ["Leaderboard", "Match History", "Elo Trends", "Add Player", "New Match"]
    )

    if action == "Leaderboard":
        st.subheader("🏆 Leaderboard")
        leaderboard_data = DatabaseManager.get_leaderboard()
        
        st.dataframe([
            {
                "Rank": index + 1,
                "Player": player[0],
                "Rating": round(player[1], 1),
                "Matches": player[2],
                "W": player[3],
                "L": player[4],
                "GD": player[5],
                "Win %": (player[3] / player[2] * 100) if player[2] > 0 else 0.0,
                "Trend": player[6] if player[6] else "-"
            }
            for index, player in enumerate(leaderboard_data)
        ], hide_index=True, column_config={
            "Win %": st.column_config.NumberColumn(format="%.1f%%"),
            "Rating": st.column_config.NumberColumn(format="%.1f")
        })

    elif action == "Match History":
        st.subheader("📜 Match History")
        limit = st.slider("Number of matches to show", 5, 100, 20)
        history_data = DatabaseManager.get_match_history(limit)

        if not history_data:
            st.info("No matches recorded.")
        else:
            table_rows = []
            for record in history_data:
                # Logic: if individual deltas are all 0, it's an old match
                is_new_match = any([record[7], record[8], record[9], record[10]])
                
                if is_new_match:
                    team_a = f"{record[1]} ({record[7]:+g}) + {record[2]} ({record[8]:+g})"
                    team_b = f"{record[3]} ({record[9]:+g}) + {record[4]} ({record[10]:+g})"
                    delta_a_display = "-"
                    delta_b_display = "-"
                else:
                    team_a = f"{record[1]} + {record[2]}"
                    team_b = f"{record[3]} + {record[4]}"
                    delta_a_display = f"{record[11]:+g}"
                    delta_b_display = f"{record[12]:+g}"

                table_rows.append({
                    "Date": record[0].strftime("%d/%m/%Y %H:%M"),
                    "Team A": team_a,
                    "Score": f"{record[5]} - {record[6]}",
                    "Team B": team_b,
                    "Δ Elo A": delta_a_display,
                    "Δ Elo B": delta_b_display,
                })

            st.table(table_rows)
    
    elif action == "Elo Trends":
        st.subheader("📈 Player Elo Trends")
        df_history = DatabaseManager.get_elo_history()

        if df_history.empty:
            st.info("No historical data available.")
        else:
            selection = alt.selection_point(
                fields=["player"],
                bind="legend",
                toggle=True
            )
            
            chart = alt.Chart(df_history).mark_line(point=True).encode(
                x=alt.X("created_at:T", title="Date"),
                y=alt.Y(
                    "rating:Q", 
                    scale=alt.Scale(zero=False), 
                    title="Elo Rating"
                ),
                color=alt.Color("player:N", title="Player"),
                opacity=alt.condition(
                    selection,
                    alt.value(1.0),
                    alt.value(0.05)
                ),
                tooltip=["player", "rating", "created_at"]
            ).add_params(selection).properties(height=500)

            st.altair_chart(chart, use_container_width=True)

    elif action == "Add Player":
        if st.session_state['user'] is None or st.session_state['user']['role'] != 'user':
            st.warning("You must be logged in to add players")
        else:
            player_name = st.text_input("Player Name")
            if st.button("Add"):
                DatabaseManager.add_player(player_name)
                st.success(f"Player '{player_name}' added")
                st.rerun()

    elif action == "New Match":
        if st.session_state['user'] is None or st.session_state['user']['role'] != 'user':
            st.warning("You must be logged in to record matches")
        else:
            st.subheader("⚽ Record 2vs2 Match")
            players_list = DatabaseManager.get_player_names()
            if len(players_list) < 4:
                st.warning("At least 4 players are required to record a match.")
                st.stop()
                
            col1, col2 = st.columns(2)
            with col1:
                a1 = st.selectbox("Team A - Player 1", players_list, key="a1")
                a2 = st.selectbox("Team A - Player 2", players_list, key="a2")
            with col2:
                b1 = st.selectbox("Team B - Player 1", players_list, key="b1")
                b2 = st.selectbox("Team B - Player 2", players_list, key="b2")

            col3, col4 = st.columns(2)
            with col3:
                score_a = st.number_input("Team A Goals", min_value=0, value=10)
            with col4:
                score_b = st.number_input("Team B Goals", min_value=0, value=8)

            selected_players = {a1, a2, b1, b2}
            if len(selected_players) < 4:
                st.error("Each player can only appear once in a match.")
                st.stop()

            if st.button("Save Match"):
                try:
                    DatabaseManager.record_match(a1, a2, b1, b2, score_a, score_b)
                    st.success("✅ Match saved! Leaderboard updated.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

if __name__ == "__main__":
    run_web_app()
