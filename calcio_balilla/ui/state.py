import streamlit as st


PAGE_HOME = "Home"
PAGE_NEW_MATCH = "New Match"
PAGE_MANAGE_PLAYERS = "Manage Players"
PAGE_DELETE_MATCH = "Delete Match"
PAGE_SEASONS = "Seasons"
PAGE_SEASON_ADMIN = "Manage Season"

SESSION_USER = "user"
SESSION_CURRENT_PAGE = "current_page"
SESSION_SELECTED_LEADERBOARD = "selected_leaderboard"
SESSION_NOTES_DISMISSED = "notes_dismissed"
SESSION_NOTES_SHOWN = "notes_shown"
SESSION_FIRST_CHECK_DONE = "first_check_done"
SESSION_AUTH_TOKEN = "auth_token"

GUEST_USER = "guest"


def init_session_state():
    defaults = {
        SESSION_USER: None,
        SESSION_CURRENT_PAGE: PAGE_HOME,
        SESSION_NOTES_DISMISSED: False,
        SESSION_AUTH_TOKEN: None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_user():
    return st.session_state.get(SESSION_USER)


def is_guest_user() -> bool:
    return get_user() == GUEST_USER


def is_authenticated() -> bool:
    return get_user() is not None


def set_user(user):
    st.session_state[SESSION_USER] = user


def set_guest_user():
    set_user(GUEST_USER)


def get_auth_token():
    return st.session_state.get(SESSION_AUTH_TOKEN)


def set_auth_token(token):
    st.session_state[SESSION_AUTH_TOKEN] = token


def logout_user():
    set_user(None)
    set_auth_token(None)


def get_current_page() -> str:
    return st.session_state[SESSION_CURRENT_PAGE]


def set_current_page(page_name: str):
    st.session_state[SESSION_CURRENT_PAGE] = page_name


def ensure_selected_leaderboard(leaderboard_names):
    if SESSION_SELECTED_LEADERBOARD not in st.session_state:
        st.session_state[SESSION_SELECTED_LEADERBOARD] = list(leaderboard_names)[0]


def get_selected_leaderboard_name() -> str:
    return st.session_state[SESSION_SELECTED_LEADERBOARD]


def set_selected_leaderboard_name(leaderboard_name: str):
    st.session_state[SESSION_SELECTED_LEADERBOARD] = leaderboard_name


def is_notes_dismissed() -> bool:
    return st.session_state[SESSION_NOTES_DISMISSED]


def set_notes_dismissed(value: bool):
    st.session_state[SESSION_NOTES_DISMISSED] = value


def has_notes_been_shown() -> bool:
    return SESSION_NOTES_SHOWN in st.session_state


def mark_notes_shown():
    st.session_state[SESSION_NOTES_SHOWN] = True


def has_completed_first_check() -> bool:
    return SESSION_FIRST_CHECK_DONE in st.session_state


def mark_first_check_done():
    st.session_state[SESSION_FIRST_CHECK_DONE] = True


def can_manage(selected_l_id: int) -> bool:
    user = get_user()
    if user is None or user == GUEST_USER:
        return False
    if user.get("role") == "admin":
        return True
    if user.get("leaderboard_id") == selected_l_id:
        return True
    return False
