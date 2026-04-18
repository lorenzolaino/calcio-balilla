import unittest
from unittest.mock import MagicMock, patch, Mock
import sys
import os

# Mock Streamlit and setup environment
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
mock_st = Mock()
sys.modules['streamlit'] = mock_st

from models import DatabaseManager

class TestScoringLogic(unittest.TestCase):

    def test_k_factor_continuous(self):
        """Verifies that the K-factor decreases smoothly as games increase."""
        # 0 games: 10 + 20/1 = 30
        self.assertAlmostEqual(DatabaseManager._get_k_factor(0), 30.0)
        # 40 games: 10 + 20/2 = 20
        self.assertAlmostEqual(DatabaseManager._get_k_factor(40), 20.0)
        # 200 games: 10 + 20/(1+5) = 10 + 3.33 = 13.33
        self.assertAlmostEqual(DatabaseManager._get_k_factor(200), 13.3333333)
        # Large number of games: should approach 10
        self.assertAlmostEqual(DatabaseManager._get_k_factor(100000), 10.0, places=1)

    @patch('models.engine')
    def test_individual_scoring_and_farming(self, mock_engine):
        """Verifies that individual K-factors and anti-farming multipliers are applied."""
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn
        
        class Row:
            def __init__(self, data):
                self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend = data
            def __getitem__(self, i):
                return [self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend][i]
            def __iter__(self):
                return iter([self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend])

        players = {
            'A1': Row((1, 'A1', 1200.0, 10, 5, 5, 0, '')),
            'A2': Row((2, 'A2', 1100.0, 40, 20, 20, 0, '')),
            'B1': Row((3, 'B1', 1000.0, 100, 50, 50, 0, '')),
            'B2': Row((4, 'B2', 900.0, 200, 100, 100, 0, '')),
        }

        def side_effect(stmt, params=None):
            stmt_text = str(stmt).lower()
            if "select max(rating), min(rating)" in stmt_text:
                res = MagicMock()
                res.fetchone.return_value = (1200.0, 900.0) # Spread = 300, Threshold = 150
                return res
            if "select id, name, rating" in stmt_text:
                res = MagicMock()
                names = params['names']
                res.fetchall.return_value = [players[name] for name in names]
                return res
            if "insert into matches" in stmt_text:
                res = MagicMock()
                res.scalar.return_value = 1
                return res
            return MagicMock()

        mock_conn.execute.side_effect = side_effect

        # CASE 1: Favored team wins
        DatabaseManager.record_match('A1', 'A2', 'B1', 'B2', 10, 5)

        update_calls = [call for call in mock_conn.execute.call_args_list if "update players" in str(call[0][0]).lower()]
        updated_data = update_calls[-1][0][1]
        
        delta_a1 = updated_data[0]['r'] - 1200.0
        delta_a2 = updated_data[1]['r'] - 1100.0
        
        # A1 has fewer games, higher K, so delta_a1 > delta_a2
        self.assertTrue(delta_a1 > delta_a2)
        # Farming multiplier (0.5x) is applied
        self.assertAlmostEqual(delta_a1, 4.1, places=1)

    @patch('models.engine')
    def test_corner_cases(self, mock_engine):
        """Verifies margin caps and invalid match rules."""
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn

        class Row:
            def __init__(self, data):
                self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend = data
            def __getitem__(self, i):
                return [self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend][i]
            def __iter__(self):
                return iter([self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend])

        def get_side_effect(players_dict, max_min=(1000.0, 1000.0)):
            def side_effect(stmt, params=None):
                stmt_text = str(stmt).lower()
                if "select max(rating), min(rating)" in stmt_text:
                    res = MagicMock()
                    res.fetchone.return_value = max_min
                    return res
                if "select id, name, rating" in stmt_text:
                    res = MagicMock()
                    names = params['names']
                    res.fetchall.return_value = [players_dict[name] for name in names if name in players_dict]
                    return res
                if "insert into matches" in stmt_text:
                    res = MagicMock()
                    res.scalar.return_value = 1
                    return res
                return MagicMock()
            return side_effect

        players_standard = {
            'A1': Row((1, 'A1', 1000.0, 100, 50, 50, 0, '')),
            'A2': Row((2, 'A2', 1000.0, 100, 50, 50, 0, '')),
            'B1': Row((3, 'B1', 1000.0, 100, 50, 50, 0, '')),
            'B2': Row((4, 'B2', 1000.0, 100, 50, 50, 0, '')),
        }
        
        # 1. Large Margin (10 goals) capped at 1.8x
        mock_conn.execute.side_effect = get_side_effect(players_standard)
        DatabaseManager.record_match('A1', 'A2', 'B1', 'B2', 10, 0)
        update_calls = [call for call in mock_conn.execute.call_args_list if "update players" in str(call[0][0]).lower()]
        delta = update_calls[-1][0][1][0]['r'] - 1000.0
        self.assertAlmostEqual(delta, 14.1, places=1)

        # 2. Invalid Matches (Draws)
        with self.assertRaises(ValueError):
            DatabaseManager.record_match('A1', 'A2', 'B1', 'B2', 10, 10)

if __name__ == '__main__':
    unittest.main()
