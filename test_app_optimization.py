import unittest
from unittest.mock import MagicMock, patch, Mock
import sys
import os

# Mock Streamlit and setup environment before importing app
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
mock_st = Mock()
sys.modules['streamlit'] = mock_st

import app
from models import DatabaseManager

class TestApp(unittest.TestCase):

    @patch('models.engine')
    def test_record_match_batches(self, mock_engine):
        # Setup mock connection and engine
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn
        
        # Mock responses for player fetching
        class Row:
            def __init__(self, data):
                self.id = data[0]
                self.name = data[1]
                self.rating = data[2]
                self.games = data[3]
                self.wins = data[4]
                self.losses = data[5]
                self.goal_diff = data[6]
            def __getitem__(self, i):
                return [self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff][i]

        mock_player_rows = [
            Row((1, 'A1', 1000, 0, 0, 0, 0)),
            Row((2, 'A2', 1000, 0, 0, 0, 0)),
            Row((3, 'B1', 1000, 0, 0, 0, 0)),
            Row((4, 'B2', 1000, 0, 0, 0, 0)),
        ]
        
        def side_effect(stmt, params=None):
            stmt_text = str(stmt).lower()
            if "select id, name, rating" in stmt_text:
                res = MagicMock()
                res.fetchall.return_value = mock_player_rows
                return res
            if "insert into matches" in stmt_text:
                res = MagicMock()
                res.scalar.return_value = 100 # match_id
                return res
            return MagicMock()

        mock_conn.execute.side_effect = side_effect
        
        # Run function
        DatabaseManager.record_match('A1', 'A2', 'B1', 'B2', 10, 8)
        
        # Verify calls
        # Expected: 1 fetch, 1 update (batch), 1 match insert, 1 history insert (batch)
        self.assertEqual(mock_conn.execute.call_count, 4)
        mock_st.cache_data.clear.assert_called()
        
        # Verify batching in updates
        update_call = [call for call in mock_conn.execute.call_args_list if "UPDATE players" in str(call[0][0])][0]
        self.assertIsInstance(update_call[0][1], list)
        self.assertEqual(len(update_call[0][1]), 4)

    def test_caching_applied(self):
        # Check if functions were passed through st.cache_data
        # We check some representative functions in DatabaseManager
        self.assertTrue(hasattr(DatabaseManager.get_leaderboard, "__wrapped__") or mock_st.cache_data.called)
        
        # Verify clear is called in add_player
        with patch('models.engine'):
            DatabaseManager.add_player("NewPlayer")
            mock_st.cache_data.clear.assert_called()

if __name__ == '__main__':
    unittest.main()
