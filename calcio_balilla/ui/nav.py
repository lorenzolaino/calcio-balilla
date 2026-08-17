import streamlit as st
from calcio_balilla.ui.state import (
    PAGE_DELETE_MATCH,
    PAGE_HOME,
    PAGE_MANAGE_PLAYERS,
    PAGE_NEW_MATCH,
    PAGE_SEASON_ADMIN,
    PAGE_SEASONS,
    can_manage,
    get_current_page,
    get_selected_leaderboard_name,
    get_user,
    is_authenticated,
    is_guest_user,
    logout_user,
    set_current_page,
    set_selected_leaderboard_name,
)
from calcio_balilla.ui.dashboard import show_leaderboard, show_elo_trends
from calcio_balilla.ui.match_history import show_match_history
from calcio_balilla.ui.matchmaking import show_matchmaking
from calcio_balilla.ui.match_management import show_new_match, show_delete_match
from calcio_balilla.ui.admin import show_manage_players
from calcio_balilla.ui.season_admin import show_season_admin
from calcio_balilla.ui.seasons import show_seasons_archive


def _set_current_page(page_name: str):
    set_current_page(page_name)
    st.rerun()


def _render_mobile_home(selected_l_id, selected_l_name):
    nav_options = ["Home", "History", "Trends"]
    if selected_l_name in {"Leaderboard UT", "Leaderboard DG"}:
        nav_options.append("Matchmaking")

    tabs = st.tabs(nav_options)
    for index, tab_name in enumerate(nav_options):
        with tabs[index]:
            if tab_name == "Home":
                show_leaderboard(selected_l_id, selected_l_name)
            elif tab_name == "History":
                show_match_history(selected_l_id)
            elif tab_name == "Trends":
                show_elo_trends(selected_l_id)
            elif tab_name == "Matchmaking":
                show_matchmaking(selected_l_id)


def _render_desktop_home(selected_l_id, selected_l_name):
    col1, col2 = st.columns([3, 2])
    with col1:
        with st.container(border=True):
            show_leaderboard(selected_l_id, selected_l_name)
        with st.container(border=True):
            show_match_history(selected_l_id)
    with col2:
        with st.container(border=True):
            show_elo_trends(selected_l_id)
        if selected_l_name in {"Leaderboard UT", "Leaderboard DG"}:
            with st.container(border=True):
                show_matchmaking(selected_l_id)


def _render_management_page(current_page, selected_l_id, selected_l_name):
    if current_page == PAGE_NEW_MATCH:
        show_new_match(selected_l_id)
        return True
    if current_page == PAGE_MANAGE_PLAYERS:
        show_manage_players(selected_l_id, selected_l_name)
        return True
    if current_page == PAGE_DELETE_MATCH:
        show_delete_match(selected_l_id)
        return True
    if current_page == PAGE_SEASONS:
        show_seasons_archive(selected_l_id, selected_l_name)
        return True
    if current_page == PAGE_SEASON_ADMIN:
        show_season_admin(selected_l_id, selected_l_name)
        return True
    return False


def render_sidebar(selected_l_id):
    with st.sidebar:
        st.title("Navigation")
        if st.button("🏠 Home / Dashboard", use_container_width=True):
            _set_current_page(PAGE_HOME)

        if st.button("📚 Seasons", use_container_width=True):
            _set_current_page(PAGE_SEASONS)
            
        if can_manage(selected_l_id):
            st.divider()
            st.subheader("Management")
            if st.button("➕ New Match", use_container_width=True):
                _set_current_page(PAGE_NEW_MATCH)
            if st.button("👥 Manage Players", use_container_width=True):
                _set_current_page(PAGE_MANAGE_PLAYERS)
            if st.button("🗑️ Delete Match", use_container_width=True):
                _set_current_page(PAGE_DELETE_MATCH)
            if is_authenticated() and not is_guest_user():
                if st.button("🛠️ Manage Season", use_container_width=True):
                    _set_current_page(PAGE_SEASON_ADMIN)

        st.divider()
        st.subheader("Account")
        if not is_guest_user():
            st.write(f"Logged in: **{get_user()['username']}**")
        else:
            st.write("Logged in: **Guest**")
            
        if st.button("Logout", use_container_width=True):
            logout_user()
            st.rerun()

def render_main_content(is_mobile, selected_l_id, selected_l_name, leaderboard_options):
    # --- Main Content Header ---
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        st.title(f"⚽ {selected_l_name}")
    with col_t2:
        new_l_name = st.selectbox(
            "Leaderboard", 
            list(leaderboard_options.keys()),
            index=list(leaderboard_options.keys()).index(get_selected_leaderboard_name()),
            label_visibility="collapsed"
        )
        if new_l_name != get_selected_leaderboard_name():
            set_selected_leaderboard_name(new_l_name)
            st.rerun()

    # --- View Routing ---
    current_page = get_current_page()

    if _render_management_page(current_page, selected_l_id, selected_l_name):
        return

    if is_mobile:
        _render_mobile_home(selected_l_id, selected_l_name)
    else:
        _render_desktop_home(selected_l_id, selected_l_name)
