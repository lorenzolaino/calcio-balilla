from db import engine as default_engine
from calcio_balilla.data.player_repository import PlayerRepository
from calcio_balilla.data.match_repository import MatchRepository
from calcio_balilla.core.domain import MatchPlayerState
import scoring

class MatchService:
    def __init__(self, engine=None, player_repo=None, match_repo=None, get_connection=None):
        self.engine = engine or default_engine
        self._get_connection = get_connection
        self.player_repo = player_repo or PlayerRepository(self.engine, self._get_connection)
        self.match_repo = match_repo or MatchRepository(self.engine, self._get_connection)

    def record_match(self, a1_name, a2_name, b1_name, b2_name, goals_a, goals_b, leaderboard_id):
        if goals_a == goals_b:
            raise ValueError("Draws are not allowed.")
        margin = abs(goals_a - goals_b)
        if margin < 2:
            raise ValueError("Minimum goal difference of 2 required.")

        with self.engine.begin() as conn:
            names = [a1_name, a2_name, b1_name, b2_name]
            
            # 1. Ensure all players exist globally
            self.player_repo.ensure_players_exist_globally(conn, names)

            # 2. Ensure all players have stats entries for this leaderboard
            self.player_repo.ensure_player_stats_exist_for_leaderboard(conn, tuple(names), leaderboard_id)

            # 3. Get rating range for farming threshold
            max_r, min_r = self.player_repo.get_rating_range(conn, leaderboard_id)
            rating_diff_threshold = (max_r - min_r) * 0.5 

            # 4. Fetch existing stats for these players
            rows = self.player_repo.get_player_stats_for_match(conn, tuple(names), leaderboard_id)
            existing = {row.name: MatchPlayerState.from_match_stats(row) for row in rows}

            a1, a2, b1, b2 = [existing[name] for name in names]

            # 5. Check duplicate match
            duplicate_match_id = self.match_repo.get_recent_duplicate_match_id(
                conn, a1.id, a2.id, b1.id, b2.id, goals_a, goals_b, leaderboard_id
            )
            if duplicate_match_id:
                raise ValueError("This match was saved a few seconds ago. Wait before saving the same match again.")

            # 6. Calculate updates
            players, deltas = scoring.calculate_match_updates_for_states(
                [a1, a2, b1, b2], goals_a, goals_b, rating_diff_threshold
            )
            a1, a2, b1, b2 = players
            delta_a1, delta_a2, delta_b1, delta_b2 = deltas

            # 7. Batch Update Player Stats in DB
            updates = [player.to_player_stats_update(leaderboard_id) for player in [a1, a2, b1, b2]]
            self.player_repo.update_player_stats_batch(conn, updates)

            # 8. Insert Match record
            match_id = self.match_repo.insert_match_record(
                conn, a1.id, a2.id, b1.id, b2.id, goals_a, goals_b, delta_a1, delta_a2, delta_b1, delta_b2, leaderboard_id
            )

            # 9. Batch Save Rating History in DB
            history_updates = [
                {"pid": player.id, "mid": match_id, "rating": int(player.rating), "l_id": leaderboard_id}
                for player in [a1, a2, b1, b2]
            ]
            self.match_repo.insert_player_ratings_history_batch(conn, history_updates)
            
        return match_id

    def delete_match(self, match_id):
        with self.engine.begin() as conn:
            # 1. Get match details
            match = self.match_repo.get_match_by_id(conn, match_id)
            if not match:
                return False

            player_ids = [match.a1_id, match.a2_id, match.b1_id, match.b2_id]
            l_id = match.leaderboard_id

            # 2. Fetch involved players' stats
            players_res = self.player_repo.get_player_stats_by_ids(conn, tuple(player_ids), l_id)
            players = {
                player.player_id: MatchPlayerState.from_player_stats(player)
                for player in players_res
            }

            # 3. Calculate restored stats in memory
            roles = [
                (match.a1_id, match.delta_a1, match.goals_a > match.goals_b, match.goals_a - match.goals_b),
                (match.a2_id, match.delta_a2, match.goals_a > match.goals_b, match.goals_a - match.goals_b),
                (match.b1_id, match.delta_b1, match.goals_b > match.goals_a, match.goals_b - match.goals_a),
                (match.b2_id, match.delta_b2, match.goals_b > match.goals_a, match.goals_b - match.goals_a),
            ]

            for pid, delta, is_win, gd_contrib in roles:
                p = players[pid]
                p.rating -= delta
                p.games -= 1
                if is_win:
                    p.wins -= 1
                else:
                    p.losses -= 1
                p.goal_diff -= gd_contrib

            # 4. Get new trends for players
            trends_res = self.player_repo.get_player_trends_excluding_match(conn, tuple(player_ids), match_id, l_id)
            trends = {t.pid: t.trend for t in trends_res}
            for pid, trend in trends.items():
                if pid in players:
                    players[pid].trend = trend

            # 5. Batch Update Player Stats
            updates = [players[pid].to_player_stats_update(l_id) for pid in player_ids]
            self.player_repo.update_player_stats_batch(conn, updates)

            # 6. Delete match history and match record
            self.match_repo.delete_player_ratings_history(conn, match_id)
            self.match_repo.delete_match_record(conn, match_id)

        return True
