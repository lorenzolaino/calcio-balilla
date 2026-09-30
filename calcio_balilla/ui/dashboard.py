import streamlit as st
import altair as alt
from calcio_balilla.ui.presenters import format_leaderboard_row
from calcio_balilla.ui.services import get_app

CIM_LINE = 924

def show_leaderboard(l_id, l_name):
    active_season = get_app().get_active_season(l_id)
    title = "🏆 Leaderboard"
    if active_season:
        title = f"🏆 Leaderboard · {active_season.name}"
    st.subheader(title)
    leaderboard_data = get_app().get_leaderboard(l_id)
    
    if not leaderboard_data:
        st.info("No stats available for this leaderboard.")
        return

    badges = get_app().get_player_badges(l_id)

    st.dataframe([
        format_leaderboard_row(index, player, badge=badges.get(player.name, ""))
        for index, player in enumerate(leaderboard_data)
    ], hide_index=True, column_config={
        "Win %": st.column_config.NumberColumn(format="%.1f%%"),
        "Rating": st.column_config.NumberColumn(format="%.1f")
    }, use_container_width=True)

def show_elo_trends(l_id):
    st.subheader("📈 Player Elo Trends")
    df_history = get_app().get_elo_history(l_id)

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

    _render_elo_markers(df_history)


def _format_points(value):
    if value is None:
        return "—"
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.1f}"


def _render_elo_markers(df_history):
    highest_str = "—"
    lowest_str = "—"
    if not df_history.empty and "rating" in df_history.columns and "player" in df_history.columns:
        max_val = df_history["rating"].max()
        max_players = df_history[df_history["rating"] == max_val]["player"].unique()
        highest_str = f"{_format_points(max_val)} ({', '.join(max_players)})"

        min_val = df_history["rating"].min()
        min_players = df_history[df_history["rating"] == min_val]["player"].unique()
        lowest_str = f"{_format_points(min_val)} ({', '.join(min_players)})"

    st.markdown(
        f"""
        <div style="margin-top: -20px; margin-bottom: 15px; font-size: 0.9rem; text-align: center; opacity: 0.85;">
            <span style="margin-right: 18px;"><strong>Highest:</strong> {highest_str}</span>
            <span style="margin-right: 18px;">•</span>
            <span style="margin-right: 18px;"><strong>Cim Line:</strong> {CIM_LINE}</span>
            <span style="margin-right: 18px;">•</span>
            <span><strong>Lowest:</strong> {lowest_str}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
