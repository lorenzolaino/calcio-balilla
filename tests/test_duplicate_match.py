import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
mock_st = MagicMock()


def mock_cache(func):
    return func


mock_st.cache_data = mock_cache
mock_st.cache_data.clear = MagicMock()
sys.modules["streamlit"] = mock_st

from models import DatabaseManager


class PlayerRow:
    def __init__(self, data):
        self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend = data

    def __getitem__(self, i):
        return [self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend][i]

    def __iter__(self):
        return iter([self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend])


class MatchRow:
    def __init__(self, data):
        self._data = data

    @property
    def _mapping(self):
        return self._data


class TestDuplicateMatchProtection(unittest.TestCase):
    def test_same_match_variants_are_detected(self):
        candidate = {
            "a1_id": 1,
            "a2_id": 2,
            "b1_id": 3,
            "b2_id": 4,
            "goals_a": 10,
            "goals_b": 8,
        }

        cases = [
            {"a1_id": 1, "a2_id": 2, "b1_id": 3, "b2_id": 4, "goals_a": 10, "goals_b": 8},
            {"a1_id": 2, "a2_id": 1, "b1_id": 4, "b2_id": 3, "goals_a": 10, "goals_b": 8},
            {"a1_id": 3, "a2_id": 4, "b1_id": 1, "b2_id": 2, "goals_a": 8, "goals_b": 10},
            {"a1_id": 4, "a2_id": 3, "b1_id": 2, "b2_id": 1, "goals_a": 8, "goals_b": 10},
        ]

        for existing in cases:
            with self.subTest(existing=existing):
                self.assertTrue(DatabaseManager._is_same_match(candidate, existing))

    def test_different_match_variants_are_not_detected(self):
        candidate = {
            "a1_id": 1,
            "a2_id": 2,
            "b1_id": 3,
            "b2_id": 4,
            "goals_a": 10,
            "goals_b": 8,
        }

        cases = [
            {"a1_id": 1, "a2_id": 2, "b1_id": 3, "b2_id": 4, "goals_a": 10, "goals_b": 7},
            {"a1_id": 1, "a2_id": 5, "b1_id": 3, "b2_id": 4, "goals_a": 10, "goals_b": 8},
            {"a1_id": 3, "a2_id": 4, "b1_id": 1, "b2_id": 2, "goals_a": 10, "goals_b": 8},
        ]

        for existing in cases:
            with self.subTest(existing=existing):
                self.assertFalse(DatabaseManager._is_same_match(candidate, existing))

    def test_recent_duplicate_query_uses_leaderboard_and_cutoff(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        now = datetime(2026, 6, 18, 12, 0, 0)

        with patch("models.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            result = DatabaseManager._get_recent_duplicate_match_id(conn, 1, 2, 3, 4, 10, 8, 7)

        self.assertIsNone(result)
        _, params = conn.execute.call_args[0]
        self.assertEqual(params["l_id"], 7)
        self.assertEqual(
            params["cutoff"],
            now - timedelta(seconds=DatabaseManager.RECENT_DUPLICATE_MATCH_WINDOW_SECONDS),
        )

    def test_recent_duplicate_returns_matching_id(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            MatchRow({"id": 99, "a1_id": 2, "a2_id": 1, "b1_id": 4, "b2_id": 3, "goals_a": 10, "goals_b": 8})
        ]

        result = DatabaseManager._get_recent_duplicate_match_id(conn, 1, 2, 3, 4, 10, 8, 7)

        self.assertEqual(result, 99)

    @patch("models.engine")
    def test_record_match_blocks_recent_duplicate_before_writes(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn
        players = {
            "A1": PlayerRow((1, "A1", 1000.0, 0, 0, 0, 0, "")),
            "A2": PlayerRow((2, "A2", 1000.0, 0, 0, 0, 0, "")),
            "B1": PlayerRow((3, "B1", 1000.0, 0, 0, 0, 0, "")),
            "B2": PlayerRow((4, "B2", 1000.0, 0, 0, 0, 0, "")),
        }

        def side_effect(stmt, params=None):
            stmt_text = str(stmt).lower()
            res = MagicMock()
            if "select max(rating), min(rating)" in stmt_text:
                res.fetchone.return_value = (1000.0, 1000.0)
            elif "select p.id, p.name, ps.rating" in stmt_text:
                res.fetchall.return_value = [players[name] for name in params["names"]]
            elif "select id, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b" in stmt_text:
                res.fetchall.return_value = [
                    MatchRow({"id": 42, "a1_id": 1, "a2_id": 2, "b1_id": 3, "b2_id": 4, "goals_a": 10, "goals_b": 8})
                ]
            return res

        mock_conn.execute.side_effect = side_effect

        with self.assertRaisesRegex(ValueError, "saved a few seconds ago"):
            DatabaseManager.record_match("A1", "A2", "B1", "B2", 10, 8, 1)

        executed_sql = "\n".join(str(call[0][0]).lower() for call in mock_conn.execute.call_args_list)
        self.assertNotIn("update player_stats", executed_sql)
        self.assertNotIn("insert into matches", executed_sql)


if __name__ == "__main__":
    unittest.main()
