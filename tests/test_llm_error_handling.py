import os
import sys
import unittest


sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend"))
)

from core.llm_errors import classify_llm_error


class TestLlmErrorHandling(unittest.TestCase):
    def test_classifies_quota_errors_as_429_with_retry_guidance(self):
        status_code, code, message, detail = classify_llm_error(
            RuntimeError(
                "Error code: 429 - {'error': {'status': 'RESOURCE_EXHAUSTED', 'message': 'Quota exceeded. Please retry in 51s.'}}"
            )
        )

        self.assertEqual(status_code, 429)
        self.assertEqual(code, "LLM_QUOTA_EXCEEDED")
        self.assertIn("quota", message.lower())
        self.assertIn("51s", detail)


if __name__ == "__main__":
    unittest.main()
