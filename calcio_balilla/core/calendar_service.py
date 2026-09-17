import itertools
import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from db import engine as default_engine

import scoring
from calcio_balilla.core.domain import MatchSuggestion
from calcio_balilla.data.match_repository import MatchRepository
from calcio_balilla.data.player_repository import PlayerRepository
from calcio_balilla.data.season_repository import SeasonRepository


BALANCE_BAND_THRESHOLDS = (0.03, 0.06, 0.10, 0.15)
BALANCE_BAND_NAMES = ("A", "B", "C", "D", "E")
RECENCY_WEIGHTS = ((7, 4), (14, 3), (30, 2))
OLDER_MATCH_WEIGHT = 1
MATCHMAKING_TIMEZONE = ZoneInfo("Europe/Rome")


def canonical_pair(player_a: int, player_b: int) -> tuple[int, int]:
    return tuple(sorted((player_a, player_b)))


def canonical_match(team_a: tuple[int, int], team_b: tuple[int, int]):
    return tuple(sorted((canonical_pair(*team_a), canonical_pair(*team_b))))


def current_matchmaking_date() -> date:
    return datetime.now(MATCHMAKING_TIMEZONE).date()


def history_weight(match_date: datetime, reference_date: date) -> int:
    age_days = max(0, (reference_date - match_date.date()).days)
    for maximum_days, weight in RECENCY_WEIGHTS:
        if age_days <= maximum_days:
            return weight
    return OLDER_MATCH_WEIGHT


def balance_band(distance_from_50: float) -> tuple[int, str]:
    for index, threshold in enumerate(BALANCE_BAND_THRESHOLDS):
        if distance_from_50 <= threshold:
            return index, BALANCE_BAND_NAMES[index]
    return len(BALANCE_BAND_THRESHOLDS), BALANCE_BAND_NAMES[-1]


def preprocess_matchmaking_history(history, reference_date: date):
    partner_history = defaultdict(int)
    opponent_history = defaultdict(int)
    exact_match_history = defaultdict(int)
    for match in history:
        team_a = (match.a1_id, match.a2_id)
        team_b = (match.b1_id, match.b2_id)
        weight = history_weight(match.date, reference_date)
        partner_history[canonical_pair(*team_a)] += weight
        partner_history[canonical_pair(*team_b)] += weight
        for player_a in team_a:
            for player_b in team_b:
                opponent_history[canonical_pair(player_a, player_b)] += weight
        exact_match_history[canonical_match(team_a, team_b)] += weight
    return partner_history, opponent_history, exact_match_history


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

    def get_match_suggestions_for_player(
        self,
        target_player_id: int,
        available_player_ids: list,
        leaderboard_id: int,
        reference_date: date | None = None,
    ) -> list[MatchSuggestion]:
        reference_date = reference_date or current_matchmaking_date()
        active_season = self.season_repo.get_active_season(leaderboard_id)
        if active_season is None:
            return []
        all_stats = self.player_repo.get_active_players_ratings_games(leaderboard_id, active_season.id)
        stats_by_id = {player.id: player for player in all_stats}
        requested_ids = sorted(set(available_player_ids) | {target_player_id})
        player_ids = [player_id for player_id in requested_ids if player_id in stats_by_id]
        if target_player_id not in player_ids or len(player_ids) < 4:
            return []

        return self._get_match_suggestions(
            player_ids,
            leaderboard_id,
            active_season.id,
            stats_by_id,
            reference_date,
            target_player_id=target_player_id,
        )

    def get_match_suggestions(
        self,
        available_player_ids: list,
        leaderboard_id: int,
        reference_date: date | None = None,
    ) -> list[MatchSuggestion]:
        """Return the three best matches among all selected players."""
        reference_date = reference_date or current_matchmaking_date()
        active_season = self.season_repo.get_active_season(leaderboard_id)
        if active_season is None:
            return []
        all_stats = self.player_repo.get_active_players_ratings_games(leaderboard_id, active_season.id)
        stats_by_id = {player.id: player for player in all_stats}
        player_ids = [player_id for player_id in sorted(set(available_player_ids)) if player_id in stats_by_id]
        if len(player_ids) < 4:
            return []

        return self._get_match_suggestions(player_ids, leaderboard_id, active_season.id, stats_by_id, reference_date)

    def _get_match_suggestions(
        self,
        player_ids,
        leaderboard_id,
        season_id,
        stats_by_id,
        reference_date,
        target_player_id=None,
    ):
        history = self.match_repo.get_matchmaking_history(
            leaderboard_id, season_id, tuple(player_ids)
        )
        partner_history, opponent_history, exact_match_history = preprocess_matchmaking_history(
            history, reference_date
        )
        candidates = []
        if target_player_id is not None:
            player_groups = (
                (target_player_id, *combo)
                for combo in itertools.combinations(
                    [player_id for player_id in player_ids if player_id != target_player_id], 3
                )
            )
        else:
            player_groups = itertools.combinations(player_ids, 4)

        for group in player_groups:
            player_a, player_b, player_c, player_d = group
            team_options = (
                ((player_a, player_b), (player_c, player_d)),
                ((player_a, player_c), (player_b, player_d)),
                ((player_a, player_d), (player_b, player_c)),
            )
            for team_a, team_b in team_options:
                rating_a = sum(stats_by_id[player_id].rating for player_id in team_a) / 2.0
                rating_b = sum(stats_by_id[player_id].rating for player_id in team_b) / 2.0
                win_probability = scoring.expected_score(rating_a, rating_b)
                distance = abs(win_probability - 0.5)
                band_index, band_name = balance_band(distance)
                exact_penalty = exact_match_history[canonical_match(team_a, team_b)]
                partner_penalty = sum(partner_history[canonical_pair(*team)] for team in (team_a, team_b))
                opponent_penalty = sum(
                    opponent_history[canonical_pair(player_a, player_b)]
                    for player_a in team_a for player_b in team_b
                )
                ranking_key = (
                    band_index, exact_penalty, partner_penalty, opponent_penalty, distance,
                    canonical_match(team_a, team_b), canonical_pair(*team_a),
                )
                suggestion = MatchSuggestion(
                    team_a=tuple(stats_by_id[player_id].name for player_id in team_a),
                    team_b=tuple(stats_by_id[player_id].name for player_id in team_b),
                    win_probability=win_probability,
                    balance_band=band_name,
                    exact_match_penalty=exact_penalty,
                    partner_penalty=partner_penalty,
                    opponent_penalty=opponent_penalty,
                    team_a_ids=team_a,
                    team_b_ids=team_b,
                )
                candidates.append((ranking_key, suggestion))
        candidates.sort(key=lambda item: item[0])
        return self._diversified_top_three(candidates)

    @staticmethod
    def _diversified_top_three(candidates):
        if not candidates:
            return []
        selected = [candidates[0][1]]
        used_sets = {frozenset(selected[0].team_a_ids + selected[0].team_b_ids)}
        for _, suggestion in candidates[1:]:
            player_set = frozenset(suggestion.team_a_ids + suggestion.team_b_ids)
            if player_set not in used_sets:
                selected.append(suggestion)
                used_sets.add(player_set)
                if len(selected) == 3:
                    return selected
        for _, suggestion in candidates[1:]:
            if suggestion not in selected:
                selected.append(suggestion)
                if len(selected) == 3:
                    break
        return selected

    def get_best_match_for_player(self, target_player_id: int, available_player_ids: list, leaderboard_id: int):
        suggestions = self.get_match_suggestions_for_player(
            target_player_id, available_player_ids, leaderboard_id
        )
        return suggestions[0] if suggestions else None
