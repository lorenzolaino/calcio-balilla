from datetime import datetime

import streamlit as st

import scoring
from calcio_balilla.app_facade import ApplicationFacade
from calcio_balilla.cache import StreamlitCacheManager
from db import engine, get_connection


def _facade() -> ApplicationFacade:
    return ApplicationFacade(
        engine=engine,
        get_connection=get_connection,
        cache_manager=StreamlitCacheManager(st.cache_data),
    )


class DatabaseManager:
    """Compatibility facade for the legacy UI and tests."""

    RECENT_DUPLICATE_MATCH_WINDOW_SECONDS = scoring.RECENT_DUPLICATE_MATCH_WINDOW_SECONDS

    @staticmethod
    def hash_password(password: str) -> str:
        return _facade().hash_password(password)

    @staticmethod
    @st.cache_data
    def get_leaderboards():
        return _facade().get_leaderboards()

    @staticmethod
    @st.cache_data
    def get_active_season(leaderboard_id: int):
        return _facade().get_active_season(leaderboard_id)

    @staticmethod
    @st.cache_data
    def get_closed_seasons(leaderboard_id: int):
        return _facade().get_closed_seasons(leaderboard_id)

    @staticmethod
    def start_next_season(leaderboard_id: int):
        return _facade().start_next_season(leaderboard_id)

    @staticmethod
    @st.cache_data
    def get_leaderboard(leaderboard_id: int, season_id=None):
        return _facade().get_leaderboard(leaderboard_id, season_id=season_id)

    @staticmethod
    def add_player(name: str, leaderboard_id: int):
        return _facade().add_player(name, leaderboard_id)

    @staticmethod
    def toggle_player_status(player_id: int, is_active: bool):
        _facade().toggle_player_status(player_id, is_active)

    @staticmethod
    @st.cache_data
    def get_match_history(limit=50, player_id=None, leaderboard_id=None, season_id=None):
        return _facade().get_match_history(limit=limit, player_id=player_id, leaderboard_id=leaderboard_id, season_id=season_id)

    @staticmethod
    @st.cache_data
    def get_elo_history(leaderboard_id=None, season_id=None):
        return _facade().get_elo_history(leaderboard_id=leaderboard_id, season_id=season_id)

    @staticmethod
    @st.cache_data
    def check_login(username, password):
        return _facade().check_login(username, password)

    @staticmethod
    @st.cache_data
    def get_player_names(leaderboard_id: int):
        return _facade().get_player_names(leaderboard_id)

    @staticmethod
    @st.cache_data
    def get_player_badges(leaderboard_id: int):
        return _facade().get_player_badges(leaderboard_id)

    @staticmethod
    @st.cache_data
    def get_all_players(leaderboard_id: int):
        return _facade().get_all_players(leaderboard_id)

    @staticmethod
    def _expected_score(r_team, r_opp):
        return _facade().expected_score(r_team, r_opp)

    @staticmethod
    def _margin_multiplier(margin):
        return _facade().margin_multiplier(margin)

    @staticmethod
    def _get_k_factor(games):
        return _facade().get_k_factor(games)

    @staticmethod
    def _calculate_match_updates(players, goals_a, goals_b, rating_diff_threshold):
        return _facade().calculate_match_updates(players, goals_a, goals_b, rating_diff_threshold)

    @staticmethod
    def _is_same_match(candidate, existing):
        return _facade().is_same_match(candidate, existing)

    @staticmethod
    def _get_recent_duplicate_match_id(conn, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b, leaderboard_id):
        return _facade().get_recent_duplicate_match_id(
            conn,
            a1_id,
            a2_id,
            b1_id,
            b2_id,
            goals_a,
            goals_b,
            leaderboard_id,
            now=datetime.now(),
        )

    @staticmethod
    @st.cache_data
    def get_future_matches(leaderboard_id: int):
        return _facade().get_future_matches(leaderboard_id)

    @staticmethod
    def generate_calendar(leaderboard_id: int, matches_per_day: int = 3, days: int = 7):
        return _facade().generate_calendar(leaderboard_id, matches_per_day, days)

    @staticmethod
    def get_best_match_for_player(target_player_id: int, available_player_ids: list, leaderboard_id: int):
        return _facade().get_best_match_for_player(target_player_id, available_player_ids, leaderboard_id)

    @staticmethod
    def delete_match(match_id):
        return _facade().delete_match(match_id)

    @staticmethod
    def record_match(a1_name, a2_name, b1_name, b2_name, goals_a, goals_b, leaderboard_id):
        return _facade().record_match(a1_name, a2_name, b1_name, b2_name, goals_a, goals_b, leaderboard_id)
