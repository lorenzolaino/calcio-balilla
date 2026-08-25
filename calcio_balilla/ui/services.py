import streamlit as st

from calcio_balilla.app_facade import ApplicationFacade
from calcio_balilla.cache import StreamlitCacheManager
from db import engine, get_connection


class CachedApplicationFacade(ApplicationFacade):
    """UI-facing facade that caches database reads across Streamlit reruns."""

    @st.cache_data
    def get_leaderboards(_self):
        return super().get_leaderboards()

    @st.cache_data
    def get_active_season(_self, leaderboard_id: int):
        return super().get_active_season(leaderboard_id)

    @st.cache_data
    def get_closed_seasons(_self, leaderboard_id: int):
        return super().get_closed_seasons(leaderboard_id)

    @st.cache_data
    def get_leaderboard(_self, leaderboard_id: int, season_id: int = None):
        return super().get_leaderboard(leaderboard_id, season_id)

    @st.cache_data
    def get_match_history(_self, limit=50, player_id=None, leaderboard_id=None, season_id=None):
        return super().get_match_history(limit, player_id, leaderboard_id, season_id)

    @st.cache_data
    def get_elo_history(_self, leaderboard_id=None, season_id=None):
        return super().get_elo_history(leaderboard_id, season_id)

    @st.cache_data
    def get_player_names(_self, leaderboard_id: int):
        return super().get_player_names(leaderboard_id)

    @st.cache_data
    def get_player_badges(_self, leaderboard_id: int):
        return super().get_player_badges(leaderboard_id)

    @st.cache_data
    def get_all_players(_self, leaderboard_id: int):
        return super().get_all_players(leaderboard_id)

    @st.cache_data
    def get_future_matches(_self, leaderboard_id: int):
        return super().get_future_matches(leaderboard_id)

    @st.cache_data
    def get_best_match_for_player(_self, target_player_id: int, available_player_ids: list, leaderboard_id: int):
        return super().get_best_match_for_player(
            target_player_id,
            list(available_player_ids),
            leaderboard_id,
        )


def get_app() -> CachedApplicationFacade:
    return CachedApplicationFacade(
        engine=engine,
        get_connection=get_connection,
        cache_manager=StreamlitCacheManager(st.cache_data),
    )
