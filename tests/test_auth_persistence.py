import os
import unittest
from unittest.mock import patch


os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from calcio_balilla.ui import auth_persistence


class TestBrowserTokenPersistence(unittest.TestCase):
    @patch("calcio_balilla.ui.auth_persistence.streamlit_js_eval")
    def test_storing_token_returns_the_stored_value(self, js_eval):
        auth_persistence._set_browser_token("session-token")

        expression = js_eval.call_args.kwargs["js_expressions"]
        self.assertIn("localStorage.setItem", expression)
        self.assertIn("localStorage.getItem", expression)
        self.assertIn("session-token", expression)

    @patch("calcio_balilla.ui.auth_persistence.streamlit_js_eval")
    def test_removing_token_returns_a_confirmation_value(self, js_eval):
        auth_persistence._remove_browser_token()

        expression = js_eval.call_args.kwargs["js_expressions"]
        self.assertIn("localStorage.removeItem", expression)
        self.assertIn("auth_token_removed", expression)


if __name__ == "__main__":
    unittest.main()
