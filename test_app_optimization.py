import unittest
from unittest.mock import MagicMock, patch, Mock
import sys
import os

# Mock Streamlit and setup environment before importing app
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
mock_st = Mock()
sys.modules['streamlit'] = mock_st

import app

class TestApp(unittest.TestCase):

    @patch('app.engine')
    def test_update_ratings_for_match_batches(self, mock_engine):
        # Setup mock connection and engine
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn
        
        # Mock responses for player fetching
        class Row(tuple):
            @property
            def name(self): return self[1]

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
        app.update_ratings_for_match('A1', 'A2', 'B1', 'B2', 10, 8)
        
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
        # In our mock setup, decorators are called during import
        self.assertTrue(mock_st.cache_data.called)
        
        # Verify clear is called in api_add_player
        with patch('app.engine'):
            app.api_add_player("NewPlayer")
            mock_st.cache_data.clear.assert_called()

if __name__ == '__main__':
    unittest.main()
