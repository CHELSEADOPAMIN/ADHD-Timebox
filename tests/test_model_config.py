import os
import sys
import unittest
from unittest.mock import patch


sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend"))
)

from agents.model_config import resolve_model


class TestModelConfig(unittest.TestCase):
    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True)
    def test_gemini_defaults_to_flash_for_direct_api(self):
        self.assertEqual(resolve_model(), "gemini-2.5-flash")


if __name__ == "__main__":
    unittest.main()
