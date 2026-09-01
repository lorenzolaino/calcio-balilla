import os
import sys
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock


os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
sys.modules.setdefault("streamlit", MagicMock())

from calcio_balilla.core.calendar_service import (
    CalendarService,
    balance_band,
    canonical_match,
    canonical_pair,
    history_weight,
    preprocess_matchmaking_history,
)
from calcio_balilla.core.domain import MatchmakingHistoryEntry, PlayerMatchStats, Season
from calcio_balilla.data.match_repository import MatchRepository


REFERENCE_TIME = datetime(2026, 9, 1, 12, 0, 0)
REFERENCE_DATE = REFERENCE_TIME.date()


def player(player_id, rating=1000):
    return PlayerMatchStats(player_id, f"P{player_id}", rating, 0, 0, 0, 0, "")


def historical(days_ago, a1, a2, b1, b2):
    return MatchmakingHistoryEntry(
        REFERENCE_TIME - timedelta(days=days_ago), a1, a2, b1, b2
    )


def make_service(players, history=()):
    player_repo = MagicMock()
    player_repo.get_active_players_ratings_games.return_value = players
    match_repo = MagicMock()
    match_repo.get_matchmaking_history.return_value = list(history)
    season_repo = MagicMock()
    season_repo.get_active_season.return_value = Season(7, 3, 1, "Season 1", True)
    return CalendarService(
        engine=MagicMock(), player_repo=player_repo, match_repo=match_repo, season_repo=season_repo
    ), player_repo, match_repo, season_repo


class TestHistoryHelpers(unittest.TestCase):
    def test_balance_band_boundaries(self):
        self.assertEqual(balance_band(0.03)[1], "A")
        self.assertEqual(balance_band(0.04)[1], "B")
        self.assertEqual(balance_band(0.08)[1], "C")
        self.assertEqual(balance_band(0.12)[1], "D")
        self.assertEqual(balance_band(0.20)[1], "E")

    def test_canonical_keys_ignore_player_and_team_order(self):
        self.assertEqual(canonical_pair(2, 1), canonical_pair(1, 2))
        expected = canonical_match((1, 2), (3, 4))
        self.assertEqual(expected, canonical_match((2, 1), (3, 4)))
        self.assertEqual(expected, canonical_match((4, 3), (2, 1)))

    def test_recency_weights(self):
        self.assertEqual(history_weight(REFERENCE_TIME - timedelta(days=2), REFERENCE_DATE), 4)
        self.assertEqual(history_weight(REFERENCE_TIME - timedelta(days=10), REFERENCE_DATE), 3)
        self.assertEqual(history_weight(REFERENCE_TIME - timedelta(days=20), REFERENCE_DATE), 2)
        self.assertEqual(history_weight(REFERENCE_TIME - timedelta(days=40), REFERENCE_DATE), 1)

    def test_recency_changes_at_calendar_day_boundary(self):
        match_date = REFERENCE_TIME - timedelta(days=7)
        self.assertEqual(history_weight(match_date, REFERENCE_DATE), 4)
        self.assertEqual(history_weight(match_date, REFERENCE_DATE + timedelta(days=1)), 3)

    def test_history_accumulates_both_partners_all_opponents_and_exact_matches(self):
        history = [historical(2, 1, 2, 3, 4), historical(10, 2, 1, 4, 3)]
        partners, opponents, exact = preprocess_matchmaking_history(history, REFERENCE_DATE)
        self.assertEqual(partners[(1, 2)], 7)
        self.assertEqual(partners[(3, 4)], 7)
        for pair in ((1, 3), (1, 4), (2, 3), (2, 4)):
            self.assertEqual(opponents[pair], 7)
        self.assertEqual(exact[canonical_match((1, 2), (3, 4))], 7)


