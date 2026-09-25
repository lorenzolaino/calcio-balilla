import streamlit as st

from calcio_balilla.ui.services import get_app


def _start_next_season(leaderboard_id: int):
    next_season = get_app().start_next_season(leaderboard_id)
    st.session_state[f"season_admin_success_{leaderboard_id}"] = (
        f"{next_season.name} opened successfully."
    )
    st.rerun()


@st.dialog("Confirm Season Change")
def _confirm_start_next_season_dialog(leaderboard_id: int, leaderboard_name: str, current_season_name: str):
    st.write(
        f"You are about to close **{current_season_name}** for **{leaderboard_name}** "
        f"and open the next season."
    )
    st.write("This action will make the new season the active leaderboard home immediately.")

    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Confirm", type="primary", width="stretch", key=f"season_confirm_{leaderboard_id}"):
            _start_next_season(leaderboard_id)
    with cancel_col:
        if st.button("Cancel", width="stretch", key=f"season_cancel_{leaderboard_id}"):
            st.rerun()


def show_season_admin(l_id, l_name):
    st.subheader("🛠️ Manage Season")
    active_season = get_app().get_active_season(l_id)
    if not active_season:
        st.error("No active season found.")
        return

    success_key = f"season_admin_success_{l_id}"
    success_message = st.session_state.pop(success_key, None)
    if success_message:
        st.success(success_message)

    with st.container(border=True):
        st.markdown(f"### {active_season.name}")
        st.caption(f"{l_name} / active season")

        info_col_1, info_col_2 = st.columns(2)
        with info_col_1:
            st.metric("Season Number", active_season.number)
        with info_col_2:
            st.metric("Status", "Active")

    if st.button("Close Current Season and Open Next", type="primary", width="stretch"):
        _confirm_start_next_season_dialog(l_id, l_name, active_season.name)
