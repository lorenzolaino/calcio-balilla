from calcio_balilla.core.tournament import draw_companions, generate_bracket
from calcio_balilla.data.player_repository import PlayerRepository
from calcio_balilla.data.tournament_repository import TournamentRepository
from db import engine as default_engine


class TournamentService:
    def __init__(self, engine=None, get_connection=None, tournament_repo=None, player_repo=None):
        self.engine = engine or default_engine
        self.repo = tournament_repo or TournamentRepository(self.engine, get_connection)
        self.player_repo = player_repo or PlayerRepository(self.engine, get_connection)

    def create_tournament(self, leaderboard_id, name, participant_ids, rng=None):
        if not name or not name.strip():
            raise ValueError("Tournament name is required.")
        participant_ids = list(dict.fromkeys(participant_ids))
        with self.engine.begin() as conn:
            season_id = self.player_repo.get_active_season_id(conn, leaderboard_id)
            ranking = self.repo.previous_ranking(conn, leaderboard_id)
            specs = generate_bracket(participant_ids, ranking, rng)
            return self.repo.create(conn, leaderboard_id, season_id, name, participant_ids, specs)

    def draw_companions(self, series_id, present_ids, rng=None):
        with self.engine.connect() as conn:
            series = self.repo.lock_series(conn, series_id)
            if not series or series.status != "active":
                raise ValueError("The selected tournament series is not active.")
            used1, used2 = self.repo.used_companions(
                conn, series.id, series.challenger1_id, series.challenger2_id
            )
            return draw_companions(series.challenger1_id, series.challenger2_id,
                                   present_ids, used1, used2, rng)
