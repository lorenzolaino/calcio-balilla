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
    if len(players_data) < 4:
        st.warning("Need 4+ players.")
        return

    badges = get_app().get_player_badges(l_id)
    display_to_player = {f"{p.name} {badges.get(p.name, '')}".strip(): p for p in players_data}
    display_list = list(display_to_player.keys())
    key_prefix = f"mm_{l_id}"

    col1, col2 = st.columns(2)
    with col1:
        who_am_i_lbl = st.selectbox("Who are you?", display_list, key=f"{key_prefix}_who")
    with col2:
        available_lbls = st.multiselect(
            "Available players",
            display_list,
            default=display_list,
            key=f"{key_prefix}_avail",
        )

    if st.button("Find Best Match", key=f"{key_prefix}_find"):
        if who_am_i_lbl not in available_lbls:
            available_lbls.append(who_am_i_lbl)
        
        if len(available_lbls) < 4:
            st.error("Select at least 3 others.")
        else:
            target_id = display_to_player[who_am_i_lbl].id
            available_ids = [display_to_player[lbl].id for lbl in available_lbls]
            
            with st.spinner("Calculating..."):
                best = get_app().get_best_match_for_player(target_id, available_ids, l_id)
            
            if best:
                st.success("Match found!")
                _render_match_suggestion(best)
