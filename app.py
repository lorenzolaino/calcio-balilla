#!/usr/bin/env python3
import streamlit as st
import altair as alt
import pandas as pd
from db import init_db
from models import DatabaseManager
from streamlit_js_eval import streamlit_js_eval

CURRENT_VERSION = "1.4.0"
MOBILE_THRESHOLD = 768

# --- Page Config ---
st.set_page_config(
    page_title="Calcio Balilla Dashboard",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS for UI Enhancements ---
st.markdown("""
<style>
    /* Desktop layout adjustments */
    @media (min-width: 768px) {
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 100%;
        }
    }

    /* Mobile Bottom Navigation Bar */
    @media (max-width: 767px) {
        .stRadio > div {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: #0e1117;
            padding: 10px 0;
            border-top: 1px solid #30363d;
            z-index: 999;
            flex-direction: row !important;
            justify-content: space-around !important;
        }
        .stRadio div[role="radiogroup"] > label {
            margin: 0 !important;
            padding: 5px 10px !important;
            background: none !important;
        }
        /* Add padding to bottom of page so content isn't hidden by nav */
        .main .block-container {
            padding-bottom: 80px !important;
        }
    }

    /* Card-like containers */
    div[data-testid="stVerticalBlock"] > div[style*="border: 1px solid"] {
        background-color: #161b22;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border: 1px solid #30363d !important;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- UI Components ---

@st.dialog("🚀 What's New")
def show_release_notes():
    st.markdown(f"""
    ### Version {CURRENT_VERSION} - Strategy & UI Overhaul
    This major update introduces advanced planning tools and a completely redesigned responsive interface.
    
    **New Features & Improvements**:
    1.  **Responsive UI**: A rich Dashboard for Desktop and an optimized Bottom-Navigation view for Mobile.
    2.  **Matchmaking (Leaderboard DG)**: Strategic tool to find optimal matches and maximize Elo gains.
    3.  **Calendar (Leaderboard UT)**: Scheduling tool for automated match planning.
    4.  **Refined Navigation**: New sidebar-based management pages and a unified entry page with "Guest" access.
    5.  **Performance**: Optimized database interactions for faster page loads.
    """)
    if st.button("Got it!"):
        st.session_state['notes_dismissed'] = True
        st.rerun()

def show_leaderboard(l_id, l_name):
    st.subheader("🏆 Leaderboard")
    leaderboard_data = DatabaseManager.get_leaderboard(l_id)
    
    if not leaderboard_data:
        st.info("No stats available for this leaderboard.")
        return

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
    }, use_container_width=True)

def show_elo_trends(l_id):
    st.subheader("📈 Player Elo Trends")
    df_history = DatabaseManager.get_elo_history(l_id)

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
        ).add_params(selection).properties(height=400)

        st.altair_chart(chart, use_container_width=True)

def show_match_history(l_id):
    st.subheader("📜 Match History")
    limit = st.slider("Matches to show", 5, 200, 20, key=f"limit_{l_id}")
    
    all_players_data = DatabaseManager.get_all_players(l_id)
    player_options = ["All Players"] + [p[1] for p in all_players_data]
    player_map = {p[1]: p[0] for p in all_players_data}
    
    selected_player_name = st.selectbox("Filter by Player", player_options, key=f"hist_filter_{l_id}")
    selected_player_id = player_map.get(selected_player_name)
    
    history_data = DatabaseManager.get_match_history(limit, player_id=selected_player_id, leaderboard_id=l_id)

    if not history_data:
        st.info("No matches recorded.")
    else:
        table_rows = []
        for record in history_data:
            is_new_match = record[11] is None
            
            if is_new_match:
                da1 = f"{record[7]:+g}" if record[7] is not None else "+0"
                da2 = f"{record[8]:+g}" if record[8] is not None else "+0"
                db1 = f"{record[9]:+g}" if record[9] is not None else "+0"
                db2 = f"{record[10]:+g}" if record[10] is not None else "+0"
                
                team_a = f"{record[1]} ({da1}) + {record[2]} ({da2})"
                team_b = f"{record[3]} ({db1}) + {record[4]} ({db2})"
                delta_a_display = "-"
                delta_b_display = "-"
            else:
                team_a = f"{record[1]} + {record[2]}"
                team_b = f"{record[3]} + {record[4]}"
                delta_a_display = f"{record[11]:+g}" if record[11] is not None else "-"
                delta_b_display = f"{record[12]:+g}" if record[12] is not None else "-"

            table_rows.append({
                "Date": record[0].strftime("%d/%m/%Y"),
                "Match": f"{team_a} vs {team_b}",
                "Score": f"{record[5]} - {record[6]}",
                "Δ A/B": f"{delta_a_display} / {delta_b_display}"
            })

        st.dataframe(table_rows, hide_index=True, use_container_width=True)

def show_calendar(l_id, can_manage):
    st.subheader("📅 Future Matches")
    
    if can_manage:
        if st.button("Generate Random Schedule"):
            with st.spinner("Generating schedule..."):
                DatabaseManager.generate_calendar(l_id)
            st.success("New schedule generated!")
            st.rerun()

    future_matches = DatabaseManager.get_future_matches(l_id)
    if not future_matches:
        st.info("No future matches scheduled.")
    else:
        table_rows = []
        for record in future_matches:
            table_rows.append({
                "Date": record[0].strftime("%d/%m/%Y %H:%M"),
                "Match": f"{record[1]} + {record[2]} vs {record[3]} + {record[4]}",
            })
        st.dataframe(table_rows, hide_index=True, use_container_width=True)

def show_matchmaking(l_id):
    st.subheader("🎯 Matchmaking")
    players_data = DatabaseManager.get_player_names(l_id)
    players_list = [p[1] for p in players_data]
    player_map = {p[1]: p[0] for p in players_data}

    if len(players_list) < 4:
        st.warning("Need 4+ players.")
        return

    col1, col2 = st.columns(2)
    with col1:
        who_am_i = st.selectbox("Who are you?", players_list, key="mm_who")
    with col2:
        available = st.multiselect("Available players", players_list, default=players_list, key="mm_avail")

    if st.button("Find Best Match"):
        if who_am_i not in available:
            available.append(who_am_i)
        
        if len(available) < 4:
            st.error("Select at least 3 others.")
        else:
            target_id = player_map[who_am_i]
            available_ids = [player_map[name] for name in available]
            
            with st.spinner("Calculating..."):
                best = DatabaseManager.get_best_match_for_player(target_id, available_ids, l_id)
            
            if best:
                st.success("Match found!")
                st.markdown(f"""
                <div style="text-align: center; border: 1px solid #4CAF50; border-radius: 8px; padding: 15px; background-color: rgba(76, 175, 80, 0.05);">
                    <h4>{best['team_a'][0]} & {best['team_a'][1]}</h4>
                    <p style="margin: 5px 0;">VS</p>
                    <h4>{best['team_b'][0]} & {best['team_b'][1]}</h4>
                    <p style="color: #4CAF50; margin-top: 10px;">Win Prob: {best['win_prob']:.1%} | Est. Gain: +{best['est_delta']:.1f}</p>
                </div>
                """, unsafe_allow_html=True)

# --- Admin Page Components ---

def show_new_match(l_id):
    st.subheader("➕ Record New Match")
    players_data = DatabaseManager.get_player_names(l_id)
    players_list = [p[1] for p in players_data]
    if len(players_list) < 4:
        st.warning("At least 4 players required.")
        return

    player_options = ["-"] + players_list
    saving_key = f"match_save_in_progress_{l_id}"
    form_version_key = f"match_form_version_{l_id}"
    form_version = st.session_state.get(form_version_key, 0)
    form_key_prefix = f"admin_match_{l_id}_{form_version}"

    col1, col2 = st.columns(2)
    with col1:
        a1 = st.selectbox("Team A - P1", player_options, index=0, key=f"{form_key_prefix}_a1")
        a2 = st.selectbox("Team A - P2", player_options, index=0, key=f"{form_key_prefix}_a2")
        score_a = st.number_input("Team A Goals", min_value=0, value=10, key=f"{form_key_prefix}_sa")
    with col2:
        b1 = st.selectbox("Team B - P1", player_options, index=0, key=f"{form_key_prefix}_b1")
        b2 = st.selectbox("Team B - P2", player_options, index=0, key=f"{form_key_prefix}_b2")
        score_b = st.number_input("Team B Goals", min_value=0, value=8, key=f"{form_key_prefix}_sb")

    save_btn_placeholder = st.empty()
    save_clicked = save_btn_placeholder.button(
        "Save Match",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.get(saving_key, False),
    )
    if save_clicked:
        if "-" in {a1, a2, b1, b2}:
            st.error("Select all four players.")
        elif len({a1, a2, b1, b2}) < 4:
            st.error("Duplicate players!")
        else:
            try:
                st.session_state[saving_key] = True
                save_btn_placeholder.button("Saving Match...", disabled=True, use_container_width=True)
                DatabaseManager.record_match(a1, a2, b1, b2, score_a, score_b, l_id)
                st.success("Match saved!")
                st.session_state[form_version_key] = form_version + 1
                st.session_state.pop(saving_key, None)
                st.rerun()
            except ValueError as e:
                st.session_state[saving_key] = False
                st.error(str(e))

def show_delete_match(l_id):
    st.subheader("🗑️ Delete Match")
    history_data = DatabaseManager.get_match_history(50, leaderboard_id=l_id)
    if not history_data:
        st.info("No matches found.")
        return

    match_map = {f"[{r[0].strftime('%d/%m %H:%M')}] {r[1]}+{r[2]} vs {r[3]}+{r[4]} ({r[5]}-{r[6]})": r[13] for r in history_data}
    selected = st.multiselect("Select matches to delete", list(match_map.keys()))
    if st.button("Delete Selected", type="primary", use_container_width=True):
        if not selected:
            st.warning("Please select at least one match.")
        else:
            for label in selected:
                DatabaseManager.delete_match(match_map[label])
            st.success("Selected matches deleted!")
            st.rerun()

def show_manage_players(l_id, l_name):
    st.subheader("👥 Manage Players")
    with st.expander("➕ Add New Player"):
        name = st.text_input("Player Name")
        if st.button("Add Player"):
            if name:
                DatabaseManager.add_player(name, l_id)
                st.success(f"Added {name} to {l_name}!")
                st.rerun()
            else:
                st.error("Enter a name.")
    
    st.divider()
    st.write("Toggle Active Status")
    all_players = DatabaseManager.get_all_players(l_id)
    if all_players:
        df_p = pd.DataFrame(all_players, columns=["ID", "Name", "Active"])
        edited = st.data_editor(df_p, column_config={"ID": None, "Name": st.column_config.TextColumn(disabled=True)}, hide_index=True, use_container_width=True)
        if not edited.equals(df_p):
            changed = edited[edited["Active"] != df_p["Active"]]
            for _, row in changed.iterrows():
                DatabaseManager.toggle_player_status(int(row["ID"]), bool(row["Active"]))
            st.success("Updated player status!")
            st.rerun()

# --- Auth Flow ---

def show_login_page():
    # Center the login box
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.title("⚽ Calcio Balilla")
        st.markdown("Please log in or continue as a guest to view the dashboard.")
        
        with st.container(border=True):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Login", use_container_width=True, type="primary"):
                    user = DatabaseManager.check_login(username, password)
                    if user:
                        st.session_state['user'] = {
                            "id": user[0], 
                            "username": user[1], 
                            "role": user[2],
                            "leaderboard_id": user[3]
                        }
                        st.rerun()
                    else:
                        st.error("Login failed")
            with col2:
                if st.button("Continue as Guest", use_container_width=True):
                    st.session_state['user'] = "guest"
                    st.rerun()

# --- Main App Logic ---

def run_web_app():
    init_db()

    # --- Session State Init ---
    if 'user' not in st.session_state:
        st.session_state['user'] = None
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = "Home"
    if 'notes_dismissed' not in st.session_state:
        st.session_state['notes_dismissed'] = False

    # --- Responsive Detection ---
    width = streamlit_js_eval(js_expressions="window.innerWidth", key="WIDTH")
    if width is None:
        st.info("Initializing UI...")
        return
    
    is_mobile = width < MOBILE_THRESHOLD

    # --- Release Notes Logic ---
    stored_version = streamlit_js_eval(js_expressions="localStorage.getItem('app_version')", key="get_ver")
    if st.session_state['notes_dismissed']:
        streamlit_js_eval(js_expressions=f"localStorage.setItem('app_version', '{CURRENT_VERSION}')", key="set_ver")
        st.session_state['notes_dismissed'] = False
    
    if stored_version is not None and stored_version != CURRENT_VERSION:
        if 'notes_shown' not in st.session_state:
            st.session_state['notes_shown'] = True
            show_release_notes()
    elif stored_version is None:
        if 'first_check_done' not in st.session_state:
            st.session_state['first_check_done'] = True
        else:
            if 'notes_shown' not in st.session_state:
                st.session_state['notes_shown'] = True
                show_release_notes()

    # --- Auth Check ---
    if st.session_state['user'] is None:
        show_login_page()
        return

    # --- Leaderboard Selection ---
    leaderboards = DatabaseManager.get_leaderboards()
    leaderboard_options = {l[1]: l[0] for l in leaderboards}
    if 'selected_leaderboard' not in st.session_state:
        st.session_state['selected_leaderboard'] = list(leaderboard_options.keys())[0]
    
    selected_l_name = st.session_state['selected_leaderboard']
    selected_l_id = leaderboard_options[selected_l_name]

    # Helper for permissions
    def can_manage():
        if st.session_state['user'] == "guest" or st.session_state['user'] is None:
            return False
        if st.session_state['user']['role'] == 'admin':
            return True
        if st.session_state['user']['leaderboard_id'] == selected_l_id:
            return True
        return False

    # --- Sidebar ---
    with st.sidebar:
        st.title("Navigation")
        if st.button("🏠 Home / Dashboard", use_container_width=True):
            st.session_state['current_page'] = "Home"
            st.rerun()
            
        if can_manage():
            st.divider()
            st.subheader("Management")
            if st.button("➕ New Match", use_container_width=True):
                st.session_state['current_page'] = "New Match"
                st.rerun()
            if st.button("👥 Manage Players", use_container_width=True):
                st.session_state['current_page'] = "Manage Players"
                st.rerun()
            if st.button("🗑️ Delete Match", use_container_width=True):
                st.session_state['current_page'] = "Delete Match"
                st.rerun()

        st.divider()
        st.subheader("Account")
        if st.session_state['user'] != "guest":
            st.write(f"Logged in: **{st.session_state['user']['username']}**")
        else:
            st.write("Logged in: **Guest**")
            
        if st.button("Logout", use_container_width=True):
            st.session_state['user'] = None
            st.rerun()

    # --- Main Content Header ---
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        st.title(f"⚽ {selected_l_name}")
    with col_t2:
        new_l_name = st.selectbox(
            "Leaderboard", 
            list(leaderboard_options.keys()),
            index=list(leaderboard_options.keys()).index(st.session_state['selected_leaderboard']),
            label_visibility="collapsed"
        )
        if new_l_name != st.session_state['selected_leaderboard']:
            st.session_state['selected_leaderboard'] = new_l_name
            st.rerun()

    # --- View Routing ---
    current_page = st.session_state['current_page']

    if current_page == "New Match":
        show_new_match(selected_l_id)
    elif current_page == "Manage Players":
        show_manage_players(selected_l_id, selected_l_name)
    elif current_page == "Delete Match":
        show_delete_match(selected_l_id)
    else:
        # Standard Views (Home / History / Trends / etc)
        if is_mobile:
            nav_options = ["Home", "History", "Trends"]
            if selected_l_name == "Leaderboard UT":
                nav_options.append("Calendar")
            elif selected_l_name == "Leaderboard DG":
                nav_options.append("Matchmaking")
            
            # Native Tabs for Mobile Navigation
            tabs = st.tabs(nav_options)
            
            for i, tab_name in enumerate(nav_options):
                with tabs[i]:
                    if tab_name == "Home":
                        show_leaderboard(selected_l_id, selected_l_name)
                    elif tab_name == "History":
                        show_match_history(selected_l_id)
                    elif tab_name == "Trends":
                        show_elo_trends(selected_l_id)
                    elif tab_name == "Calendar":
                        show_calendar(selected_l_id, can_manage())
                    elif tab_name == "Matchmaking":
                        show_matchmaking(selected_l_id)
        else:
            # Desktop Dashboard
            col1, col2 = st.columns([3, 2])
            with col1:
                with st.container(border=True):
                    show_leaderboard(selected_l_id, selected_l_name)
                with st.container(border=True):
                    show_match_history(selected_l_id)
            with col2:
                with st.container(border=True):
                    show_elo_trends(selected_l_id)
                if selected_l_name == "Leaderboard UT":
                    with st.container(border=True):
                        show_calendar(selected_l_id, can_manage())
                elif selected_l_name == "Leaderboard DG":
                    with st.container(border=True):
                        show_matchmaking(selected_l_id)

if __name__ == "__main__":
    run_web_app()
