#!/usr/bin/env python3
import streamlit as st
from db import init_db

from calcio_balilla.ui.bootstrap import configure_page, inject_global_styles, resolve_is_mobile, sync_release_notes
from calcio_balilla.ui.state import (
    ensure_selected_leaderboard,
    get_selected_leaderboard_name,
    init_session_state,
    is_authenticated,
)
from calcio_balilla.ui.auth import show_login_page
from calcio_balilla.ui.nav import render_sidebar, render_main_content
from calcio_balilla.ui.services import get_app

configure_page()
inject_global_styles()

def run_web_app():
    init_db()

    # --- Session State Init ---
    init_session_state()

    # --- Responsive Detection ---
    is_mobile = resolve_is_mobile()
    if is_mobile is None:
        return

    # --- Release Notes Logic ---
    sync_release_notes()

    # --- Auth Check ---
    if not is_authenticated():
        show_login_page()
        return

    # --- Leaderboard Selection ---
    leaderboards = get_app().get_leaderboards()
    leaderboard_options = {leaderboard.name: leaderboard.id for leaderboard in leaderboards}
    ensure_selected_leaderboard(leaderboard_options.keys())
    
    selected_l_name = get_selected_leaderboard_name()
    selected_l_id = leaderboard_options[selected_l_name]

    # --- Navigation Sidebar ---
    render_sidebar(selected_l_id)

    # --- Main Content Rendering ---
    render_main_content(is_mobile, selected_l_id, selected_l_name, leaderboard_options)

if __name__ == "__main__":
    run_web_app()
