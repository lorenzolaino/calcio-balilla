from db import engine as default_engine

from calcio_balilla.data.season_repository import SeasonRepository


class SeasonService:
    def __init__(self, engine=None, season_repo=None, get_connection=None):
        self.engine = engine or default_engine
        self._get_connection = get_connection
        self.season_repo = season_repo or SeasonRepository(self.engine, self._get_connection)

    def start_next_season(self, leaderboard_id: int):
        with self.engine.begin() as conn:
            active_season = self.season_repo.get_active_season_for_update(conn, leaderboard_id)
            if not active_season:
                raise ValueError("No active season found for this leaderboard.")

            next_number = active_season.number + 1
            self.season_repo.close_season(conn, active_season.id)
            return self.season_repo.create_season(conn, leaderboard_id, next_number)
