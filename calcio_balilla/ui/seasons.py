import streamlit as st

from calcio_balilla.ui.presenters import format_history_row, format_leaderboard_row
from calcio_balilla.ui.services import get_app


def _render_podium(leaderboard_data):
    if not leaderboard_data:
        st.info("No completed season data available.")
        return

    winner = leaderboard_data[0]
    st.subheader("Champion 🥇")
    with st.container(border=True):
        st.markdown(f"### {winner.name}")
        stat_col_1, stat_col_2, stat_col_3 = st.columns(3)
        with stat_col_1:
            st.metric("Rating", f"{winner.rating:.1f}")
        with stat_col_2:
            st.metric("Wins", winner.wins)
        with stat_col_3:
            st.metric("Goal Diff", winner.goal_diff)

    st.subheader("Top 3 📈")
    st.dataframe(
        [format_leaderboard_row(index, player) for index, player in enumerate(leaderboard_data[:3])],
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Bottom 3 📉")
    bottom_three = leaderboard_data[-3:] if len(leaderboard_data) >= 3 else leaderboard_data
    start_index = max(len(leaderboard_data) - len(bottom_three), 0)
    st.dataframe(
        [format_leaderboard_row(start_index + index, player) for index, player in enumerate(bottom_three)],
        hide_index=True,
        use_container_width=True,
    )


def show_seasons_archive(l_id, l_name):
    st.subheader("📚 Seasons")
    seasons = get_app().get_closed_seasons(l_id)
    if not seasons:
        st.info("No past seasons available.")
        return

    season_options = {season.name: season.id for season in seasons}
    selected_season_name = st.selectbox(
        "Season",
        list(season_options.keys()),
        key=f"season_archive_{l_id}",
    )
    selected_season_id = season_options[selected_season_name]

    leaderboard_data = get_app().get_leaderboard(l_id, season_id=selected_season_id)
    history_data = get_app().get_match_history(200, leaderboard_id=l_id, season_id=selected_season_id)

    st.caption(f"{l_name} / {selected_season_name}")
    _render_podium(leaderboard_data)

    st.subheader("Final Standings")
    st.dataframe(
        [format_leaderboard_row(index, player) for index, player in enumerate(leaderboard_data)],
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Matches")
    if not history_data:
        st.info("No matches recorded in this season.")
        return

    st.dataframe(
        [format_history_row(record) for record in history_data],
        hide_index=True,
        use_container_width=True,
    )
