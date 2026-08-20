import os
import sys
import unittest
from unittest.mock import MagicMock


os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
mock_st = MagicMock()
sys.modules["streamlit"] = mock_st

from calcio_balilla.data.user_repository import UserRepository


class TestAuthSessionExpiry(unittest.TestCase):
    def test_new_session_expires_after_seven_days(self):
        engine = MagicMock()
        connection = MagicMock()
        engine.begin.return_value.__enter__.return_value = connection
        repository = UserRepository(engine=engine)

        token = repository.create_session(user_id=42)

        statement, params = connection.execute.call_args.args
        self.assertIn("expires_at", str(statement).lower())
        self.assertIn("now() + interval '7 days'", str(statement).lower())
        self.assertEqual(params["user_id"], 42)
        self.assertEqual(params["token_hash"], repository._hash_session_token(token))

    def test_expired_session_is_not_restored(self):
        connection = MagicMock()
        connection.execute.return_value.fetchone.return_value = None
        get_connection = MagicMock()
        get_connection.return_value.__enter__.return_value = connection
        repository = UserRepository(engine=MagicMock(), get_connection=get_connection)

        identity = repository.get_session_identity("expired-token")

        statement, params = connection.execute.call_args.args
        self.assertIn("s.expires_at > now()", str(statement).lower())
        self.assertEqual(params["token_hash"], repository._hash_session_token("expired-token"))
        self.assertIsNone(identity)


if __name__ == "__main__":
    unittest.main()
