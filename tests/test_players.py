import unittest
from unittest.mock import MagicMock, patch, Mock
import sys
import os
import importlib

# 1. Setup Environment
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"

# 2. Mock Streamlit BEFORE anything else
mock_st = MagicMock()
# Mock the cache decorator to be a simple identity function
def mock_cache(func): return func
mock_st.cache_data = mock_cache
mock_st.cache_data.clear = MagicMock()
sys.modules['streamlit'] = mock_st

# 3. Force reload of models to ensure decorators use the mock
import models
importlib.reload(models)
from models import DatabaseManager

class TestPlayerManagement(unittest.TestCase):

    @patch('models.engine')
    def test_add_player_reactivation(self, mock_engine):
        """Verifies that adding a player uses the reactivation logic (ON CONFLICT)."""
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn
        
        DatabaseManager.add_player("John Doe", 1)
        
        # Verify SQL contains DO UPDATE SET is_active = TRUE in one of the calls
        all_sql = " ".join([str(call[0][0]).lower() for call in mock_conn.execute.call_args_list])
        self.assertIn("on conflict", all_sql)
        self.assertIn("do update set is_active = true", all_sql)

    @patch('models.get_connection')
    def test_leaderboard_filtering(self, mock_get_conn):
        """Verifies that the leaderboard only fetches active players."""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        
        # Bypass any potentially cached version
        DatabaseManager.get_leaderboard(1)
        
        self.assertTrue(mock_conn.execute.called)
        args, kwargs = mock_conn.execute.call_args
        sql = str(args[0]).lower()
        self.assertIn("where p.is_active = true", sql)
        self.assertIn("join player_stats", sql)

    @patch('models.get_connection')
    def test_player_names_filtering(self, mock_get_conn):
        """Verifies that player names for selection only include active players."""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        
        DatabaseManager.get_player_names(1)
        
        self.assertTrue(mock_conn.execute.called)
        args, kwargs = mock_conn.execute.call_args
        sql = str(args[0]).lower()
        self.assertIn("where p.is_active = true", sql)
        self.assertIn("join player_stats", sql)

    @patch('models.engine')
    def test_toggle_player_status(self, mock_engine):
        """Verifies the toggle status logic."""
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn
        
        DatabaseManager.toggle_player_status(1, False)
        
        args, kwargs = mock_conn.execute.call_args
        params = args[1]
        self.assertEqual(params["status"], False)
        self.assertEqual(params["pid"], 1)

if __name__ == '__main__':
    unittest.main()
