import json

from streamlit_js_eval import streamlit_js_eval

from calcio_balilla.ui.services import get_app
from calcio_balilla.ui.state import GUEST_USER, set_auth_token, set_user


AUTH_STORAGE_KEY = "calcio_balilla_auth_token"


def restore_persisted_login() -> bool:
    """Restore an authenticated session after a browser refresh."""
    token = streamlit_js_eval(
        js_expressions=f"localStorage.getItem('{AUTH_STORAGE_KEY}') || ''",
        key="get_auth_token",
    )
    if token is None:
        return False

    if not token:
        return True

    identity = get_app().get_session_identity(token)
    if identity == GUEST_USER:
        set_auth_token(token)
        set_user(GUEST_USER)
    elif identity:
        set_auth_token(token)
        set_user({
            "id": identity.id,
            "username": identity.username,
            "role": identity.role,
            "leaderboard_id": identity.leaderboard_id,
        })
    else:
        _remove_browser_token()
    return True


def persist_login(user_id=None):
    token = get_app().create_session(user_id)
    set_auth_token(token)
    _set_browser_token(token)
    return token


def clear_persisted_login(token):
    if token:
        get_app().delete_session(token)
    _remove_browser_token()


def _set_browser_token(token: str):
    streamlit_js_eval(
        js_expressions=(
            f"localStorage.setItem('{AUTH_STORAGE_KEY}', {json.dumps(token)})"
        ),
        key="set_auth_token",
    )


def _remove_browser_token():
    streamlit_js_eval(
        js_expressions=f"localStorage.removeItem('{AUTH_STORAGE_KEY}')",
        key="remove_auth_token",
    )
