import streamlit as st
from calcio_balilla.ui.services import get_app

def show_new_match(l_id):
    st.subheader("➕ Record New Match")
    players_data = get_app().get_player_names(l_id)
    if len(players_data) < 4:
        st.warning("At least 4 players required.")
        return

    badges = get_app().get_player_badges(l_id)
    display_map = {f"{p.name} {badges.get(p.name, '')}".strip(): p.name for p in players_data}
    display_map["-"] = "-"
    player_options = ["-"] + [f"{p.name} {badges.get(p.name, '')}".strip() for p in players_data]

    saving_key = f"match_save_in_progress_{l_id}"
    form_version_key = f"match_form_version_{l_id}"
    form_version = st.session_state.get(form_version_key, 0)
    form_key_prefix = f"admin_match_{l_id}_{form_version}"

    season = get_app().get_active_season(l_id)
    tournaments = get_app().get_tournaments(l_id, season.id if season else None)
    tournament_options = {"No tournament": None}
    tournament_options.update({t.name: t for t in tournaments if t.status == "active"})
    tournament_label = st.selectbox("Tournament match", list(tournament_options), key=f"{form_key_prefix}_tournament")
    selected_tournament = tournament_options[tournament_label]
    series_id = None
    if selected_tournament:
        active_series = get_app().get_tournament_series(selected_tournament.id, active_only=True)
        series_options = {
            f"{s.round_name}: {s.challenger1_name} vs {s.challenger2_name} ({s.wins1}-{s.wins2})": s.id
            for s in active_series
        }
        if not series_options:
            st.warning("This tournament has no active series.")
        else:
            series_id = series_options[st.selectbox("Series", list(series_options), key=f"{form_key_prefix}_series")]

    with st.form(key=f"{form_key_prefix}_form"):
        col1, col2 = st.columns(2)
        with col1:
            a1_lbl = st.selectbox("Team A - P1", player_options, index=0, key=f"{form_key_prefix}_a1")
            a2_lbl = st.selectbox("Team A - P2", player_options, index=0, key=f"{form_key_prefix}_a2")
            score_a = st.number_input("Team A Goals", min_value=0, value=10, key=f"{form_key_prefix}_sa")
        with col2:
            b1_lbl = st.selectbox("Team B - P1", player_options, index=0, key=f"{form_key_prefix}_b1")
            b2_lbl = st.selectbox("Team B - P2", player_options, index=0, key=f"{form_key_prefix}_b2")
            score_b = st.number_input("Team B Goals", min_value=0, value=8, key=f"{form_key_prefix}_sb")
        save_clicked = st.form_submit_button(
            "Save Match",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get(saving_key, False),
        )

    if save_clicked:
        a1, a2, b1, b2 = display_map[a1_lbl], display_map[a2_lbl], display_map[b1_lbl], display_map[b2_lbl]
        if "-" in {a1, a2, b1, b2}:
            st.error("Select all four players.")
        elif len({a1, a2, b1, b2}) < 4:
            st.error("Duplicate players!")
        else:
            try:
                st.session_state[saving_key] = True
                if selected_tournament and series_id is None:
                    raise ValueError("Select an active tournament series.")
                get_app().record_match(a1, a2, b1, b2, score_a, score_b, l_id, series_id)
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
