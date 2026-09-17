import streamlit as st
from streamlit_js_eval import streamlit_js_eval

from calcio_balilla.ui.admin import show_release_notes
from calcio_balilla.ui.state import (
    has_completed_first_check,
    has_notes_been_shown,
    is_notes_dismissed,
    mark_first_check_done,
    mark_notes_shown,
    set_notes_dismissed,
)


CURRENT_VERSION = "1.6.0"
MOBILE_THRESHOLD = 768

GLOBAL_STYLES = """
<style>
    @media (min-width: 768px) {
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 100%;
        }
    }

    @media (max-width: 767px) {
        .stRadio > div {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: #0e1117;
            padding: 10px 0;
            border-top: 1px solid #30363d;
            z-index: 999;
            flex-direction: row !important;
            justify-content: space-around !important;
        }
        .stRadio div[role="radiogroup"] > label {
            margin: 0 !important;
            padding: 5px 10px !important;
            background: none !important;
        }
        .main .block-container {
            padding-bottom: 80px !important;
        }
    }

    div[data-testid="stVerticalBlock"] > div[style*="border: 1px solid"] {
        background-color: #161b22;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border: 1px solid #30363d !important;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
"""


def configure_page():
    st.set_page_config(
        page_title="Calcio Balilla Dashboard",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def inject_global_styles():
    st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)


def resolve_is_mobile():
    width = streamlit_js_eval(js_expressions="window.innerWidth", key="WIDTH")
    if width is None:
        st.info("Initializing UI...")
        return None
    return width < MOBILE_THRESHOLD


def sync_release_notes():
    stored_version = streamlit_js_eval(js_expressions="localStorage.getItem('app_version')", key="get_ver")
    if is_notes_dismissed():
        streamlit_js_eval(
            js_expressions=f"localStorage.setItem('app_version', '{CURRENT_VERSION}')",
            key="set_ver",
        )
        set_notes_dismissed(False)

    if stored_version is not None and stored_version != CURRENT_VERSION:
        if not has_notes_been_shown():
            mark_notes_shown()
            show_release_notes(CURRENT_VERSION)
    elif stored_version is None:
        if not has_completed_first_check():
            mark_first_check_done()
        elif not has_notes_been_shown():
            mark_notes_shown()
            show_release_notes(CURRENT_VERSION)
