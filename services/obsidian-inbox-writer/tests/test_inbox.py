from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile
import sys
import unittest

WRITER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WRITER_ROOT))

from app.inbox import InboxMessage, append_message, parse_category, resolve_inbox_path


class InboxTests(unittest.TestCase):
    def test_parse_known_tag(self):
        category, body = parse_category("#日记 今天测试机器人写入 Obsidian")

        self.assertEqual(category, "日记")
        self.assertEqual(body, "今天测试机器人写入 Obsidian")

    def test_parse_default_category(self):
        category, body = parse_category("没有标签的碎片")

        self.assertEqual(category, "随手记")
        self.assertEqual(body, "没有标签的碎片")

    def test_append_creates_daily_inbox_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = InboxMessage(
                platform="QQ",
                sender="nick",
                sender_id="123456",
                message="#金句 知识管理不是存储信息",
                raw_type="text",
                received_at=datetime(2026, 5, 27, 22, 31, 0),
            )

            result = append_message(root, item)
            content = result.path.read_text(encoding="utf-8")

        self.assertEqual(result.relative_path, "raw/inbox/2026-05-27.md")
        self.assertEqual(result.category, "金句")
        self.assertIn("type: inbox", content)
        self.assertIn("# Inbox 2026-05-27", content)
        self.assertIn("## 22:31 | QQ | 金句", content)
        self.assertIn("知识管理不是存储信息", content)
        self.assertIn("- sender_id: 123456", content)
        self.assertIn("- status: unprocessed", content)

    def test_append_preserves_existing_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = InboxMessage(
                platform="QQ",
                sender="nick",
                sender_id="123456",
                message="#灵感 第一条",
                raw_type="text",
                received_at=datetime(2026, 5, 27, 9, 0, 0),
            )
            second = InboxMessage(
                platform="QQ",
                sender="nick",
                sender_id="123456",
                message="#待办 第二条",
                raw_type="text",
                received_at=datetime(2026, 5, 27, 10, 0, 0),
            )

            append_message(root, first)
            result = append_message(root, second)
            content = result.path.read_text(encoding="utf-8")

        self.assertIn("## 09:00 | QQ | 灵感", content)
        self.assertIn("第一条", content)
        self.assertIn("## 10:00 | QQ | 待办", content)
        self.assertIn("第二条", content)

    def test_resolved_path_stays_in_raw_inbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            path = resolve_inbox_path(root, datetime(2026, 5, 27))

        self.assertEqual(path.name, "2026-05-27.md")
        self.assertEqual(path.parent.name, "inbox")

    def test_append_rejects_missing_vault_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_root = Path(tmp) / "missing"
            item = InboxMessage(
                platform="QQ",
                sender="nick",
                sender_id="123456",
                message="测试",
                raw_type="text",
                received_at=datetime(2026, 5, 27, 9, 0, 0),
            )

            with self.assertRaises(ValueError):
                append_message(missing_root, item)


if __name__ == "__main__":
    unittest.main()
