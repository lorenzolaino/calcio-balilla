import streamlit as st
from calcio_balilla.ui.services import get_app


def _render_match_suggestion(best_match):
    with st.container(border=True):
        team_col_a, center_col, team_col_b = st.columns([5, 1, 5])
        with team_col_a:
            st.markdown(f"#### {best_match['team_a'][0]} & {best_match['team_a'][1]}")
        with center_col:
            st.markdown("#### vs")
        with team_col_b:
            st.markdown(f"#### {best_match['team_b'][0]} & {best_match['team_b'][1]}")

        metric_col_1, metric_col_2 = st.columns(2)
        with metric_col_1:
            st.metric("Win Prob", f"{best_match['win_prob']:.1%}")
        with metric_col_2:
            st.metric("Est. Gain", f"+{best_match['est_delta']:.1f}")


def show_matchmaking(l_id):
    st.subheader("🎯 Matchmaking")
    players_data = get_app().get_player_names(l_id)
    players_list = [p.name for p in players_data]
    player_map = {p.name: p.id for p in players_data}

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
                best = get_app().get_best_match_for_player(target_id, available_ids, l_id)
            
            if best:
                st.success("Match found!")
                _render_match_suggestion(best)
