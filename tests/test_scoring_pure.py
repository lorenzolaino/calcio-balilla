import unittest
from datetime import datetime, timedelta

import scoring
from calcio_balilla.core.domain import MatchPlayerState


class TestPureScoringModule(unittest.TestCase):
    def test_calculate_match_updates_for_states_returns_updated_states(self):
        players = [
            MatchPlayerState(id=1, name="A1", rating=1000.0, games=0, wins=0, losses=0, goal_diff=0, trend="W L"),
            MatchPlayerState(id=2, name="A2", rating=1000.0, games=0, wins=0, losses=0, goal_diff=0, trend=""),
            MatchPlayerState(id=3, name="B1", rating=1000.0, games=0, wins=0, losses=0, goal_diff=0, trend="L W"),
            MatchPlayerState(id=4, name="B2", rating=1000.0, games=0, wins=0, losses=0, goal_diff=0, trend=""),
        ]

        updated, deltas = scoring.calculate_match_updates_for_states(players, 10, 8, 0.0)

        self.assertEqual(deltas, (15.0, 15.0, -15.0, -15.0))
        self.assertEqual([player.games for player in updated], [1, 1, 1, 1])
        self.assertEqual([player.wins for player in updated], [1, 1, 0, 0])
        self.assertEqual([player.losses for player in updated], [0, 0, 1, 1])
        self.assertEqual([player.goal_diff for player in updated], [2, 2, -2, -2])
        self.assertEqual([player.trend for player in updated], ["W W L", "W", "L L W", "L"])
        self.assertEqual(players[0].rating, 1000.0)

    def test_recent_duplicate_cutoff_uses_window_seconds(self):
        now = datetime(2026, 8, 17, 12, 0, 0)
        cutoff = scoring.recent_duplicate_cutoff(now)

        self.assertEqual(
            cutoff,
            now - timedelta(seconds=scoring.RECENT_DUPLICATE_MATCH_WINDOW_SECONDS),
        )

    def test_is_same_match_handles_swapped_sides(self):
        candidate = {
            "a1_id": 1,
            "a2_id": 2,
            "b1_id": 3,
            "b2_id": 4,
            "goals_a": 10,
            "goals_b": 8,
        }
        existing = {
            "a1_id": 3,
            "a2_id": 4,
            "b1_id": 1,
            "b2_id": 2,
            "goals_a": 8,
            "goals_b": 10,
        }

        self.assertTrue(scoring.is_same_match(candidate, existing))


if __name__ == "__main__":
    unittest.main()
