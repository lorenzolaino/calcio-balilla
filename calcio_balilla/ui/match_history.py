import streamlit as st
from calcio_balilla.ui.presenters import format_history_row
from calcio_balilla.ui.services import get_app

def show_match_history(l_id):
    st.subheader("📜 Match History")
    limit = st.slider("Matches to show", 5, 200, 20, key=f"limit_{l_id}")
    
    all_players_data = get_app().get_all_players(l_id)
    player_options = ["All Players"] + [p.name for p in all_players_data]
    player_map = {p.name: p.id for p in all_players_data}
    
    selected_player_name = st.selectbox("Filter by Player", player_options, key=f"hist_filter_{l_id}")
    selected_player_id = player_map.get(selected_player_name)
    
    history_data = get_app().get_match_history(limit, player_id=selected_player_id, leaderboard_id=l_id)

    if not history_data:
        st.info("No matches recorded.")
    else:
        st.dataframe(
            [format_history_row(record) for record in history_data],
            hide_index=True,
            use_container_width=True,
        )
