from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import sys
from pathlib import Path
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from astrbot_plugin_obsidian_life_hub.briefing import generate_briefing_text
from astrbot_plugin_obsidian_life_hub.config import LifePluginConfig
from astrbot_plugin_obsidian_life_hub.database import LifeDatabase
from astrbot_plugin_obsidian_life_hub.intent import classify_auto_record, classify_auto_record_batch
from astrbot_plugin_obsidian_life_hub.native_future_task import (
    looks_like_incomplete_native_future_task,
    parse_native_future_task,
)
from astrbot_plugin_obsidian_life_hub.summary import build_day_data_text, generate_daily_summary_text, generate_weekly_summary_text
from astrbot_plugin_obsidian_life_hub.utils import (
    command_body,
    infer_finance_category,
    is_command_message,
    is_low_signal_life_message,
    is_sender_allowed,
    normalize_note_category,
    parse_finance_command,
    parse_finance_record,
    parse_leading_tag,
    parse_note_command,
    strip_command_name,
)


class FakeEvent:
    def __init__(self, message: str):
        self.message_str = message

    def get_message_str(self) -> str:
        return self.message_str


class CoreTests(unittest.TestCase):
    def test_config_defaults_to_qingdao_weather(self):
        config = LifePluginConfig.from_astrbot_config({})

        self.assertEqual(config.amap_weather_city, "370200")
        self.assertEqual(config.weather_city_name, "青岛")
        self.assertEqual(config.life_root_folder, "生活")
        self.assertEqual(config.plan_folder, "待办")
        self.assertTrue(config.enable_inbox)
        self.assertTrue(config.inbox_require_admin)
        self.assertTrue(config.enable_native_future_task_bridge)
        self.assertTrue(config.enable_auto_record)
        self.assertEqual(config.auto_record_mode, "explicit")
        self.assertTrue(config.enable_scheduler)
        self.assertTrue(config.enable_plans)
        self.assertTrue(config.enable_health)
        self.assertEqual(config.health_folder, "健康")
        self.assertEqual(config.assistant_display_name, "Obsidian Life Hub")
        self.assertEqual(config.currency_symbol, "¥")
        self.assertEqual(config.monthly_budget, 0.0)
        self.assertFalse(config.include_conversations_in_summaries)
        self.assertEqual(config.daily_summary_time, "23:55")
        self.assertEqual(config.weekly_summary_day, 7)

    def test_only_trigger_help_is_registered_as_astrbot_command(self):
        main_text = (REPO_ROOT / "main.py").read_text(encoding="utf-8")
        command_lines = [line.strip() for line in main_text.splitlines() if line.strip().startswith("@filter.command(")]

        self.assertEqual(command_lines, ['@filter.command("查看触发词")'])
        self.assertNotIn("管理行为", main_text)
        self.assertNotIn("| 想做什么 |", main_text)
        self.assertIn("assistant_display_name} 触发词", main_text)

    def test_schema_hides_legacy_config_keys(self):
        schema = json.loads((REPO_ROOT / "_conf_schema.json").read_text(encoding="utf-8"))

        for key in (
            "enable_natural_language",
            "auto_categorize",
            "briefing_push_target",
            "briefing_push_hour",
            "summary_push_target",
            "summary_push_hour",
            "owner_display_name",
            "auto_record_mode",
            "diary_draft_time",
            "assistant_display_name",
            "diary_folder",
            "notes_folder",
            "finance_folder",
            "plan_folder",
            "health_folder",
            "summary_folder",
            "enable_auto_record",
            "enable_inbox",
            "inbox_require_admin",
            "inbox_allowed_sender_ids",
            "enable_diary",
            "enable_notes",
            "enable_finance",
            "enable_plans",
            "enable_health",
            "enable_daily_summary",
            "enable_morning_briefing",
            "write_briefing_to_obsidian",
            "auto_polish",
            "timeout_seconds",
        ):
            self.assertNotIn(key, schema)

        for key in (
            "enabled",
            "writer_base_url",
            "writer_token",
            "life_root_folder",
            "enable_native_future_task_bridge",
            "include_conversations_in_summaries",
            "currency_symbol",
            "monthly_budget",
            "enable_scheduler",
            "push_target_session",
            "daily_summary_time",
            "amap_weather_key",
            "weather_city_name",
        ):
            self.assertIn(key, schema)

    def test_config_reads_inbox_sender_allowlist(self):
        config = LifePluginConfig.from_astrbot_config({"inbox_allowed_sender_ids": "a,b\nc"})

        self.assertEqual(config.inbox_allowed_sender_ids, ["a", "b", "c"])

    def test_config_reads_legacy_push_target_fallback(self):
        briefing = LifePluginConfig.from_astrbot_config({"briefing_push_target": "qq:brief"})
        summary = LifePluginConfig.from_astrbot_config({"summary_push_target": "qq:summary"})
        explicit = LifePluginConfig.from_astrbot_config(
            {
                "push_target_session": "qq:explicit",
                "briefing_push_target": "qq:brief",
                "summary_push_target": "qq:summary",
            }
        )

        self.assertEqual(briefing.push_target_session, "qq:brief")
        self.assertEqual(summary.push_target_session, "qq:summary")
        self.assertEqual(explicit.push_target_session, "qq:explicit")

    def test_config_reads_scheduler_target(self):
        config = LifePluginConfig.from_astrbot_config(
            {
                "push_target_session": "qq:123",
                "daily_summary_time": "23:30",
                "include_conversations_in_summaries": True,
            }
        )

        self.assertEqual(config.push_target_session, "qq:123")
        self.assertEqual(config.daily_summary_time, "23:30")
        self.assertTrue(config.include_conversations_in_summaries)

    def test_config_reads_legacy_diary_draft_time_as_daily_summary_time(self):
        config = LifePluginConfig.from_astrbot_config({"diary_draft_time": "23:40"})

        self.assertEqual(config.daily_summary_time, "23:40")

    def test_parse_finance_command(self):
        self.assertEqual(parse_finance_command("午饭 18"), (18.0, "支出", "午饭"))
        self.assertEqual(parse_finance_command("收入 兼职 500"), (500.0, "收入", "兼职"))

    def test_native_future_task_bridge_parser(self):
        now = datetime(2026, 5, 28, 22, 54)

        task = parse_native_future_task("明天上午十点提醒我查旅游攻略", now=now)
        self.assertIsNotNone(task)
        self.assertEqual(task.run_at.strftime("%Y-%m-%d %H:%M"), "2026-05-29 10:00")
        self.assertEqual(task.note, "查旅游攻略")

        later_today = parse_native_future_task("[At:qq_official] 两点提醒我去签字", now=datetime(2026, 5, 27, 13, 28))
        self.assertIsNotNone(later_today)
        self.assertEqual(later_today.run_at.strftime("%Y-%m-%d %H:%M"), "2026-05-27 14:00")
        self.assertEqual(later_today.note, "去签字")

        tomorrow = parse_native_future_task("两点提醒我去签字", now=datetime(2026, 5, 27, 14, 1))
        self.assertIsNotNone(tomorrow)
        self.assertEqual(tomorrow.run_at.strftime("%Y-%m-%d %H:%M"), "2026-05-28 02:00")

        daily = parse_native_future_task("每天晚上9点提醒我跑步", now=datetime(2026, 5, 28, 23, 37))
        self.assertIsNotNone(daily)
        self.assertFalse(daily.run_once)
        self.assertEqual(daily.cron_expression, "0 21 * * *")
        self.assertEqual(daily.note, "跑步")

        completed = parse_native_future_task("每天晚上点提醒我跑步 晚上9点", now=datetime(2026, 5, 28, 23, 40))
        self.assertIsNotNone(completed)
        self.assertFalse(completed.run_once)
        self.assertEqual(completed.cron_expression, "0 21 * * *")
        self.assertEqual(completed.note, "跑步")

        completed_cn = parse_native_future_task("每天晚上提醒我跑步 晚上九点", now=datetime(2026, 5, 28, 23, 55))
        self.assertIsNotNone(completed_cn)
        self.assertFalse(completed_cn.run_once)
        self.assertEqual(completed_cn.cron_expression, "0 21 * * *")
        self.assertEqual(completed_cn.note, "跑步")

    def test_native_future_task_bridge_ignores_non_reminders(self):
        self.assertIsNone(parse_native_future_task("备忘 明天 18:00 交材料", now=datetime(2026, 5, 28, 12, 0)))
        self.assertIsNone(parse_native_future_task("明天上午十点查旅游攻略", now=datetime(2026, 5, 28, 12, 0)))
        self.assertTrue(looks_like_incomplete_native_future_task("每天晚上点提醒我跑步"))
        self.assertFalse(looks_like_incomplete_native_future_task("你设好提醒了吗"))
        self.assertEqual(parse_finance_command("支出 咖啡 18"), (18.0, "支出", "咖啡"))
        parsed = parse_finance_command("打了23分钟视频，午饭和辉哥去吃了个9块钱的西红柿鸡蛋面")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[0], 9.0)

    def test_parse_finance_record_supports_wallet_and_loan(self):
        parsed = parse_finance_record("借出 给张三100元 微信")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.amount, 100.0)
        self.assertEqual(parsed.direction, "借出")
        self.assertEqual(parsed.wallet, "微信")
        self.assertEqual(parsed.counterparty, "张三")

        transfer = parse_finance_record("转账 微信转到中国银行300元")
        self.assertIsNotNone(transfer)
        self.assertEqual(transfer.direction, "转账")
        self.assertEqual(transfer.wallet, "微信")
        self.assertEqual(transfer.counterparty, "中国银行")

    def test_auto_record_requires_explicit_trigger(self):
        self.assertIsNone(classify_auto_record("今天咖啡花了18"))
        self.assertIsNone(classify_auto_record("今天自然语言自动记录上线了"))
        self.assertIsNone(classify_auto_record("有个想法，以后可以把这个做成插件市场"))

    def test_explicit_finance_trigger(self):
        intent = classify_auto_record("记账，午饭吃了一碗9快钱的西红柿鸡蛋面")

        self.assertIsNotNone(intent)
        self.assertEqual(intent.kind, "finance")
        self.assertEqual(intent.amount, 9.0)
        self.assertEqual(intent.note, "午饭 西红柿鸡蛋面")
        self.assertEqual(intent.direction, "支出")

    def test_finance_alias_triggers_override_direction(self):
        expense = classify_auto_record("支出 午饭9元 西红柿鸡蛋面")
        income = classify_auto_record("收入 兼职500元")
        lend = classify_auto_record("借出 给张三100元 微信")

        self.assertIsNotNone(expense)
        self.assertEqual(expense.kind, "finance")
        self.assertEqual(expense.direction, "支出")
        self.assertIsNotNone(income)
        self.assertEqual(income.kind, "finance")
        self.assertEqual(income.direction, "收入")
        self.assertIsNotNone(lend)
        self.assertEqual(lend.kind, "finance")
        self.assertEqual(lend.direction, "借出")
        self.assertEqual(lend.wallet, "微信")
        self.assertEqual(lend.counterparty, "张三")

    def test_finance_multientry_requires_explicit_separator(self):
        risky = classify_auto_record("支出 午饭20元 晚饭30元")
        intents = classify_auto_record_batch("支出 午饭20元；晚饭30元")

        self.assertIsNotNone(risky)
        self.assertEqual(risky.kind, "needs_confirmation")
        self.assertEqual([item.kind for item in intents], ["finance", "finance"])
        self.assertEqual([item.amount for item in intents], [20.0, 30.0])
        self.assertEqual([item.note for item in intents], ["午饭", "晚饭"])

    def test_finance_query_triggers(self):
        query = classify_auto_record("借贷情况")

        self.assertIsNotNone(query)
        self.assertEqual(query.kind, "finance_query")
        self.assertEqual(query.content, "loan")

    def test_explicit_finance_supports_backfill_date(self):
        intent = classify_auto_record("记账 2026-05-26 19:30 晚饭18元 兰州拉面")

        self.assertIsNotNone(intent)
        self.assertEqual(intent.kind, "finance")
        self.assertEqual(intent.amount, 18.0)
        self.assertEqual(intent.note, "晚饭 兰州拉面")
        self.assertEqual(intent.date, "2026-05-26")
        self.assertEqual(intent.time, "19:30")

    def test_explicit_diary_trigger(self):
        intent = classify_auto_record("日记，今天自然语言自动记录上线了")

        self.assertIsNotNone(intent)
        self.assertEqual(intent.kind, "diary")
        self.assertEqual(intent.category, "日记")
        self.assertEqual(intent.content, "今天自然语言自动记录上线了")

    def test_explicit_diary_supports_backfill_date(self):
        intent = classify_auto_record("记事 5月26日 那天主要在处理论文格式")

        self.assertIsNotNone(intent)
        self.assertEqual(intent.kind, "diary")
        self.assertEqual(intent.category, "记事")
        self.assertEqual(intent.date, "2026-05-26")
        self.assertEqual(intent.content, "那天主要在处理论文格式")

    def test_backfill_trigger_wraps_inner_record(self):
        intent = classify_auto_record("补记 2026-05-26 19:30 支出 晚饭18元 兰州拉面")

        self.assertIsNotNone(intent)
        self.assertEqual(intent.kind, "finance")
        self.assertEqual(intent.trigger, "补记")
        self.assertEqual(intent.date, "2026-05-26")
        self.assertEqual(intent.time, "19:30")
        self.assertEqual(intent.amount, 18.0)

    def test_backfill_without_inner_trigger_defaults_to_diary(self):
        intent = classify_auto_record("补记 2026-05-26 那天主要在整理插件方案")

        self.assertIsNotNone(intent)
        self.assertEqual(intent.kind, "diary")
        self.assertEqual(intent.category, "补记")
        self.assertEqual(intent.date, "2026-05-26")

    def test_explicit_note_and_quote_triggers(self):
        idea = classify_auto_record("随想，Obsidian记录应该少猜测，多用明确入口")
        quote = classify_auto_record("语录 2026-05-26 抖音｜人真正的稳定，是知道自己在做什么")

        self.assertIsNotNone(idea)
        self.assertEqual(idea.kind, "note")
        self.assertEqual(idea.note_type, "随想")
        self.assertEqual(idea.content, "Obsidian记录应该少猜测，多用明确入口")
        self.assertIsNotNone(quote)
        self.assertEqual(quote.kind, "note")
        self.assertEqual(quote.note_type, "语录")
        self.assertEqual(quote.date, "2026-05-26")
        self.assertEqual(quote.title, "人真正的稳定，是知道自己在做什么")
        self.assertEqual(quote.source, "抖音")
        self.assertIn("来源：抖音", quote.content)

    def test_quote_trigger_supports_full_fields(self):
        quote = classify_auto_record("语录 抖音｜某账号｜保持稳定比偶尔热血更重要｜#自律 #生活｜提醒我要持续")

        self.assertIsNotNone(quote)
        self.assertEqual(quote.kind, "note")
        self.assertEqual(quote.source, "抖音")
        self.assertEqual(quote.author, "某账号")
        self.assertEqual(quote.tags, ("自律", "生活"))
        self.assertEqual(quote.comment, "提醒我要持续")
        self.assertIn("一句话感想：提醒我要持续", quote.content)

    def test_quote_trigger_supports_labeled_fields(self):
        quote = classify_auto_record("语录 原句：生活系统需要稳定可恢复 来源：测试 作者或账号：Codex 标签：链路 一句话感想：用于验证写入")

        self.assertIsNotNone(quote)
        self.assertEqual(quote.title, "生活系统需要稳定可恢复")
        self.assertEqual(quote.source, "测试")
        self.assertEqual(quote.author, "Codex")
        self.assertEqual(quote.tags, ("链路",))
        self.assertEqual(quote.comment, "用于验证写入")

        fallback = classify_auto_record("语录 来源：测试 作者：Codex 标签：链路 一句话感想：生活系统需要稳定可恢复")
        self.assertEqual(fallback.title, "生活系统需要稳定可恢复")

    def test_control_triggers(self):
        self.assertEqual(classify_auto_record("撤销上一条").kind, "undo")
        self.assertEqual(classify_auto_record("确认").kind, "confirm_pending")
        self.assertEqual(classify_auto_record("取消写入").kind, "cancel_pending")
        self.assertEqual(classify_auto_record("系统状态").kind, "system_status")
        self.assertEqual(classify_auto_record("Obsidian状态").kind, "system_status")
        self.assertEqual(classify_auto_record("恢复索引").kind, "recover_index")
        self.assertEqual(classify_auto_record("查看触发词").kind, "help")
        self.assertEqual(classify_auto_record("使用帮助").kind, "help")
        self.assertEqual(classify_auto_record("记账帮助").kind, "help")
        self.assertEqual(classify_auto_record("Obsidian帮助").kind, "help")
        self.assertEqual(classify_auto_record("晨报").kind, "briefing")
        self.assertEqual(classify_auto_record("今日总结").kind, "daily_summary")
        self.assertEqual(classify_auto_record("日总结").kind, "daily_summary")
        self.assertEqual(classify_auto_record("总结").kind, "daily_summary")
        self.assertEqual(classify_auto_record("日记草稿").kind, "diary_draft")
        self.assertEqual(classify_auto_record("语录周精选").kind, "quote_weekly")
        self.assertEqual(classify_auto_record("周报").kind, "weekly_summary")
        self.assertEqual(classify_auto_record("推送到这里").kind, "set_push_target")
        self.assertEqual(classify_auto_record("预算情况").content, "budget")
        self.assertEqual(classify_auto_record("财务周报").content, "week_report")
        self.assertEqual(classify_auto_record("计划复盘").kind, "plan_review")
        self.assertEqual(classify_auto_record("今日待办").kind, "todo_query")
        self.assertEqual(classify_auto_record("近期待办").content, "soon")
        amend = classify_auto_record("改上一条 记账 午饭18元")
        self.assertIsNotNone(amend)
        self.assertEqual(amend.kind, "amend")
        self.assertEqual(amend.content, "记账 午饭18元")

    def test_cancel_and_update_triggers(self):
        cancel_plan = classify_auto_record("取消计划 清单")
        update_plan = classify_auto_record("修改计划 清单 为 明天 整理宿舍")
        cancel_finance = classify_auto_record("作废账目 午饭")
        update_finance = classify_auto_record("修改账目 午饭 为 支出 午饭10元")

        self.assertEqual(cancel_plan.kind, "plan_cancel")
        self.assertEqual(cancel_plan.content, "清单")
        self.assertEqual(update_plan.kind, "plan_update")
        self.assertEqual(update_plan.content, "清单")
        self.assertEqual(update_plan.note, "明天 整理宿舍")
        self.assertEqual(cancel_finance.kind, "finance_cancel")
        self.assertEqual(cancel_finance.content, "午饭")
        self.assertEqual(update_finance.kind, "finance_update")
        self.assertEqual(update_finance.note, "支出 午饭10元")

    def test_plan_triggers(self):
        plan = classify_auto_record("计划 明天 高优先级 整理 AstrBot 插件配置")
        compact_date_plan = classify_auto_record("计划 明天整理一下宿舍个人物品")
        week = classify_auto_record("计划 本周 把计划系统跑通")
        long_term = classify_auto_record("计划 长期 去青岛周边旅行")
        query = classify_auto_record("今日计划")
        list_query = classify_auto_record("计划清单")
        done = classify_auto_record("完成计划 AstrBot")
        start = classify_auto_record("开始计划 AstrBot")
        postpone = classify_auto_record("推迟计划 AstrBot 到 明天")

        self.assertIsNotNone(plan)
        self.assertEqual(plan.kind, "plan")
        self.assertEqual(plan.plan_scope, "短期")
        self.assertEqual(plan.priority, "高")
        self.assertEqual(plan.date, (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"))
        self.assertIsNotNone(compact_date_plan)
        self.assertEqual(compact_date_plan.kind, "plan")
        self.assertEqual(compact_date_plan.plan_scope, "短期")
        self.assertEqual(compact_date_plan.content, "整理一下宿舍个人物品")
        self.assertIsNotNone(compact_date_plan.date)
        self.assertEqual(week.kind, "plan")
        self.assertEqual(week.plan_scope, "短期")
        self.assertEqual(long_term.kind, "plan")
        self.assertEqual(long_term.plan_scope, "长期")
        self.assertEqual(query.kind, "plan_query")
        self.assertEqual(query.content, "today")
        self.assertEqual(list_query.kind, "plan_query")
        self.assertEqual(list_query.content, "all")
        self.assertEqual(done.kind, "plan_complete")
        self.assertEqual(done.content, "AstrBot")
        self.assertEqual(start.kind, "plan_start")
        self.assertEqual(start.content, "AstrBot")
        self.assertEqual(postpone.kind, "plan_postpone")
        self.assertEqual(postpone.content, "AstrBot")
        self.assertEqual(postpone.date, (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"))

    def test_reminder_triggers(self):
        reminder = classify_auto_record("备忘 明天 18:00 交材料")
        chinese_time = classify_auto_record("备忘 明天晚上六点交材料")
        ddl = classify_auto_record("DDL 5月30日 23:59 提交论文终稿")
        query = classify_auto_record("今日备忘")
        native_reminder = classify_auto_record("提醒 明天 18:00 交材料")

        self.assertEqual(reminder.kind, "reminder")
        self.assertEqual(reminder.title, "交材料")
        self.assertEqual(reminder.date, (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"))
        self.assertEqual(reminder.time, "18:00")
        self.assertEqual(chinese_time.kind, "reminder")
        self.assertEqual(chinese_time.time, "18:00")
        self.assertEqual(chinese_time.title, "交材料")
        self.assertEqual(ddl.kind, "reminder")
        self.assertEqual(ddl.time, "23:59")
        self.assertEqual(query.kind, "reminder_query")
        self.assertEqual(query.content, "today")
        self.assertIsNone(native_reminder)

    def test_plan_multientry_requires_explicit_separator(self):
        risky = classify_auto_record("计划 有空看一下龙族动漫 去爬大珠山 去灵山岛")
        intents = classify_auto_record_batch("计划 有空 看龙族动漫；爬大珠山；去灵山岛")

        self.assertIsNotNone(risky)
        self.assertEqual(risky.kind, "needs_confirmation")
        self.assertEqual([item.kind for item in intents], ["plan", "plan", "plan"])
        self.assertEqual([item.plan_scope for item in intents], ["其它", "其它", "其它"])
        self.assertEqual([item.content for item in intents], ["看龙族动漫", "爬大珠山", "去灵山岛"])

    def test_confirmation_candidates_for_risky_messages(self):
        from astrbot_plugin_obsidian_life_hub.intent import build_confirmation_candidate_intents

        finance_items = build_confirmation_candidate_intents("支出 午饭20元 晚饭30元")
        plan_items = build_confirmation_candidate_intents("计划 有空看龙族动漫 去爬大珠山 去灵山岛")

        self.assertEqual([item.amount for item in finance_items], [20.0, 30.0])
        self.assertEqual([item.note for item in finance_items], ["午饭", "晚饭"])
        self.assertEqual([item.content for item in plan_items], ["看龙族动漫", "去爬大珠山", "去灵山岛"])

    def test_health_triggers(self):
        weight = classify_auto_record("体重 75.5kg")
        run = classify_auto_record("跑步 5公里 30分钟")
        sleep = classify_auto_record("睡眠 7.5小时")
        query = classify_auto_record("本周健康")

        self.assertEqual(weight.kind, "health")
        self.assertEqual(weight.category, "体重")
        self.assertEqual(weight.value, 75.5)
        self.assertEqual(weight.note, "")
        weight_note = classify_auto_record("体重 75.5kg codex-smoke 测试")
        self.assertEqual(weight_note.note, "codex-smoke 测试")
        self.assertEqual(run.kind, "health")
        self.assertEqual(run.distance_km, 5)
        self.assertEqual(run.duration_minutes, 30)
        run_compact = classify_auto_record("跑步 3.2公里 20m22s")
        self.assertEqual(run_compact.kind, "health")
        self.assertEqual(run_compact.distance_km, 3.2)
        self.assertAlmostEqual(run_compact.duration_minutes or 0, 20 + 22 / 60, places=2)
        self.assertEqual(run_compact.note, "")
        run_colon = classify_auto_record("跑步 3.2公里 20:22")
        self.assertAlmostEqual(run_colon.duration_minutes or 0, 20 + 22 / 60, places=2)
        self.assertEqual(sleep.value, 7.5)
        self.assertEqual(query.kind, "health_query")
        self.assertEqual(query.content, "week")

    def test_health_write_keeps_empty_metric_note_empty(self):
        main_text = (REPO_ROOT / "main.py").read_text(encoding="utf-8")

        self.assertIn("note=intent.note,\n            platform=event_platform(event)", main_text)
        self.assertIn("note=intent.note,\n            status=\"已记录\"", main_text)

    def test_explicit_collect_trigger(self):
        intent = classify_auto_record("收集，这个链接以后研究一下：https://example.com")

        self.assertIsNotNone(intent)
        self.assertEqual(intent.kind, "inbox")
        self.assertEqual(intent.content, "这个链接以后研究一下：https://example.com")

    def test_auto_record_ignores_ordinary_chat_and_dates(self):
        self.assertIsNone(classify_auto_record("你觉得这个怎么样"))
        self.assertIsNone(classify_auto_record("18号再说"))

    def test_auto_record_batch_splits_multiline_trigger_message(self):
        intents = classify_auto_record_batch(
            "[At:qq_official] 记账，午饭吃了一碗9快钱的西红柿鸡蛋面\n"
            "日记，今天自然语言自动记录上线了\n"
            "随想，以后可以把这个做成插件市场\n"
            "你觉得这个怎么样"
        )

        self.assertEqual([intent.kind for intent in intents], ["finance", "diary", "note"])
        self.assertEqual(intents[0].note, "午饭 西红柿鸡蛋面")
        self.assertEqual(intents[1].content, "今天自然语言自动记录上线了")
        self.assertEqual(intents[2].content, "以后可以把这个做成插件市场")

    def test_note_category_and_command(self):
        self.assertEqual(normalize_note_category("游戏"), "游戏笔记")
        self.assertEqual(normalize_note_category("语录"), "语录笔记")
        self.assertEqual(
            parse_note_command("游戏 黑神话|战斗节奏很重要"),
            ("游戏", "黑神话", "战斗节奏很重要"),
        )
        self.assertEqual(
            parse_note_command("随想 统一入口｜兼容中文竖线"),
            ("随想", "统一入口", "兼容中文竖线"),
        )

    def test_strip_command_name_handles_qq_at_and_full_body(self):
        self.assertEqual(strip_command_name("[At:qq_official] 记账 咖啡 18", ("记账",)), "咖啡 18")
        self.assertEqual(strip_command_name("支出 咖啡 18", ("支出", "收入")), "咖啡 18")
        self.assertEqual(strip_command_name("生活笔记 随想 洗澡回来测试|能写入生活层", ("生活笔记",)), "随想 洗澡回来测试|能写入生活层")
        self.assertEqual(strip_command_name("记 #灵感 完整正文", ("记", "收集", "存一下")), "#灵感 完整正文")

    def test_command_body_prefers_full_event_text_over_truncated_arg(self):
        event = FakeEvent("[At:qq_official] 日记 #链路测试 我回来了，这是生活助手日记测试")

        self.assertEqual(command_body(event, ("日记",), "#链路测试"), "#链路测试 我回来了，这是生活助手日记测试")

    def test_parse_leading_tag(self):
        self.assertEqual(parse_leading_tag("#链路测试 我回来了", "日记"), ("链路测试", "我回来了"))
        self.assertEqual(parse_leading_tag("没有标签", "日记"), ("日记", "没有标签"))

    def test_command_message_and_low_signal_message_detection(self):
        self.assertTrue(is_command_message("[At:qq_official] 记账 咖啡 18", ("记账",)))
        self.assertTrue(is_command_message("生活笔记 随想 标题|正文", ("生活笔记",)))
        self.assertFalse(is_command_message("普通聊天", ("记账",)))
        self.assertTrue(is_low_signal_life_message("支出"))
        self.assertFalse(is_low_signal_life_message("支出 咖啡 18"))

    def test_sender_allowlist(self):
        self.assertTrue(is_sender_allowed(sender_id="abc", allowed_sender_ids=[]))
        self.assertTrue(is_sender_allowed(sender_id="abc", allowed_sender_ids=["abc"]))
        self.assertFalse(is_sender_allowed(sender_id="abc", allowed_sender_ids=["other"]))

    def test_infer_finance_category(self):
        self.assertEqual(infer_finance_category("兰州拉面午饭"), "餐饮")
        self.assertEqual(infer_finance_category("地铁通勤"), "交通")

    def test_build_day_data_text(self):
        text = build_day_data_text(
            {
                "events": [{"event_time": "19:00", "category": "日记", "content": "链路测试"}],
                "notes": [],
                "finance": [],
                "plans": [{"plan_scope": "短期", "priority": "高", "status": "未开始", "title": "整理插件配置", "target_date": "2026-05-28"}],
                "conversations": [{"created_at": "2026-05-28 20:00:00", "role": "user", "content": "普通聊天不要进总结"}],
            }
        )

        self.assertIn("生活事件", text)
        self.assertIn("链路测试", text)
        self.assertIn("整理插件配置", text)
        self.assertNotIn("普通聊天不要进总结", text)

        text_with_chat = build_day_data_text(
            {
                "events": [{"event_time": "19:00", "category": "日记", "content": "链路测试"}],
                "notes": [],
                "finance": [],
                "plans": [],
                "conversations": [{"created_at": "2026-05-28 20:00:00", "role": "user", "content": "普通聊天可作背景"}],
            },
            include_conversations=True,
        )
        self.assertIn("普通聊天可作背景", text_with_chat)


class BriefingTests(unittest.IsolatedAsyncioTestCase):
    async def test_briefing_fallback_keeps_plan_context(self):
        async def no_llm(_prompt: str) -> None:
            return None

        config = LifePluginConfig.from_astrbot_config({"amap_weather_key": ""})
        text = await generate_briefing_text(
            config=config,
            llm_call=no_llm,
            plan_context="| 内容 | 时间 |\n|---|---|\n| 整理插件配置 | |\n| 交材料 | 18:00 |",
        )

        self.assertIn("## ✅ 待办", text)
        self.assertIn("## 📍青岛", text)
        self.assertIn("🌤️ 天气数据暂不可用", text)
        self.assertIn("整理插件配置", text)
        self.assertIn("交材料", text)
        self.assertNotIn("早上好", text)
        self.assertNotIn("出门前", text)
        self.assertNotIn("今日建议", text)
        self.assertNotIn("财务简讯", text)

    async def test_summary_fallback_has_operational_sections(self):
        async def no_llm(_prompt: str) -> None:
            return None

        day_text, ok = await generate_daily_summary_text(
            day_data={
                "events": [{"event_time": "19:00", "category": "日记", "content": "链路测试"}],
                "notes": [],
                "finance": [{"record_time": "12:00", "direction": "支出", "amount": 9, "category": "餐饮", "note": "午饭"}],
                "finance_summary": [
                    {"scope": "今日", "expense": 9, "income": 0, "currency_symbol": "¥"},
                    {"scope": "本周", "expense": 30, "income": 100, "currency_symbol": "¥"},
                    {"scope": "本月", "expense": 30, "income": 100, "currency_symbol": "¥"},
                ],
                "health": [],
                "plans": [{"status": "未开始", "plan_scope": "短期", "priority": "中", "title": "整理插件", "target_date": "2026-05-28"}],
                "summary_date": "2026-05-28",
                "upcoming_reminders": [
                    {"title": "交材料", "due_date": "2026-05-29", "due_time": "20:00", "status": "已记录"},
                    {"title": "提交论文材料", "due_date": "2026-05-30", "due_time": "", "status": "已记录"},
                ],
                "conversations": [],
            },
            llm_call=no_llm,
        )
        self.assertTrue(ok)
        self.assertIn("# 🌙 今日总结", day_text)
        self.assertIn("## ⏰ 待办提醒", day_text)
        self.assertIn("| 内容 | 截止时间 |", day_text)
        self.assertIn("| 交材料 | 明日 20:00 |", day_text)
        self.assertIn("## ✅ 计划概览", day_text)
        self.assertIn("## 💰 财务简讯", day_text)
        self.assertIn("| 范围 | 支出 | 收入 |", day_text)
        self.assertIn("## 📝 日记草稿", day_text)
        self.assertNotIn("今日一览", day_text)
        self.assertNotIn("今日重点", day_text)
        self.assertNotIn("明日接续", day_text)
        self.assertNotIn("已记录事实", day_text)

        week_text, ok = await generate_weekly_summary_text(
            range_data={
                "events": [],
                "notes": [{"note_date": "2026-05-28", "note_time": "12:00", "category": "语录笔记", "title": "一句话", "content": "内容"}],
                "finance": [
                    {"record_date": "2026-05-28", "record_time": "12:00", "direction": "收入", "amount": 100, "category": "其他"},
                    {"record_date": "2026-05-28", "record_time": "13:00", "direction": "支出", "amount": 30, "category": "餐饮"},
                ],
                "health": [{"record_date": "2026-05-28", "record_time": "19:00", "metric_type": "跑步", "distance_km": 5}],
                "plans": [
                    {"status": "已完成", "plan_scope": "短期", "priority": "中", "title": "完成项", "target_date": "2026-05-28"},
                    {"status": "未开始", "plan_scope": "短期", "priority": "高", "title": "推进项", "target_date": "2026-05-29"},
                ],
                "conversations": [],
            },
            llm_call=no_llm,
        )
        self.assertTrue(ok)
        self.assertIn("本周概览", week_text)
        self.assertIn("下周建议", week_text)


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_finance_records_store_wallet_and_counterparty(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LifeDatabase(str(Path(tmp) / "life.db"))
            try:
                await db.add_finance_record(
                    "session",
                    "2026-05-28",
                    "12:00",
                    100,
                    "借出",
                    "借贷",
                    note="临时周转",
                    wallet="微信",
                    counterparty="张三",
                )
                rows = await db.query_finance_records("session", directions=("借出",))

                self.assertEqual(rows[0]["wallet"], "微信")
                self.assertEqual(rows[0]["counterparty"], "张三")
                self.assertEqual(rows[0]["status"], "已记录")

                cancelled = await db.cancel_finance_by_keyword("session", "临时周转")
                self.assertIsNotNone(cancelled)
                rows = await db.query_finance_records("session", directions=("借出",))
                self.assertEqual(rows, [])
            finally:
                db.conn.close()

    async def test_plan_status_can_be_restored_after_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LifeDatabase(str(Path(tmp) / "life.db"))
            try:
                plan_id = await db.add_plan(
                    "session",
                    "2026-05-28",
                    "12:00",
                    "整理插件配置",
                    "整理插件配置",
                    "短期",
                    "中",
                )
                completed = await db.complete_plan_by_keyword("session", "插件")

                self.assertIsNotNone(completed)
                self.assertEqual(completed["previous_status"], "未开始")
                self.assertEqual(completed["status"], "已完成")

                await db.set_plan_status(plan_id, "未开始")
                rows = await db.query_plans("session", include_completed=True)

                self.assertEqual(rows[0]["status"], "未开始")
            finally:
                db.conn.close()

    async def test_plan_start_and_postpone(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LifeDatabase(str(Path(tmp) / "life.db"))
            try:
                await db.add_plan(
                    "session",
                    "2026-05-28",
                    "12:00",
                    "整理插件配置",
                    "整理插件配置",
                    "短期",
                    "中",
                )
                started = await db.start_plan_by_keyword("session", "插件")
                self.assertIsNotNone(started)
                self.assertEqual(started["status"], "进行中")

                postponed = await db.postpone_plan_by_keyword(
                    "session",
                    "插件",
                    target_date="2026-05-29",
                    note="明天",
                )
                self.assertIsNotNone(postponed)
                self.assertEqual(postponed["status"], "已推迟")
                self.assertEqual(postponed["new_target_date"], "2026-05-29")
            finally:
                db.conn.close()

    async def test_reminders_store_and_query_by_due_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LifeDatabase(str(Path(tmp) / "life.db"))
            try:
                await db.add_reminder(
                    "session",
                    "2026-05-28",
                    "12:00",
                    "交材料",
                    "交材料",
                    due_date="2026-05-29",
                    due_time="18:00",
                    record_uid="rem-1",
                )
                rows = await db.query_reminders(
                    "session",
                    start_date="2026-05-29",
                    end_date="2026-05-29",
                    include_undated=False,
                )
                day_data = await db.query_day("session", "2026-05-29")

                self.assertEqual(rows[0]["title"], "交材料")
                self.assertEqual(rows[0]["due_time"], "18:00")
                self.assertEqual(day_data["reminders"][0]["record_uid"], "rem-1")
            finally:
                db.conn.close()

    async def test_health_and_pending_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LifeDatabase(str(Path(tmp) / "life.db"))
            try:
                await db.add_health_record(
                    "session",
                    "2026-05-28",
                    "21:00",
                    "跑步",
                    distance_km=5,
                    duration_minutes=30,
                    note="操场",
                )
                rows = await db.query_health_records("session", metric_types=("跑步",))
                self.assertEqual(rows[0]["distance_km"], 5)

                pending_id = await db.add_pending_action("session", "auto_record", "两条账目", "[]")
                pending = await db.get_pending_action("session")
                self.assertEqual(pending["id"], pending_id)
                await db.resolve_pending_action(pending_id, "confirmed")
                self.assertIsNone(await db.get_pending_action("session"))
            finally:
                db.conn.close()

    async def test_import_recovery_records_skips_duplicate_uids(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LifeDatabase(str(Path(tmp) / "life.db"))
            try:
                records = {
                    "finance": [
                        {
                            "record_uid": "fin-1",
                            "record_date": "2026-05-28",
                            "record_time": "12:00",
                            "amount": 9,
                            "direction": "支出",
                            "category": "餐饮",
                            "note": "午饭",
                            "wallet": "支付宝",
                            "counterparty": "",
                            "status": "已记录",
                            "markdown_path": "生活/财务/2026-05 财务.md",
                        }
                    ],
                    "plans": [
                        {
                            "record_uid": "plan-1",
                            "plan_date": "2026-05-28",
                            "plan_time": "13:00",
                            "title": "整理插件",
                            "content": "整理插件",
                            "plan_scope": "短期",
                            "priority": "中",
                            "status": "未开始",
                            "target_date": "2026-05-29",
                            "target_time": None,
                            "markdown_path": "生活/待办/计划/计划清单.md",
                        }
                    ],
                    "health": [
                        {
                            "record_uid": "health-1",
                            "record_date": "2026-05-28",
                            "record_time": "21:00",
                            "metric_type": "跑步",
                            "distance_km": 5,
                            "duration_minutes": 30,
                            "status": "已记录",
                            "markdown_path": "生活/健康/2026-05 健康.md",
                        }
                    ],
                }

                first = await db.import_recovery_records("session", records)
                second = await db.import_recovery_records("session", records)

                self.assertEqual(first["finance"]["imported"], 1)
                self.assertEqual(first["plans"]["imported"], 1)
                self.assertEqual(first["health"]["imported"], 1)
                self.assertEqual(second["finance"]["skipped"], 1)
                self.assertEqual(second["plans"]["skipped"], 1)
                self.assertEqual(second["health"]["skipped"], 1)
            finally:
                db.conn.close()


if __name__ == "__main__":
    unittest.main()
