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

    st.write("Select the players who are present.")
    checkbox_columns = st.columns(3)
    available_ids = []
    for index, label in enumerate(display_list):
        player = display_to_player[label]
        with checkbox_columns[index % len(checkbox_columns)]:
            if st.checkbox(label, value=False, key=f"{key_prefix}_player_{player.id}"):
                available_ids.append(player.id)

    if st.button("Find Matches", key=f"{key_prefix}_find"):
        if len(available_ids) < 4:
            st.error("Select at least 4 players.")
            return

        reference_date = current_matchmaking_date()
        with st.spinner("Calculating..."):
            suggestions = get_app().get_match_suggestions(available_ids, l_id, reference_date)
        if suggestions:
            st.success("Daily matches found!")
            if len(available_ids) > 12:
                st.info(
                    "Three 2v2 matches have 12 places, so not every selected player can play today."
                )
            titles = ("Match 1", "Match 2", "Match 3")
            for title, suggestion in zip(titles, suggestions):
                _render_match_suggestion(suggestion, title)
