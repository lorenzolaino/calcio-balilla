#!/usr/bin/env python3
import streamlit as st
import altair as alt
import pandas as pd
from db import init_db
from models import DatabaseManager
from streamlit_js_eval import streamlit_js_eval

CURRENT_VERSION = "1.4.0"

@st.dialog("🚀 What's New")
def show_release_notes():
    st.markdown(f"""
    ### Version {CURRENT_VERSION} - Strategy & Planning Update
    This update introduces advanced tools for match planning and competitive strategy.
    
    **New Features**:
    1.  **Matchmaking (Leaderboard DG Exclusive)**: A new tool to generate the "Optimal Match." It uses a strategic heuristic to find matches you are likely to win while maximizing Elo gains against your immediate rivals.
    2.  **Calendar (Leaderboard UT Exclusive)**: A scheduling tool that generates a random match calendar, ensuring a variety of pairings and providing a clear view of upcoming games.
    3.  **Refined Navigation**: The sidebar now intelligently shows/hides management tools based on your specific permissions for the selected leaderboard.
    
    **Note**: Management actions (New Match, Manage Players, etc.) are now strictly visible only to logged-in users with appropriate permissions.
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
                    "role": user[2],
                    "leaderboard_id": user[3]
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

    # --- Leaderboard Selection ---
    leaderboards = DatabaseManager.get_leaderboards()
    if not leaderboards:
        st.error("No leaderboards found in database.")
        st.stop()
    
    leaderboard_options = {l[1]: l[0] for l in leaderboards}
    
    # Initialize session state for leaderboard
    if 'selected_leaderboard' not in st.session_state:
        st.session_state['selected_leaderboard'] = list(leaderboard_options.keys())[0]
        
    st.sidebar.title("Leaderboard Settings")
    selected_l_name = st.sidebar.selectbox(
        "Select Leaderboard", 
        list(leaderboard_options.keys()),
        index=list(leaderboard_options.keys()).index(st.session_state['selected_leaderboard'])
    )
    st.session_state['selected_leaderboard'] = selected_l_name
    selected_l_id = leaderboard_options[selected_l_name]

    st.title(f"⚽ {selected_l_name}")

    # Helper for permissions
    def can_manage():
        if st.session_state['user'] is None:
            return False
        if st.session_state['user']['role'] == 'admin':
            return True
        # If the role is specifically linked to this leaderboard
        if st.session_state['user']['leaderboard_id'] == selected_l_id:
            return True
        return False

    # --- Sidebar Navigation ---
    st.sidebar.title("Actions")
    actions = ["Leaderboard", "Match History", "Elo Trends"]
    
    if selected_l_name == "Leaderboard UT":
        actions.insert(1, "Calendar")
    elif selected_l_name == "Leaderboard DG":
        actions.insert(1, "Matchmaking")

    # Only show management actions if the user has permission for this leaderboard
    if can_manage():
        actions.extend(["Manage Players", "New Match", "Delete Match"])

    action = st.sidebar.selectbox(
        "Choose", 
        actions
    )

    if action == "Leaderboard":
        st.subheader("🏆 Leaderboard")
        leaderboard_data = DatabaseManager.get_leaderboard(selected_l_id)
        
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

    elif action == "Calendar":
        st.subheader("📅 Future Matches")
        
        if can_manage():
            if st.button("Generate Random Schedule"):
                with st.spinner("Generating schedule..."):
                    DatabaseManager.generate_calendar(selected_l_id)
                st.success("New schedule generated!")
                st.rerun()

        future_matches = DatabaseManager.get_future_matches(selected_l_id)
        if not future_matches:
            st.info("No future matches scheduled. Managers can generate a new schedule.")
        else:
            table_rows = []
            for record in future_matches:
                table_rows.append({
                    "Date": record[0].strftime("%d/%m/%Y %H:%M"),
                    "Team A": f"{record[1]} + {record[2]}",
                    "vs": "vs",
                    "Team B": f"{record[3]} + {record[4]}",
                })
            st.table(table_rows)

    elif action == "Matchmaking":
        st.subheader("🎯 Optimal Matchmaking")
        players_data = DatabaseManager.get_player_names(selected_l_id)
        players_list = [p[1] for p in players_data]
        player_map = {p[1]: p[0] for p in players_data}

        if len(players_list) < 4:
            st.warning("At least 4 players are required for matchmaking.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                who_am_i = st.selectbox("Who are you?", players_list)
            with col2:
                available = st.multiselect("Available players", players_list, default=players_list)

            if st.button("Generate Next Match"):
                if who_am_i not in available:
                    available.append(who_am_i)
                
                if len(available) < 4:
                    st.error("Select at least 3 other available players.")
                else:
                    target_id = player_map[who_am_i]
                    available_ids = [player_map[name] for name in available]
                    
                    with st.spinner("Finding best match..."):
                        best = DatabaseManager.get_best_match_for_player(target_id, available_ids, selected_l_id)
                    
                    if best:
                        st.success("Best match found!")
                        
                        st.markdown(f"""
                        <div style="text-align: center; border: 2px solid #4CAF50; border-radius: 10px; padding: 20px; background-color: rgba(76, 175, 80, 0.1);">
                            <h3 style="margin: 0;">Team A</h3>
                            <h2 style="margin: 10px 0; color: #4CAF50;">{best['team_a'][0]} & {best['team_a'][1]}</h2>
                            <h4 style="margin: 10px 0;">VS</h4>
                            <h3 style="margin: 0;">Team B</h3>
                            <h2 style="margin: 10px 0; color: #FF5252;">{best['team_b'][0]} & {best['team_b'][1]}</h2>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.write("")
                        col_stat1, col_stat2 = st.columns(2)
                        with col_stat1:
                            st.metric("Win Probability", f"{best['win_prob']:.1%}")
                        with col_stat2:
                            st.metric("Est. Elo Gain", f"+{best['est_delta']:.1f}")
                    else:
                        st.error("Could not generate a match.")

    elif action == "Match History":
        st.subheader("📜 Match History")
        
        # Player filter (include all players so history can be searched for inactive ones)
        all_players_data = DatabaseManager.get_all_players(selected_l_id)
        player_options = ["All Players"] + [p[1] for p in all_players_data]
        player_map = {p[1]: p[0] for p in all_players_data}
        
        selected_player_name = st.selectbox("Filter by Player", player_options)
        selected_player_id = player_map.get(selected_player_name)
        
        limit = st.slider("Number of matches to show", 5, 100, 20)
        history_data = DatabaseManager.get_match_history(limit, player_id=selected_player_id, leaderboard_id=selected_l_id)

        if not history_data:
            st.info("No matches recorded.")
        else:
            table_rows = []
            for record in history_data:
                # A match is "new" if team deltas (delta_a/b) are NULL (None)
                is_new_match = record[11] is None
                
                if is_new_match:
                    # New matches: show individual deltas next to names
                    da1 = f"{record[7]:+g}" if record[7] is not None else "+0"
                    da2 = f"{record[8]:+g}" if record[8] is not None else "+0"
                    db1 = f"{record[9]:+g}" if record[9] is not None else "+0"
                    db2 = f"{record[10]:+g}" if record[10] is not None else "+0"
                    
                    team_a = f"{record[1]} ({da1}) + {record[2]} ({da2})"
                    team_b = f"{record[3]} ({db1}) + {record[4]} ({db2})"
                    delta_a_display = "-"
                    delta_b_display = "-"
                else:
                    # Old matches: show team deltas in the dedicated columns
                    team_a = f"{record[1]} + {record[2]}"
                    team_b = f"{record[3]} + {record[4]}"
                    delta_a_display = f"{record[11]:+g}" if record[11] is not None else "-"
                    delta_b_display = f"{record[12]:+g}" if record[12] is not None else "-"

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
        df_history = DatabaseManager.get_elo_history(selected_l_id)

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

    elif action == "Manage Players":
        st.subheader("👥 Manage Players")
        
        # --- Add Player Section ---
        with st.expander("➕ Add New Player"):
            new_player_name = st.text_input("Player Name")
            add_btn_placeholder = st.empty()
            if add_btn_placeholder.button("Add"):
                if new_player_name:
                    add_btn_placeholder.button("Adding...", disabled=True)
                    with st.spinner("Adding player..."):
                        DatabaseManager.add_player(new_player_name, selected_l_id)
                    st.success(f"Player '{new_player_name}' added to {selected_l_name}")
                    st.rerun()
                else:
                    st.error("Please enter a name")

        st.divider()

        # --- Player Status Management ---
        st.write("Toggle player active status (Inactive players are hidden from Leaderboard and New Match selection)")
        all_players = DatabaseManager.get_all_players(selected_l_id)
        
        if not all_players:
            st.info("No players registered.")
        else:
            # Prepare data for display
            df_players = pd.DataFrame(all_players, columns=["ID", "Name", "Active"])
            
            # Display editable dataframe
            edited_df = st.data_editor(
                df_players,
                column_config={
                    "Active": st.column_config.CheckboxColumn(
                        "Active",
                        help="Uncheck to hide player from leaderboard and selection",
                        default=True,
                    ),
                    "ID": None, # Hide ID column
                    "Name": st.column_config.TextColumn("Player Name", disabled=True)
                },
                disabled=["Name"],
                hide_index=True,
            )

            # Check for changes
            if not edited_df.equals(df_players):
                # Identify which row changed
                changed_rows = edited_df[edited_df["Active"] != df_players["Active"]]
                for _, row in changed_rows.iterrows():
                    DatabaseManager.toggle_player_status(int(row["ID"]), bool(row["Active"]))
                st.success("Changes saved!")
                st.rerun()

    elif action == "New Match":
        st.subheader(f"⚽ Record 2vs2 Match for {selected_l_name}")
        players_data = DatabaseManager.get_player_names(selected_l_id)
        players_list = [p[1] for p in players_data]
        
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

        save_btn_placeholder = st.empty()
        if save_btn_placeholder.button("Save Match"):
            try:
                save_btn_placeholder.button("Saving Match...", disabled=True)
                with st.spinner("Saving match..."):
                    DatabaseManager.record_match(a1, a2, b1, b2, score_a, score_b, selected_l_id)
                st.success(f"✅ Match saved! {selected_l_name} updated.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))
                # Rerun to restore the active button for correction
                st.button("Try Again", on_click=st.rerun)

    elif action == "Delete Match":
        st.subheader(f"🗑️ Delete Match from {selected_l_name}")
        limit = st.slider("Number of matches to search from", 5, 100, 20)
        history_data = DatabaseManager.get_match_history(limit, leaderboard_id=selected_l_id)

        if not history_data:
            st.info("No matches recorded.")
        else:
            match_options = []
            match_map = {}
            for record in history_data:
                # record index 13 is the id (added in DatabaseManager.get_match_history)
                label = f"[{record[0].strftime('%d/%m/%Y %H:%M')}] {record[1]}+{record[2]} vs {record[3]}+{record[4]} ({record[5]}-{record[6]})"
                match_options.append(label)
                match_map[label] = record[13]

            selected_match_labels = st.multiselect("Select matches to delete", match_options)
            
            delete_btn_placeholder = st.empty()
            if delete_btn_placeholder.button("Delete Selected Matches", type="primary"):
                if not selected_match_labels:
                    st.warning("Please select at least one match to delete.")
                else:
                    delete_btn_placeholder.button("Deleting...", type="primary", disabled=True)
                    success_count = 0
                    with st.spinner(f"Deleting {len(selected_match_labels)} matches..."):
                        for label in selected_match_labels:
                            match_id = match_map[label]
                            if DatabaseManager.delete_match(match_id):
                                success_count += 1
                    
                    if success_count == len(selected_match_labels):
                        st.success(f"✅ {success_count} matches deleted and stats restored!")
                        st.rerun()
                    else:
                        st.warning(f"⚠️ {success_count} of {len(selected_match_labels)} matches deleted.")
                        st.rerun()

if __name__ == "__main__":
    run_web_app()
