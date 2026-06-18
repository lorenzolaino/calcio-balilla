import unittest
from unittest.mock import MagicMock, patch, Mock
import sys
import os

# Mock Streamlit BEFORE importing DatabaseManager
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
mock_st = MagicMock()
# Mock the cache decorator to return the function itself and support .clear()
def mock_cache(func): return func
mock_st.cache_data = mock_cache
mock_st.cache_data.clear = MagicMock()
sys.modules['streamlit'] = mock_st

from models import DatabaseManager

def legacy_calculate_match_updates(players, goals_a, goals_b, rating_diff_threshold):
    a1, a2, b1, b2 = [list(player) for player in players]
    margin = abs(goals_a - goals_b)

    r_a = (a1[2] + a2[2]) / 2.0
    r_b = (b1[2] + b2[2]) / 2.0
    e_a = DatabaseManager._expected_score(r_a, r_b)
    s_a = 1.0 if goals_a > goals_b else 0.0
    m = DatabaseManager._margin_multiplier(margin)

    multiplier = 1.0
    team_diff = r_a - r_b
    is_a_favored = team_diff > 0

    if abs(team_diff) > rating_diff_threshold:
        if (is_a_favored and s_a == 1.0) or (not is_a_favored and s_a == 0.0):
            multiplier = 0.5
        else:
            multiplier = 1.5

    delta_a1 = round(DatabaseManager._get_k_factor(a1[3]) * m * multiplier * (s_a - e_a), 1)
    delta_a2 = round(DatabaseManager._get_k_factor(a2[3]) * m * multiplier * (s_a - e_a), 1)
    delta_b1 = round(DatabaseManager._get_k_factor(b1[3]) * m * multiplier * ((1 - s_a) - (1 - e_a)), 1)
    delta_b2 = round(DatabaseManager._get_k_factor(b2[3]) * m * multiplier * ((1 - s_a) - (1 - e_a)), 1)

    a1[2] += delta_a1; a2[2] += delta_a2
    b1[2] += delta_b1; b2[2] += delta_b2

    for p in [a1, a2, b1, b2]:
        p[3] += 1

    if s_a == 1:
        a1[4] += 1; a2[4] += 1; b1[5] += 1; b2[5] += 1
    else:
        b1[4] += 1; b2[4] += 1; a1[5] += 1; a2[5] += 1

    gd_a = goals_a - goals_b
    a1[6] += gd_a; a2[6] += gd_a; b1[6] -= gd_a; b2[6] -= gd_a

    for i, p in enumerate([a1, a2, b1, b2]):
        is_win = (i < 2 and s_a == 1) or (i >= 2 and s_a == 0)
        res_char = 'W' if is_win else 'L'

        current_trend = p[7] if p[7] else ""
        parts = current_trend.split()
        new_parts = ([res_char] + parts)[:5]
        p[7] = " ".join(new_parts)

    return [a1, a2, b1, b2], (delta_a1, delta_a2, delta_b1, delta_b2)

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

    def test_calculate_match_updates_is_pure_and_updates_stats(self):
        """Verifies the Elo calculation without database mocks."""
        players = [
            [1, 'A1', 1000.0, 0, 0, 0, 0, 'W L'],
            [2, 'A2', 1000.0, 0, 0, 0, 0, ''],
            [3, 'B1', 1000.0, 0, 0, 0, 0, 'L W'],
            [4, 'B2', 1000.0, 0, 0, 0, 0, ''],
        ]

        updated, deltas = DatabaseManager._calculate_match_updates(players, 10, 8, 0.0)

        self.assertEqual(deltas, (15.0, 15.0, -15.0, -15.0))
        self.assertEqual([p[3] for p in updated], [1, 1, 1, 1])
        self.assertEqual([p[4] for p in updated], [1, 1, 0, 0])
        self.assertEqual([p[5] for p in updated], [0, 0, 1, 1])
        self.assertEqual([p[6] for p in updated], [2, 2, -2, -2])
        self.assertEqual([p[7] for p in updated], ['W W L', 'W', 'L L W', 'L'])
        self.assertEqual(players[0][2], 1000.0)

    def test_calculate_match_updates_matches_legacy_inline_logic(self):
        """Locks the refactor against the previous inline scoring implementation."""
        scenarios = [
            (
                [
                    [1, 'A1', 1200.0, 10, 5, 5, 2, 'W L W'],
                    [2, 'A2', 1100.0, 40, 20, 20, -1, 'L W'],
                    [3, 'B1', 1000.0, 100, 50, 50, 3, 'W W L'],
                    [4, 'B2', 900.0, 200, 100, 100, -4, 'L L W'],
                ],
                10,
                5,
                150.0,
            ),
            (
                [
                    [1, 'A1', 1200.0, 10, 5, 5, 2, 'W L W'],
                    [2, 'A2', 1100.0, 40, 20, 20, -1, 'L W'],
                    [3, 'B1', 1000.0, 100, 50, 50, 3, 'W W L'],
                    [4, 'B2', 900.0, 200, 100, 100, -4, 'L L W'],
                ],
                5,
                10,
                150.0,
            ),
            (
                [
                    [1, 'A1', 1000.0, 0, 0, 0, 0, ''],
                    [2, 'A2', 1000.0, 39, 20, 19, 1, 'W W W W W'],
                    [3, 'B1', 1000.0, 40, 19, 21, -1, 'L L L L L'],
                    [4, 'B2', 1000.0, 200, 90, 110, -8, 'W L W L W'],
                ],
                10,
                0,
                0.0,
            ),
        ]

        for players, goals_a, goals_b, threshold in scenarios:
            with self.subTest(goals_a=goals_a, goals_b=goals_b, threshold=threshold):
                self.assertEqual(
                    DatabaseManager._calculate_match_updates(players, goals_a, goals_b, threshold),
                    legacy_calculate_match_updates(players, goals_a, goals_b, threshold),
                )

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
            if "select id from players" in stmt_text:
                res = MagicMock()
                name = params['name']
                res.fetchone.return_value = (players[name].id,)
                return res
            if "select 1 from player_stats" in stmt_text:
                res = MagicMock()
                res.fetchone.return_value = (1,)
                return res
            if "select p.id, p.name, ps.rating" in stmt_text:
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
        DatabaseManager.record_match('A1', 'A2', 'B1', 'B2', 10, 5, 1)

        update_calls = [call for call in mock_conn.execute.call_args_list if "update player_stats" in str(call[0][0]).lower()]
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
                if "select id from players" in stmt_text:
                    res = MagicMock()
                    name = params['name']
                    res.fetchone.return_value = (players_dict[name].id,)
                    return res
                if "select 1 from player_stats" in stmt_text:
                    res = MagicMock()
                    res.fetchone.return_value = (1,)
                    return res
                if "select p.id, p.name, ps.rating" in stmt_text:
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
        DatabaseManager.record_match('A1', 'A2', 'B1', 'B2', 10, 0, 1)
        update_calls = [call for call in mock_conn.execute.call_args_list if "update player_stats" in str(call[0][0]).lower()]
        delta = update_calls[-1][0][1][0]['r'] - 1000.0
        self.assertAlmostEqual(delta, 14.1, places=1)

        # 2. Invalid Matches (Draws)
        with self.assertRaises(ValueError):
            DatabaseManager.record_match('A1', 'A2', 'B1', 'B2', 10, 10, 1)

if __name__ == '__main__':
    unittest.main()
