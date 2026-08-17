import streamlit as st
from calcio_balilla.ui.services import get_app

def show_new_match(l_id):
    st.subheader("➕ Record New Match")
    players_data = get_app().get_player_names(l_id)
    players_list = [p.name for p in players_data]
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
                get_app().record_match(a1, a2, b1, b2, score_a, score_b, l_id)
                st.success("Match saved!")
                st.session_state[form_version_key] = form_version + 1
                st.session_state.pop(saving_key, None)
                st.rerun()
            except ValueError as e:
                st.session_state[saving_key] = False
                st.error(str(e))

def show_delete_match(l_id):
    st.subheader("🗑️ Delete Match")
    history_data = get_app().get_match_history(50, leaderboard_id=l_id)
    if not history_data:
        st.info("No matches found.")
        return

    match_map = {f"[{r.date.strftime('%d/%m %H:%M')}] {r.a1}+{r.a2} vs {r.b1}+{r.b2} ({r.goals_a}-{r.goals_b})": r.id for r in history_data}
    selected = st.multiselect("Select matches to delete", list(match_map.keys()))
    if st.button("Delete Selected", type="primary", use_container_width=True):
        if not selected:
            st.warning("Please select at least one match.")
        else:
            for label in selected:
                get_app().delete_match(match_map[label])
            st.success("Selected matches deleted!")
            st.rerun()
