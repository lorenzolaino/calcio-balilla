import streamlit as st

from calcio_balilla.core.calendar_service import current_matchmaking_date
from calcio_balilla.ui.services import get_app


def _rotation_reasons(suggestion):
    reasons = []
    if suggestion.partner_penalty == 0:
        reasons.append("Fresh teammate combinations")
    if suggestion.exact_match_penalty == 0:
        reasons.append("Avoids recent rematch")
    if suggestion.opponent_penalty == 0:
        reasons.append("Fresh opponent combinations")
    return reasons[:2]


def _render_match_suggestion(suggestion, title):
    with st.container(border=True):
        st.markdown(f"### {title}")
        team_col_a, center_col, team_col_b = st.columns([5, 1, 5])
        with team_col_a:
            st.markdown(f"#### {suggestion.team_a[0]} + {suggestion.team_a[1]}")
        with center_col:
            st.markdown("#### vs")
        with team_col_b:
            st.markdown(f"#### {suggestion.team_b[0]} + {suggestion.team_b[1]}")

        probability_a = suggestion.win_probability
        st.metric("Elo balance", f"{probability_a:.0%} / {1 - probability_a:.0%}")
        balance_labels = {
            "A": "Excellent balance",
            "B": "Very good balance",
            "C": "Good balance",
            "D": "Fair balance",
            "E": "Best available balance",
        }
        reasons = [balance_labels[suggestion.balance_band], *_rotation_reasons(suggestion)]
        st.caption(" · ".join(reasons))


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
            "Available players", display_list, default=display_list, key=f"{key_prefix}_avail"
        )

    if st.button("Find Matches", key=f"{key_prefix}_find"):
        selected_labels = list(available_lbls)
        if who_am_i_lbl not in selected_labels:
            selected_labels.append(who_am_i_lbl)
        if len(set(selected_labels)) < 4:
            st.error("Select at least 3 others.")
            return

        target_id = display_to_player[who_am_i_lbl].id
        available_ids = [display_to_player[label].id for label in selected_labels]
        reference_date = current_matchmaking_date()
        with st.spinner("Calculating..."):
            suggestions = get_app().get_match_suggestions_for_player(
                target_id, available_ids, l_id, reference_date
            )
        if suggestions:
            st.success("Matches found!")
            titles = ("Recommended", "Alternative 1", "Alternative 2")
            for title, suggestion in zip(titles, suggestions):
                _render_match_suggestion(suggestion, title)
