import sys
import os
import unittest
from unittest.mock import MagicMock

# Add backend to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from api.dependencies import get_user_id
from server import create_app

class TestBackendLogic(unittest.TestCase):
    def test_get_user_id(self):
        # Mock Request object
        mock_request = MagicMock()
        user_id = get_user_id(mock_request)
        self.assertEqual(user_id, "default-user", "User ID should be fixed to 'default-user' for desktop app")

    def test_create_app_data_dir(self):
        test_dir = "/tmp/test_adhd_data"
        create_app(data_dir=test_dir)
        self.assertEqual(os.environ.get("ADHD_DATA_DIR"), test_dir, "ADHD_DATA_DIR env var should be set")

if __name__ == '__main__':
    unittest.main()