class TestMatchmakingService(unittest.TestCase):
    def test_target_added_duplicates_removed_and_less_than_four_returns_empty(self):
        service, _, match_repo, _ = make_service([player(i) for i in range(1, 4)])
        result = service.get_match_suggestions_for_player(1, [2, 2, 3], 3, REFERENCE_DATE)
        self.assertEqual(result, [])
        match_repo.get_matchmaking_history.assert_not_called()

    def test_more_than_ten_players_are_considered(self):
        players = [player(1, 1000)] + [player(i, 2000) for i in range(2, 12)] + [player(12, 1000)]
        service, _, _, _ = make_service(players)
        suggestions = service.get_match_suggestions_for_player(1, list(range(2, 13)), 3, REFERENCE_DATE)
        recommended_ids = suggestions[0].team_a_ids + suggestions[0].team_b_ids
        self.assertIn(12, recommended_ids)
        self.assertEqual(suggestions[0].balance_band, "A")

    def test_worse_balance_band_cannot_be_overridden_by_rotation(self):
        players = [player(1, 1000), player(2, 1000), player(3, 1000), player(4, 1000), player(5, 1200)]
        history = [historical(2, 1, 2, 3, 4)] * 4
        service, _, _, _ = make_service(players, history)
        best = service.get_match_suggestions_for_player(1, [1, 2, 3, 4, 5], 3, REFERENCE_DATE)[0]
        self.assertEqual(best.balance_band, "A")

    def test_exact_rematch_is_penalized_including_swapped_teams(self):
        service, _, _, _ = make_service(
            [player(i) for i in range(1, 5)], [historical(2, 4, 3, 2, 1)]
        )
        best = service.get_match_suggestions_for_player(1, [1, 2, 3, 4], 3, REFERENCE_DATE)[0]
        self.assertNotEqual(canonical_match(best.team_a_ids, best.team_b_ids), canonical_match((1, 2), (3, 4)))

    def test_partner_and_opponent_penalties_use_all_four_players(self):
        service, _, _, _ = make_service(
            [player(i) for i in range(1, 5)], [historical(2, 1, 2, 3, 4)]
        )
        suggestions = service.get_match_suggestions_for_player(1, [1, 2, 3, 4], 3, REFERENCE_DATE)
        repeated = next(s for s in suggestions if canonical_match(s.team_a_ids, s.team_b_ids) == canonical_match((1, 2), (3, 4)))
        self.assertEqual(repeated.partner_penalty, 8)
        self.assertEqual(repeated.opponent_penalty, 16)

    def test_empty_history_is_deterministic_and_closest_balance_wins(self):
        players = [player(1, 1000), player(2, 1000), player(3, 1100), player(4, 900), player(5, 1300)]
        service, _, _, _ = make_service(players)
        first = service.get_match_suggestions_for_player(1, [5, 4, 3, 2, 1], 3, REFERENCE_DATE)
        second = service.get_match_suggestions_for_player(1, [2, 3, 4, 5], 3, REFERENCE_DATE)
        self.assertEqual(first, second)
        self.assertLessEqual(abs(first[0].win_probability - 0.5), 0.03)

    def test_same_band_and_history_prefers_closest_to_fifty(self):
        service, _, _, _ = make_service([
            player(1, 1000), player(2, 1000), player(3, 1100), player(4, 900)
        ])
        best = service.get_match_suggestions_for_player(1, [1, 2, 3, 4], 3, REFERENCE_DATE)[0]
        self.assertEqual(best.win_probability, 0.5)

    def test_top_three_diversifies_sets_and_four_player_fallback(self):
        service, _, _, _ = make_service([player(i) for i in range(1, 7)])
        suggestions = service.get_match_suggestions_for_player(1, list(range(1, 7)), 3, REFERENCE_DATE)
        self.assertEqual(len(suggestions), 3)
        self.assertEqual(len({frozenset(s.team_a_ids + s.team_b_ids) for s in suggestions}), 3)

        service, _, _, _ = make_service([player(i) for i in range(1, 5)])
        fallback = service.get_match_suggestions_for_player(1, [1, 2, 3, 4], 3, REFERENCE_DATE)
        self.assertEqual(len(fallback), 3)
        self.assertEqual(len({frozenset(s.team_a_ids + s.team_b_ids) for s in fallback}), 1)

    def test_repository_read_budget_is_constant_for_four_and_twenty_five_players(self):
        counts = []
        for size in (4, 25):
            service, player_repo, match_repo, season_repo = make_service(
                [player(i) for i in range(1, size + 1)]
            )
            service.get_match_suggestions_for_player(1, list(range(1, size + 1)), 3, REFERENCE_DATE)
            counts.append((
                season_repo.get_active_season.call_count,
                player_repo.get_active_players_ratings_games.call_count,
                match_repo.get_matchmaking_history.call_count,
            ))
        self.assertEqual(counts, [(1, 1, 1), (1, 1, 1)])

    def test_history_fetch_receives_current_leaderboard_season_and_relevant_ids(self):
        service, _, match_repo, _ = make_service([player(i) for i in range(1, 5)])
        service.get_match_suggestions_for_player(1, [1, 2, 3, 4], 99, REFERENCE_DATE)
        match_repo.get_matchmaking_history.assert_called_once_with(99, 7, (1, 2, 3, 4))


class TestMatchmakingHistoryRepository(unittest.TestCase):
    def test_single_query_is_scoped_to_leaderboard_season_and_minimal_columns(self):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = []
        get_connection = MagicMock()
        get_connection.return_value.__enter__.return_value = connection
        repository = MatchRepository(engine=MagicMock(), get_connection=get_connection)

        result = repository.get_matchmaking_history(9, 12, (1, 2, 3, 4))

        self.assertEqual(result, [])
        connection.execute.assert_called_once()
        query, params = connection.execute.call_args.args
        sql = str(query)
        self.assertIn("SELECT date, a1_id, a2_id, b1_id, b2_id", sql)
        self.assertIn("leaderboard_id = :l_id", sql)
        self.assertIn("season_id = :season_id", sql)
        self.assertNotIn("JOIN", sql)
        self.assertEqual(params["l_id"], 9)
        self.assertEqual(params["season_id"], 12)


if __name__ == "__main__":
    unittest.main()
