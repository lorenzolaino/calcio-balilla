import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
mock_st = MagicMock()


def mock_cache(func):
    return func


mock_st.cache_resource = mock_cache
sys.modules["streamlit"] = mock_st

import db


class TestDatabaseSchema(unittest.TestCase):
    def test_init_db_creates_matches_leaderboard_date_index(self):
        sys.modules["streamlit"] = mock_st
        importlib.reload(db)
        mock_engine = MagicMock()
        with patch("db.engine", mock_engine):
            mock_conn = MagicMock()
            mock_engine.begin.return_value.__enter__.return_value = mock_conn
            count_res = MagicMock()
            count_res.fetchone.return_value = (1,)

            def side_effect(stmt, params=None):
                stmt_text = str(stmt).lower()
                if "select count(*) from leaderboards" in stmt_text:
                    return count_res
                return MagicMock()

            mock_conn.execute.side_effect = side_effect

            db.init_db()

        executed_sql = "\n".join(str(call[0][0]).lower() for call in mock_conn.execute.call_args_list)
        self.assertIn("create index if not exists idx_matches_leaderboard_date", executed_sql)
        self.assertIn("on matches (leaderboard_id, date desc)", executed_sql)


if __name__ == "__main__":
    unittest.main()
