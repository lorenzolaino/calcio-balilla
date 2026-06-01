import unittest
from unittest.mock import MagicMock, patch, Mock
import sys
import os

# Mock Streamlit and setup environment
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
mock_st = Mock()
sys.modules['streamlit'] = mock_st

from models import DatabaseManager

class TestDeletionLogic(unittest.TestCase):

    @patch('models.engine')
    def test_delete_match_efficiency(self, mock_engine):
        """Verifies that deleting a match correctly restores player stats and trends with optimized calls."""
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn
        
        class MockRow:
            def __init__(self, data_dict):
                self._data = data_dict
                # For list(p) to work, we need an order. Let's use the dict order.
                self._items = list(data_dict.values())
            def __getattr__(self, name):
                if name in self._data: return self._data[name]
                raise AttributeError(name)
            def __getitem__(self, key):
                if isinstance(key, int): return self._items[key]
                return self._data[key]
            def __iter__(self):
                return iter(self._items)
            def _asdict(self):
                return self._data
            @property
            def _mapping(self):
                return self._data

        # Mock Match
        match_data = {
            "a1_id": 1, "a2_id": 2, "b1_id": 3, "b2_id": 4,
            "goals_a": 10, "goals_b": 5,
            "delta_a1": 5.0, "delta_a2": 4.0, "delta_b1": -4.0, "delta_b2": -3.0,
            "leaderboard_id": 1
        }
        mock_match = MockRow(match_data)

        # Mock Players
        players_data = [
            MockRow({"player_id": 1, "rating": 1005.0, "games": 1, "wins": 1, "losses": 0, "goal_diff": 5}),
            MockRow({"player_id": 2, "rating": 1004.0, "games": 1, "wins": 1, "losses": 0, "goal_diff": 5}),
            MockRow({"player_id": 3, "rating": 996.0, "games": 1, "wins": 0, "losses": 1, "goal_diff": -5}),
            MockRow({"player_id": 4, "rating": 997.0, "games": 1, "wins": 0, "losses": 1, "goal_diff": -5}),
        ]

        # Mock Trends
        trends_data = [
            MockRow({"pid": 1, "trend": "L W L"}),
            MockRow({"pid": 2, "trend": "W W"}),
            MockRow({"pid": 3, "trend": "L"}),
            MockRow({"pid": 4, "trend": "W L W L W"}),
        ]

        def side_effect(stmt, params=None):
            stmt_text = str(stmt).lower()
            if "select a1_id, a2_id" in stmt_text:
                res = MagicMock()
                res.fetchone.return_value = mock_match
                return res
            if "select player_id, rating, games" in stmt_text:
                res = MagicMock()
                res.fetchall.return_value = players_data
                return res
            if "select pid, string_agg" in stmt_text:
                res = MagicMock()
                res.fetchall.return_value = trends_data
                return res
            return MagicMock()

        mock_conn.execute.side_effect = side_effect

        # Execute deletion
        result = DatabaseManager.delete_match(123)

        self.assertTrue(result)

        # Verify Batch Update call
        update_calls = [call for call in mock_conn.execute.call_args_list if "update player_stats" in str(call[0][0]).lower()]
        self.assertEqual(len(update_calls), 1)
        
        updated_list = update_calls[0][0][1]
        self.assertEqual(len(updated_list), 4)

        # Check Player 1 restoration (A1)
        # rating: 1005.0 - 5.0 = 1000.0
        # games: 1 - 1 = 0
        # wins: 1 - 1 = 0
        # goal_diff: 5 - 5 = 0
        p1_update = next(p for p in updated_list if p["pid"] == 1)
        self.assertEqual(p1_update["r"], 1000.0)
        self.assertEqual(p1_update["g"], 0)
        self.assertEqual(p1_update["w"], 0)
        self.assertEqual(p1_update["gd"], 0)
        self.assertEqual(p1_update["t"], "L W L")

        # Check Player 3 restoration (B1)
        # rating: 996.0 - (-4.0) = 1000.0
        # games: 1 - 1 = 0
        # losses: 1 - 1 = 0
        # goal_diff: -5 - (-5) = 0
        p3_update = next(p for p in updated_list if p["pid"] == 3)
        self.assertEqual(p3_update["r"], 1000.0)
        self.assertEqual(p3_update["g"], 0)
        self.assertEqual(p3_update["l"], 0)
        self.assertEqual(p3_update["gd"], 0)
        self.assertEqual(p3_update["t"], "L")

        # Verify DELETE calls
        delete_history_calls = [call for call in mock_conn.execute.call_args_list if "delete from player_ratings_history" in str(call[0][0]).lower()]
        delete_match_calls = [call for call in mock_conn.execute.call_args_list if "delete from matches" in str(call[0][0]).lower()]
        
        self.assertEqual(len(delete_history_calls), 1)
        self.assertEqual(len(delete_match_calls), 1)

if __name__ == '__main__':
    unittest.main()
