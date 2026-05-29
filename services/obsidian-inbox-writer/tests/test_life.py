from __future__ import annotations

from pathlib import Path
import os
import tempfile
import sys
import unittest
from unittest.mock import patch

WRITER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WRITER_ROOT))

from app.git_sync import GitSyncResult
from app.life import (
    DiaryEvent,
    FinanceRecord,
    FinanceStatusUpdate,
    HealthRecord,
    LifeDocument,
    LifeNote,
    PlanRecord,
    PlanStatusUpdate,
    append_diary_event,
    append_finance_record,
    append_finance_status_update,
    append_health_record,
    append_plan_record,
    append_plan_status_update,
    collect_life_recovery_records,
    write_life_note,
    write_summary_document,
)
from app.main import LifeFinanceRequest, RevertRequest, git_revert, life_finance


class LifeWriterTests(unittest.TestCase):
    def test_append_diary_event_creates_chinese_life_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = append_diary_event(
                root,
                DiaryEvent(
                    date="2026-05-27",
                    time="19:42",
                    category="情绪",
                    content="今天和朋友吃饭很开心。",
                    mood="开心",
                    platform="QQ",
                    sender_id="abc123",
                ),
            )
            content = result.path.read_text(encoding="utf-8")

        self.assertEqual(result.relative_path, "生活/日记/2026/2026-05/2026-05-27.md")
        self.assertEqual(result.kind, "diary")
        self.assertIn("type: life-diary", content)
        self.assertIn("# 2026-05-27 日记", content)
        self.assertIn("## 19:42 | 情绪", content)
        self.assertIn("今天和朋友吃饭很开心。", content)
        self.assertIn("- 心情：开心", content)

    def test_write_life_note_sanitizes_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = write_life_note(
                root,
                LifeNote(
                    date="2026-05-27",
                    time="20:10",
                    title="../黑神话:战斗节奏?",
                    category="游戏笔记",
                    content="把战斗节奏单独整理一篇。",
                    original_content="记一下，把战斗节奏单独整理一篇。",
                ),
            )
            content = result.path.read_text(encoding="utf-8")

        self.assertEqual(result.relative_path, "生活/笔记/游戏笔记/黑神话-战斗节奏.md")
        self.assertIn("# 黑神话-战斗节奏", content)
        self.assertIn("### 原文", content)
        self.assertIn("记一下，把战斗节奏单独整理一篇。", content)

    def test_append_finance_record_appends_monthly_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = FinanceRecord(
                date="2026-05-27",
                time="12:20",
                amount=18,
                direction="支出",
                category="餐饮",
                merchant="兰州拉面",
                note="午饭",
                wallet="支付宝",
                record_uid="fin-20260527-test",
            )
            second = FinanceRecord(
                date="2026-05-27",
                time="18:30",
                amount=6.5,
                direction="借出",
                category="借贷",
                note="临时周转",
                wallet="微信",
                counterparty="张三",
                record_uid="fin-20260527-loan",
            )

            append_finance_record(root, first)
            result = append_finance_record(root, second)
            content = result.path.read_text(encoding="utf-8")

        self.assertEqual(result.relative_path, "生活/财务/2026-05.md")
        self.assertIn("# 2026-05 财务", content)
        self.assertIn("| 日期 | 时间 | 类型 | 金额 | 类别 | 钱包/渠道 | 对象 | 状态 | 备注 |", content)
        self.assertIn("| 2026-05-27 | 12:20 | 支出 | 18.00 | 餐饮 | 支付宝 |  | 已记录 | 兰州拉面<br>午饭", content)
        self.assertIn("| 2026-05-27 | 18:30 | 借出 | 6.50 | 借贷 | 微信 | 张三 | 已记录 | 临时周转", content)
        self.assertIn("record_id: fin-20260527-test", content)

    def test_append_finance_status_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = append_finance_status_update(
                root,
                FinanceStatusUpdate(
                    date="2026-05-27",
                    time="20:00",
                    title="午饭 ¥18",
                    status="作废",
                    note="误记",
                ),
            )
            content = result.path.read_text(encoding="utf-8")

        self.assertEqual(result.relative_path, "生活/财务/2026-05.md")
        self.assertIn("## 修正记录", content)
        self.assertIn("午饭 ¥18", content)
        self.assertIn("标记为 **作废**", content)

    def test_append_health_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = append_health_record(
                root,
                HealthRecord(
                    date="2026-05-27",
                    time="21:30",
                    metric_type="跑步",
                    distance_km=5,
                    duration_minutes=30,
                    note="操场",
                    record_uid="health-20260527-test",
                ),
            )
            content = result.path.read_text(encoding="utf-8")

        self.assertEqual(result.relative_path, "生活/健康/2026-05.md")
        self.assertEqual(result.kind, "health")
        self.assertIn("type: life-health", content)
        self.assertIn("| 2026-05-27 | 21:30 | 跑步 |  |  | 30 | 5 | 已记录 | 操场", content)
        self.assertIn("record_id: health-20260527-test", content)

    def test_write_summary_document_uses_summary_subfolder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = write_summary_document(
                root,
                LifeDocument(
                    date="2026-05-27",
                    time="22:00",
                    document_type="日总结",
                    title="2026-05-27 日总结",
                    content="今天完成了链路设计。",
                ),
            )
            content = result.path.read_text(encoding="utf-8")

        self.assertEqual(result.relative_path, "生活/总结/日总结/2026-05-27.md")
        self.assertEqual(result.kind, "summary")
        self.assertIn("# 2026-05-27 日总结", content)
        self.assertIn("今天完成了链路设计。", content)

    def test_write_briefing_document_reports_briefing_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = write_summary_document(
                root,
                LifeDocument(
                    date="2026-05-27",
                    time="08:00",
                    document_type="晨报",
                    content="深圳天气晴，适合出门。",
                ),
            )

        self.assertEqual(result.relative_path, "生活/总结/晨报/2026-05-27.md")
        self.assertEqual(result.kind, "briefing")

    def test_append_plan_record_and_status_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = append_plan_record(
                root,
                PlanRecord(
                    date="2026-05-28",
                    time="16:30",
                    title="整理插件配置",
                    content="整理 AstrBot 插件配置",
                    plan_scope="日",
                    priority="高",
                    target_date="2026-05-29",
                    record_uid="plan-20260528-test",
                ),
            )
            append_plan_status_update(
                root,
                PlanStatusUpdate(
                    date="2026-05-28",
                    time="17:00",
                    title="整理插件配置",
                    status="已完成",
                ),
            )
            content = result.path.read_text(encoding="utf-8")

        self.assertEqual(result.relative_path, "生活/计划/计划清单.md")
        self.assertEqual(result.kind, "plan")
        self.assertIn("type: life-plan", content)
        self.assertIn("| 2026-05-28 | 16:30 | 日 | 2026-05-29 |", content)
        self.assertIn("整理 AstrBot 插件配置", content)
        self.assertIn("record_id: plan-20260528-test", content)
        self.assertIn("标记为 **已完成**", content)

    def test_append_plan_record_leaves_empty_target_cells_blank(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = append_plan_record(
                root,
                PlanRecord(
                    date="2026-05-28",
                    time="17:30",
                    title="看龙族动漫",
                    content="看龙族动漫",
                    plan_scope="长期",
                ),
            )
            content = result.path.read_text(encoding="utf-8")

        self.assertIn("| 2026-05-28 | 17:30 | 长期 |  |  | 中 | 未开始 | 看龙族动漫 |", content)
        self.assertNotIn("长期 | unknown | unknown |", content)

    def test_collect_life_recovery_records_reads_markdown_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            append_finance_record(
                root,
                FinanceRecord(
                    date="2026-05-27",
                    time="12:20",
                    amount=18,
                    direction="支出",
                    category="餐饮",
                    note="午饭",
                    record_uid="fin-recover",
                ),
            )
            append_plan_record(
                root,
                PlanRecord(
                    date="2026-05-27",
                    time="13:00",
                    title="整理插件",
                    content="整理插件",
                    record_uid="plan-recover",
                ),
            )
            append_health_record(
                root,
                HealthRecord(
                    date="2026-05-27",
                    time="21:00",
                    metric_type="跑步",
                    distance_km=5,
                    duration_minutes=30,
                    record_uid="health-recover",
                ),
            )

            records = collect_life_recovery_records(root)

        self.assertEqual(records["finance"][0]["record_uid"], "fin-recover")
        self.assertEqual(records["plans"][0]["record_uid"], "plan-recover")
        self.assertEqual(records["health"][0]["record_uid"], "health-recover")

    def test_rejects_escaped_life_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                append_diary_event(
                    root,
                    DiaryEvent(
                        date="2026-05-27",
                        time="19:42",
                        content="测试",
                        life_root="../raw",
                    ),
                )

    def test_rejects_path_separator_in_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                write_life_note(
                    root,
                    LifeNote(
                        date="2026-05-27",
                        time="20:10",
                        title="测试",
                        category="../逃逸",
                        content="测试",
                    ),
                )


class LifeApiTests(unittest.TestCase):
    def setUp(self):
        self.previous_token = os.environ.get("INBOX_TOKEN")
        self.previous_vault = os.environ.get("VAULT_ROOT")
        self.previous_git = os.environ.get("ENABLE_GIT_SYNC")
        os.environ["INBOX_TOKEN"] = "test-token"
        os.environ["ENABLE_GIT_SYNC"] = "true"

    def tearDown(self):
        self._restore_env("INBOX_TOKEN", self.previous_token)
        self._restore_env("VAULT_ROOT", self.previous_vault)
        self._restore_env("ENABLE_GIT_SYNC", self.previous_git)

    def test_life_api_uses_git_sync_for_written_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["VAULT_ROOT"] = tmp
            payload = LifeFinanceRequest(
                date="2026-05-27",
                time="12:20",
                amount=18,
                category="餐饮",
                note="午饭",
            )

            with patch("app.main.git_pull_rebase", return_value=GitSyncResult(synced=True)), patch(
                "app.main.git_commit_push",
                return_value=GitSyncResult(synced=True, commit_hash="abc1234"),
            ) as commit_push:
                result = life_finance(payload, authorization="Bearer test-token")

        self.assertEqual(result["ok"], True)
        self.assertEqual(result["path"], "生活/财务/2026-05.md")
        self.assertEqual(result["commit_hash"], "abc1234")
        commit_push.assert_called_once()
        self.assertEqual(commit_push.call_args.args[1], "生活/财务/2026-05.md")
        self.assertEqual(commit_push.call_args.args[2], "life: add finance 2026-05-27 12:20")

    def test_git_revert_api_reverts_writer_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["VAULT_ROOT"] = tmp
            payload = RevertRequest(commit_hash="abc1234")

            with patch("app.main.git_pull_rebase", return_value=GitSyncResult(synced=True)), patch(
                "app.main.git_revert_push",
                return_value=GitSyncResult(synced=True, commit_hash="def5678"),
            ) as revert_push:
                result = git_revert(payload, authorization="Bearer test-token")

        self.assertEqual(result["ok"], True)
        self.assertEqual(result["commit_hash"], "def5678")
        revert_push.assert_called_once()
        self.assertEqual(revert_push.call_args.args[1], "abc1234")

    def _restore_env(self, name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
