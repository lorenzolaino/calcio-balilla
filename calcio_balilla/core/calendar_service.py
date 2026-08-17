import random
import itertools
from datetime import datetime, timedelta
from db import engine as default_engine
from calcio_balilla.data.player_repository import PlayerRepository
from calcio_balilla.data.match_repository import MatchRepository
from calcio_balilla.data.season_repository import SeasonRepository
import scoring

class CalendarService:
    def __init__(self, engine=None, player_repo=None, match_repo=None, season_repo=None, get_connection=None):
        self.engine = engine or default_engine
        self._get_connection = get_connection
        self.player_repo = player_repo or PlayerRepository(self.engine, self._get_connection)
        self.match_repo = match_repo or MatchRepository(self.engine, self._get_connection)
        self.season_repo = season_repo or SeasonRepository(self.engine, self._get_connection)

    def generate_calendar(self, leaderboard_id: int, matches_per_day: int = 3, days: int = 7):
        players_data = self.player_repo.get_player_names(leaderboard_id)
        if len(players_data) < 4:
            return False

        player_ids = [player.id for player in players_data]
        active_season = self.season_repo.get_active_season(leaderboard_id)
        
        with self.engine.begin() as conn:
            self.match_repo.delete_future_matches(conn, leaderboard_id)
            
            start_date = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
            
            future_matches_to_insert = []
            for d in range(days):
                current_day = start_date + timedelta(days=d)
                for m in range(matches_per_day):
                    match_time = current_day + timedelta(minutes=30 * m)
                    selected = random.sample(player_ids, 4)
                    
                    future_matches_to_insert.append({
                        "date": match_time,
                        "a1": selected[0], "a2": selected[1],
                        "b1": selected[2], "b2": selected[3],
                        "l_id": leaderboard_id,
                        "s_id": active_season.id,
                    })
            
            if future_matches_to_insert:
                self.match_repo.insert_future_matches(conn, future_matches_to_insert)
        return True

    def get_best_match_for_player(self, target_player_id: int, available_player_ids: list, leaderboard_id: int):
        active_season = self.season_repo.get_active_season(leaderboard_id)
        all_stats = self.player_repo.get_active_players_ratings_games(leaderboard_id, active_season.id)
        stats_dict = {s.id: {"name": s.name, "rating": s.rating, "games": s.games} for s in all_stats}
        
        if target_player_id not in available_player_ids:
            available_player_ids.append(target_player_id)
            
        if len(available_player_ids) < 4:
            return None

        target_rating = stats_dict[target_player_id]["rating"]
        
        # Identify rivals: players with rating close to target (e.g., +/- 100)
        rivals = [s.id for s in all_stats if s.id != target_player_id and abs(s.rating - target_rating) < 150]
        if not rivals:
            rivals = [s.id for s in all_stats if s.id != target_player_id]

        best_score = -9999
        best_match = None
        
        # Limit to 10 available players + target
        if len(available_player_ids) > 10:
             available_player_ids = sorted(available_player_ids, key=lambda x: abs(stats_dict[x]["rating"] - target_rating))[:10]
             if target_player_id not in available_player_ids:
                 available_player_ids[-1] = target_player_id

        other_players = [p for p in available_player_ids if p != target_player_id]
        for combo in itertools.combinations(other_players, 3):
            p1, p2, p3 = combo
            possible_teams = [
                ((target_player_id, p1), (p2, p3)),
                ((target_player_id, p2), (p1, p3)),
                ((target_player_id, p3), (p1, p2))
            ]
            
            for team_a, team_b in possible_teams:
                r_a = (stats_dict[team_a[0]]["rating"] + stats_dict[team_a[1]]["rating"]) / 2.0
                r_b = (stats_dict[team_b[0]]["rating"] + stats_dict[team_b[1]]["rating"]) / 2.0
                
                exp_a = scoring.expected_score(r_a, r_b)
                
                k = scoring.get_k_factor(stats_dict[target_player_id]["games"])
                delta_if_win = k * 1.0 * (1.0 - exp_a)
                
                rival_impact = 0
                for p_id in team_b:
                    if p_id in rivals:
                        rival_impact += 1
                for p_id in team_a:
                    if p_id == target_player_id: continue
                    if p_id in rivals:
                        rival_impact -= 0.5
                
                match_score = (exp_a * 10) + (delta_if_win * 0.5) + (rival_impact * 5)
                
                if match_score > best_score:
                    best_score = match_score
                    best_match = {
                        "team_a": (stats_dict[team_a[0]]["name"], stats_dict[team_a[1]]["name"]),
                        "team_b": (stats_dict[team_b[0]]["name"], stats_dict[team_b[1]]["name"]),
                        "win_prob": exp_a,
                        "est_delta": delta_if_win
                    }
                    
        return best_match
