from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import os
import sys
import unittest

WRITER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WRITER_ROOT))

from app.main import _parse_received_at


class MainTimeTests(unittest.TestCase):
    def setUp(self):
        self.previous_timezone = os.environ.get("INBOX_TIMEZONE")
        os.environ["INBOX_TIMEZONE"] = "Asia/Shanghai"

    def tearDown(self):
        if self.previous_timezone is None:
            os.environ.pop("INBOX_TIMEZONE", None)
        else:
            os.environ["INBOX_TIMEZONE"] = self.previous_timezone

    def test_default_time_uses_configured_timezone(self):
        received_at = _parse_received_at(None)

        self.assertIsNotNone(received_at)
        self.assertEqual(received_at.utcoffset(), timedelta(hours=8))

    def test_aware_input_is_converted_to_configured_timezone(self):
        received_at = _parse_received_at("2026-05-27T09:42:53Z")

        self.assertEqual(received_at.strftime("%Y-%m-%d %H:%M:%S"), "2026-05-27 17:42:53")
        self.assertEqual(received_at.utcoffset(), timedelta(hours=8))

    def test_naive_input_is_kept_as_given(self):
        received_at = _parse_received_at("2026-05-27 17:42:53")

        self.assertEqual(received_at.strftime("%Y-%m-%d %H:%M:%S"), "2026-05-27 17:42:53")
        self.assertIsNone(received_at.tzinfo)

    def test_invalid_time_returns_none(self):
        self.assertIsNone(_parse_received_at("not-a-time"))


if __name__ == "__main__":
    unittest.main()

