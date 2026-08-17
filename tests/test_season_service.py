import os
import sys
import unittest
from unittest.mock import MagicMock


os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
mock_st = MagicMock()


def mock_cache(func):
    return func


mock_st.cache_data = mock_cache
mock_st.cache_data.clear = MagicMock()
mock_st.cache_resource = mock_cache
sys.modules["streamlit"] = mock_st

from calcio_balilla.core.domain import Season
from calcio_balilla.core.season_service import SeasonService


class TestSeasonService(unittest.TestCase):
    def test_start_next_season_closes_current_and_opens_incremented_season(self):
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn

        mock_repo = MagicMock()
        mock_repo.get_active_season_for_update.return_value = Season(
            id=10,
            leaderboard_id=3,
            number=2,
            name="Season 2",
            is_active=True,
        )
        mock_repo.create_season.return_value = Season(
            id=11,
            leaderboard_id=3,
            number=3,
            name="Season 3",
            is_active=True,
        )

        service = SeasonService(engine=mock_engine, season_repo=mock_repo)
        result = service.start_next_season(3)

        self.assertEqual(result.number, 3)
        mock_repo.get_active_season_for_update.assert_called_once_with(mock_conn, 3)
        mock_repo.close_season.assert_called_once_with(mock_conn, 10)
        mock_repo.create_season.assert_called_once_with(mock_conn, 3, 3)

    def test_start_next_season_requires_active_season(self):
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn

        mock_repo = MagicMock()
        mock_repo.get_active_season_for_update.return_value = None

        service = SeasonService(engine=mock_engine, season_repo=mock_repo)

        with self.assertRaisesRegex(ValueError, "No active season found"):
            service.start_next_season(3)


if __name__ == "__main__":
    unittest.main()
