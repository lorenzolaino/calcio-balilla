import hashlib
from datetime import datetime

import scoring
from calcio_balilla.cache import StreamlitCacheManager
from calcio_balilla.core.calendar_service import CalendarService
from calcio_balilla.core.match_service import MatchService
from calcio_balilla.core.season_service import SeasonService
from calcio_balilla.data.leaderboard_repository import LeaderboardRepository
from calcio_balilla.data.match_repository import MatchRepository
from calcio_balilla.data.player_repository import PlayerRepository
from calcio_balilla.data.season_repository import SeasonRepository
from calcio_balilla.data.user_repository import UserRepository


class ApplicationFacade:
    def __init__(self, engine, get_connection, cache_manager: StreamlitCacheManager):
        self.engine = engine
        self.get_connection = get_connection
        self.cache_manager = cache_manager

    def player_repo(self):
        return PlayerRepository(engine=self.engine, get_connection=self.get_connection)

    def match_repo(self):
        return MatchRepository(engine=self.engine, get_connection=self.get_connection)

    def leaderboard_repo(self):
        return LeaderboardRepository(engine=self.engine, get_connection=self.get_connection)

    def user_repo(self):
        return UserRepository(engine=self.engine, get_connection=self.get_connection)

    def season_repo(self):
        return SeasonRepository(engine=self.engine, get_connection=self.get_connection)

    def match_service(self):
        return MatchService(engine=self.engine, get_connection=self.get_connection)

    def calendar_service(self):
        return CalendarService(engine=self.engine, get_connection=self.get_connection)

    def season_service(self):
        return SeasonService(engine=self.engine, get_connection=self.get_connection)

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def get_leaderboards(self):
        return self.leaderboard_repo().get_leaderboards()

    def get_active_season(self, leaderboard_id: int):
        return self.season_repo().get_active_season(leaderboard_id)

    def get_closed_seasons(self, leaderboard_id: int):
        return self.season_repo().get_closed_seasons(leaderboard_id)

    def start_next_season(self, leaderboard_id: int):
        season = self.season_service().start_next_season(leaderboard_id)
        self.cache_manager.invalidate_all()
        return season

    def get_leaderboard(self, leaderboard_id: int, season_id: int = None):
        return self.player_repo().get_leaderboard(leaderboard_id, season_id=season_id)

    def add_player(self, name: str, leaderboard_id: int):
        player_id = self.player_repo().add_player(name, leaderboard_id)
        self.cache_manager.invalidate_all()
        return player_id

    def toggle_player_status(self, player_id: int, is_active: bool):
        self.player_repo().toggle_player_status(player_id, is_active)
        self.cache_manager.invalidate_all()

    def get_match_history(self, limit=50, player_id=None, leaderboard_id=None, season_id=None):
        return self.match_repo().get_match_history(
            limit=limit,
            player_id=player_id,
            leaderboard_id=leaderboard_id,
            season_id=season_id,
        )

    def get_elo_history(self, leaderboard_id=None, season_id=None):
        return self.player_repo().get_elo_history(leaderboard_id=leaderboard_id, season_id=season_id)

    def check_login(self, username, password):
        hashed_password = self.hash_password(password)
        return self.user_repo().check_login(username, hashed_password)

    def get_player_names(self, leaderboard_id: int):
        return self.player_repo().get_player_names(leaderboard_id)

    def get_player_badges(self, leaderboard_id: int):
        return self.player_repo().get_player_badges(leaderboard_id)

    def get_all_players(self, leaderboard_id: int):
        return self.player_repo().get_all_players(leaderboard_id)

    def get_recent_duplicate_match_id(self, conn, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b, leaderboard_id, now=None):
        return self.match_repo().get_recent_duplicate_match_id(
            conn,
            a1_id,
            a2_id,
            b1_id,
            b2_id,
            goals_a,
            goals_b,
            leaderboard_id,
            now=now or datetime.now(),
        )

    def get_future_matches(self, leaderboard_id: int):
        return self.match_repo().get_future_matches(leaderboard_id)

    def generate_calendar(self, leaderboard_id: int, matches_per_day: int = 3, days: int = 7):
        result = self.calendar_service().generate_calendar(leaderboard_id, matches_per_day, days)
        if result:
            self.cache_manager.invalidate_all()
        return result

    def get_best_match_for_player(self, target_player_id: int, available_player_ids: list, leaderboard_id: int):
        return self.calendar_service().get_best_match_for_player(
            target_player_id,
            available_player_ids,
            leaderboard_id,
        )

    def delete_match(self, match_id):
        result = self.match_service().delete_match(match_id)
        if result:
            self.cache_manager.invalidate_all()
        return result

    def record_match(self, a1_name, a2_name, b1_name, b2_name, goals_a, goals_b, leaderboard_id):
        result = self.match_service().record_match(
            a1_name,
            a2_name,
            b1_name,
            b2_name,
            goals_a,
            goals_b,
            leaderboard_id,
        )
        self.cache_manager.invalidate_all()
        return result

    @staticmethod
    def expected_score(r_team, r_opp):
        return scoring.expected_score(r_team, r_opp)

    @staticmethod
    def margin_multiplier(margin):
        return scoring.margin_multiplier(margin)

    @staticmethod
    def get_k_factor(games):
        return scoring.get_k_factor(games)

    @staticmethod
    def calculate_match_updates(players, goals_a, goals_b, rating_diff_threshold):
        return scoring.calculate_match_updates(players, goals_a, goals_b, rating_diff_threshold)

    @staticmethod
    def is_same_match(candidate, existing):
        return scoring.is_same_match(candidate, existing)
