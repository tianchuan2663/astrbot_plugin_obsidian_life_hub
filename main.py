from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import date, datetime, timedelta
import inspect
import json
from pathlib import Path
import re
from typing import Any
import uuid

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig

from . import prompts
from .briefing import generate_briefing_text
from .config import LifePluginConfig
from .database import LifeDatabase
from .intent import AutoRecordIntent, build_confirmation_candidate_intents, classify_auto_record, classify_auto_record_batch
from .native_future_task import looks_like_incomplete_native_future_task, parse_native_future_task
from .report_renderer import markdown_to_push_text
from .summary import generate_daily_summary_text, generate_diary_draft_text, generate_quote_weekly_text, generate_weekly_summary_text
from .utils import (
    command_body,
    event_message_text,
    event_platform,
    event_sender_id,
    event_sender_name,
    event_session_id,
    infer_finance_category,
    is_command_message,
    is_low_signal_life_message,
    is_sender_allowed,
    normalize_note_category,
    now_date_time,
    parse_finance_record,
    parse_leading_tag,
    parse_note_command,
    safe_error_text,
    truncate,
)
from .writer_client import WriterClient


PLUGIN_NAME = "astrbot_plugin_obsidian_life_hub"
INBOX_COMMANDS = ("记", "收集", "存一下")
DIARY_COMMANDS = ("日记",)
NOTE_COMMANDS = ("生活笔记", "笔记")
FINANCE_COMMANDS = ("记账", "账目")
FINANCE_RECORD_COMMANDS = FINANCE_COMMANDS + ("支出", "收入", "借入", "借出", "还款", "收款", "转账")
FINANCE_QUERY_COMMANDS = (
    "今日财务",
    "本周财务",
    "本月财务",
    "借贷情况",
    "钱包统计",
    "预算情况",
    "财务周报",
    "财务月报",
)
FINANCE_CANCEL_COMMANDS = ("作废账目", "删除账目")
FINANCE_UPDATE_COMMANDS = ("修改账目", "改账目")
PLAN_COMMANDS = ("计划",)
PLAN_QUERY_COMMANDS = (
    "我的计划",
    "计划清单",
    "所有计划",
    "今日计划",
    "本周计划",
    "本月计划",
    "长期计划",
    "空闲计划",
)
PLAN_DONE_COMMANDS = ("完成计划",)
PLAN_CANCEL_COMMANDS = ("取消计划", "删除计划", "作废计划")
PLAN_UPDATE_COMMANDS = ("修改计划", "改计划")
PLAN_POSTPONE_COMMANDS = ("推迟计划",)
PLAN_START_COMMANDS = ("开始计划",)
PLAN_REVIEW_COMMANDS = ("计划复盘",)
HEALTH_COMMANDS = ("健康", "体重", "跑步", "睡眠", "健身", "运动")
HEALTH_QUERY_COMMANDS = ("今日健康", "本周健康", "本月健康", "健康概览")
CONFIRM_COMMANDS = ("确认", "确认写入", "取消", "取消写入")
STATUS_COMMANDS = ("系统状态", "Obsidian状态")
HELP_COMMANDS = ("查看触发词", "Obsidian帮助", "使用帮助", "记账帮助", "计划帮助", "健康帮助", "总结帮助")
RECOVERY_COMMANDS = ("恢复索引", "重建索引")
BRIEFING_COMMANDS = ("晨报",)
SUMMARY_COMMANDS = ("今日总结", "日总结", "总结")
DIARY_DRAFT_COMMANDS = ("日记草稿",)
QUOTE_WEEKLY_COMMANDS = ("语录周精选",)
WEEKLY_SUMMARY_COMMANDS = ("周报",)
ALL_COMMANDS = (
    INBOX_COMMANDS
    + DIARY_COMMANDS
    + NOTE_COMMANDS
    + FINANCE_RECORD_COMMANDS
    + FINANCE_QUERY_COMMANDS
    + FINANCE_CANCEL_COMMANDS
    + FINANCE_UPDATE_COMMANDS
    + PLAN_COMMANDS
    + PLAN_QUERY_COMMANDS
    + PLAN_DONE_COMMANDS
    + PLAN_CANCEL_COMMANDS
    + PLAN_UPDATE_COMMANDS
    + PLAN_POSTPONE_COMMANDS
    + PLAN_START_COMMANDS
    + PLAN_REVIEW_COMMANDS
    + HEALTH_COMMANDS
    + HEALTH_QUERY_COMMANDS
    + CONFIRM_COMMANDS
    + STATUS_COMMANDS
    + HELP_COMMANDS
    + RECOVERY_COMMANDS
    + BRIEFING_COMMANDS
    + SUMMARY_COMMANDS
    + DIARY_DRAFT_COMMANDS
    + QUOTE_WEEKLY_COMMANDS
    + WEEKLY_SUMMARY_COMMANDS
)

@register(PLUGIN_NAME, "qwe", "Obsidian Life Hub", "0.1.2")
class ObsidianLifeHubPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.raw_config = config
        self.config = LifePluginConfig.from_astrbot_config(config)
        plugin_dir = Path(__file__).parent
        data_dir = plugin_dir / "data"
        data_dir.mkdir(exist_ok=True)
        self.db = LifeDatabase(str(data_dir / "obsidian_life_hub.db"))
        self.writer = WriterClient(self.config)
        self._scheduler_task: asyncio.Task | None = None
        self._scheduler_seen: set[str] = set()
        self._pending_native_future_tasks: dict[str, str] = {}

    async def initialize(self):
        if self.config.enabled:
            logger.info("[ObsidianLifeHub] plugin loaded")
            if self.config.enable_scheduler:
                self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        else:
            logger.info("[ObsidianLifeHub] plugin disabled by config")

    @filter.event_message_type(filter.EventMessageType.ALL, priority=50)
    async def on_auto_record_message(self, event: AstrMessageEvent):
        if not self.config.enabled or not (self.config.enable_auto_record or self.config.enable_native_future_task_bridge):
            return

        message = event_message_text(event)
        if not message or is_low_signal_life_message(message):
            return
        if self._is_unmentioned_group_message(event):
            return

        if self.config.enable_native_future_task_bridge:
            reply = await self._maybe_create_native_future_task(event, message)
            if reply:
                try:
                    event.stop_event()
                except Exception:
                    pass
                yield event.plain_result(reply)
                return

        if not self.config.enable_auto_record:
            return

        intents = classify_auto_record_batch(message, mode=self.config.auto_record_mode)
        if not intents:
            return
        await self._remember_session(event)

        try:
            event.stop_event()
        except Exception:
            pass

        replies: list[str] = []
        try:
            for intent in intents:
                reply = await self._handle_auto_record_intent(event, intent)
                if reply:
                    replies.append(reply)
        except Exception as exc:
            logger.warning(f"[ObsidianLifeHub] auto record failed: {safe_error_text(exc)}")
            yield event.plain_result(f"自动记录失败：{safe_error_text(exc)}")
            return

        if replies:
            yield event.plain_result(_compact_reply_lines(replies))

    async def _maybe_create_native_future_task(self, event: AstrMessageEvent, message: str) -> str | None:
        session_id = event_session_id(event)
        timezone = self._runtime_timezone(event)
        pending_message = self._pending_native_future_tasks.get(session_id)
        source_message = f"{pending_message} {message}" if pending_message else message
        task = parse_native_future_task(source_message, timezone=timezone)
        if task is None:
            if pending_message:
                if looks_like_incomplete_native_future_task(source_message):
                    return "还差一个具体时间，比如：晚上9点。"
                self._pending_native_future_tasks.pop(session_id, None)
            elif looks_like_incomplete_native_future_task(message):
                self._pending_native_future_tasks[session_id] = message
                return "你想让我几点提醒？比如：晚上9点。"
            return None

        cron_mgr = getattr(self.context, "cron_manager", None)
        if cron_mgr is None:
            logger.warning("[ObsidianLifeHub] native future task bridge skipped: cron_manager unavailable")
            return None

        self._pending_native_future_tasks.pop(session_id, None)
        note = f"到时间后提醒当前用户：{task.note}"
        payload = {
            "session": getattr(event, "unified_msg_origin", "") or event_session_id(event),
            "sender_id": event_sender_id(event),
            "note": note,
            "origin": "obsidian_life_hub_bridge",
        }
        try:
            job = await cron_mgr.add_active_job(
                name=f"{task.repeat_label}提醒：{task.title}" if task.repeat_label else f"提醒：{task.title}",
                cron_expression=task.cron_expression,
                payload=payload,
                description=note,
                run_once=task.run_once,
                run_at=task.run_at if task.run_once else None,
            )
        except Exception as exc:
            logger.warning(f"[ObsidianLifeHub] native future task bridge failed: {safe_error_text(exc)}")
            return None

        logger.info(f"[ObsidianLifeHub] native future task created: {getattr(job, 'job_id', '')} {task.run_at.isoformat()}")
        if task.repeat_label:
            return f"已创建原生未来任务：{task.repeat_label} {task.run_at.strftime('%H:%M')} 提醒你 {task.note}"
        return f"已创建原生未来任务：{task.run_at.strftime('%Y-%m-%d %H:%M')} 提醒你 {task.note}"

    def _runtime_timezone(self, event: AstrMessageEvent | None = None) -> str:
        try:
            config = self.context.get_config(umo=getattr(event, "unified_msg_origin", None))
            timezone = config.get("timezone")
            if timezone:
                return str(timezone)
        except Exception:
            pass
        try:
            config = self.context.get_config()
            timezone = config.get("timezone")
            if timezone:
                return str(timezone)
        except Exception:
            pass
        return "Asia/Shanghai"

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, request):
        if not self.config.enabled:
            return
        await self._remember_session(event)
        await self._log_conversation(event, "user")

    @filter.on_llm_response()
    async def on_llm_response(self, event: AstrMessageEvent, response):
        if not self.config.enabled:
            return
        text = getattr(response, "completion_text", "") or ""
        if text.strip():
            await self.db.add_conversation_log(event_session_id(event), "assistant", text.strip())

    async def cmd_life(self, event: AstrMessageEvent):
        """查看 Obsidian Life Hub 状态。"""
        if not self.config.enabled:
            yield event.plain_result("Obsidian Life Hub 已关闭。")
            return
        writer_state = "已配置" if self.config.writer_token else "未配置 token"
        weather_state = f"{self.config.weather_city_name}({self.config.amap_weather_city})" if self.config.amap_weather_key else "未配置"
        yield event.plain_result(
            "Obsidian Life Hub 已启用。\n"
            f"- writer: {self.config.writer_base_url}（{writer_state}）\n"
            f"- 天气: {weather_state}\n"
            "- 总指令: 查看触发词\n"
            "- 常用触发: 记账、计划、备忘、随想、语录、体重、晨报、今日总结"
        )

    async def cmd_status(self, event: AstrMessageEvent, content: str = ""):
        """查看 writer、Git、SQLite 索引和待确认状态。"""
        yield event.plain_result(await self._system_status(event))

    @filter.command("查看触发词")
    async def cmd_help(self, event: AstrMessageEvent, content: str = ""):
        """查看所有聊天触发词。"""
        message = event_message_text(event)
        topic = "all"
        if "记账帮助" in message:
            topic = "finance"
        elif "计划帮助" in message:
            topic = "plan"
        elif "健康帮助" in message:
            topic = "health"
        elif "总结帮助" in message:
            topic = "summary"
        yield event.plain_result(self._help_text(topic))

    async def cmd_recover_index(self, event: AstrMessageEvent, content: str = ""):
        """从 Obsidian Markdown 重建插件 SQLite 索引。"""
        yield event.plain_result(await self._recover_index(event))

    async def cmd_inbox(self, event: AstrMessageEvent, content: str = ""):
        """写入 raw/inbox。用法：记 #灵感 这里是内容"""
        if not self.config.enable_inbox:
            yield event.plain_result("Inbox 记录功能已关闭。")
            return
        try:
            event.stop_event()
        except Exception:
            pass
        sender_id = event_sender_id(event)
        try:
            is_admin = bool(event.is_admin())
        except Exception:
            is_admin = False
        if self.config.inbox_require_admin and not is_admin:
            yield event.plain_result("没有写入权限。")
            return
        if not is_sender_allowed(sender_id=sender_id, allowed_sender_ids=self.config.inbox_allowed_sender_ids):
            yield event.plain_result("当前账号不在 Obsidian 写入白名单中。")
            return
        await self._remember_session(event)
        body = command_body(event, INBOX_COMMANDS, content)
        if not body:
            yield event.plain_result("请在“记”后面输入要写入 Obsidian 的内容。")
            return
        result = await self.writer.append_inbox(
            platform=event_platform(event),
            sender=event_sender_name(event),
            sender_id=sender_id,
            message=body,
            raw_type="text",
        )
        await self._remember_write(event, action_type="inbox", trigger="/记", result=result, original_text=body)
        yield event.plain_result(self._format_inbox_reply(result))

    async def cmd_diary(self, event: AstrMessageEvent, content: str = ""):
        """写生活日记。用法：日记 今天很开心"""
        if not self.config.enable_diary:
            yield event.plain_result("日记记录功能已关闭。")
            return
        body = command_body(event, DIARY_COMMANDS, content)
        if not body:
            yield event.plain_result("请在“日记”后面输入要记录的内容。")
            return
        category, diary_content = parse_leading_tag(body, "日记")
        result = await self._record_diary(event, content=diary_content, category=category)
        yield event.plain_result(self._format_write_reply("日记", result))

    async def cmd_note(self, event: AstrMessageEvent, content: str = ""):
        """写生活笔记。用法：生活笔记 游戏 标题|内容"""
        if not self.config.enable_notes:
            yield event.plain_result("生活笔记功能已关闭。")
            return
        body = command_body(event, NOTE_COMMANDS, content)
        parsed = parse_note_command(body)
        if not parsed:
            yield event.plain_result("用法：生活笔记 <类型> <标题>|<内容>，例如 生活笔记 游戏 黑神话|战斗节奏很重要")
            return
        note_type, title, body = parsed
        result = await self._write_note(event, note_type=note_type, title=title, content=body)
        yield event.plain_result(self._format_write_reply("笔记", result))

    async def cmd_finance(self, event: AstrMessageEvent, content: str = ""):
        """记录财务。用法：记账 午饭 18"""
        if not self.config.enable_finance:
            yield event.plain_result("记账功能已关闭。")
            return
        body = command_body(event, FINANCE_RECORD_COMMANDS, content)
        trigger = _finance_trigger_from_message(event_message_text(event))
        parsed = parse_finance_record(body, direction_override=_direction_from_finance_trigger(trigger))
        if not parsed:
            yield event.plain_result("用法：记账 午饭 18，或 借出 给张三100元 微信")
            return
        result = await self._record_finance(
            event,
            amount=parsed.amount,
            direction=parsed.direction,
            note=parsed.description,
            category=_finance_category_for(parsed.direction, parsed.description),
            wallet=parsed.wallet,
            counterparty=parsed.counterparty,
            trigger=trigger,
        )
        yield event.plain_result(self._format_write_reply("账目", result))

    async def cmd_finance_query(self, event: AstrMessageEvent, content: str = ""):
        """查询财务概览。"""
        result = await self._query_finance(event, _finance_query_from_message(event_message_text(event)))
        yield event.plain_result(result)

    async def cmd_plan(self, event: AstrMessageEvent, content: str = ""):
        """记录计划。用法：计划 明天 整理插件配置"""
        if not self.config.enable_plans:
            yield event.plain_result("计划功能已关闭。")
            return
        body = command_body(event, PLAN_COMMANDS, content)
        intent = classify_auto_record_batch(f"计划 {body}", mode="explicit")
        plan_intent = intent[0] if intent else None
        if not plan_intent or plan_intent.kind != "plan":
            yield event.plain_result("用法：计划 明天 整理插件配置")
            return
        result = await self._record_plan(event, plan_intent)
        yield event.plain_result(self._format_write_reply("计划", result))

    async def cmd_plans(self, event: AstrMessageEvent, content: str = ""):
        """查询计划。"""
        message = event_message_text(event)
        result = await self._query_plans(event, _plan_query_from_message(message))
        yield event.plain_result(result)

    async def cmd_done_plan(self, event: AstrMessageEvent, content: str = ""):
        """完成计划。用法：完成计划 关键词"""
        body = command_body(event, PLAN_DONE_COMMANDS, content)
        if not body:
            yield event.plain_result("请提供要完成的计划关键词。")
            return
        result = await self._complete_plan(event, body)
        yield event.plain_result(result)

    async def cmd_postpone_plan(self, event: AstrMessageEvent, content: str = ""):
        """推迟计划。用法：推迟计划 整理宿舍 到 明天"""
        body = command_body(event, PLAN_POSTPONE_COMMANDS, content)
        intent = classify_auto_record(f"推迟计划 {body}", mode="explicit")
        if not intent or intent.kind != "plan_postpone":
            yield event.plain_result("用法：推迟计划 <关键词> 到 <日期>，例如 推迟计划 整理宿舍 到 明天")
            return
        yield event.plain_result(await self._postpone_plan(event, intent))

    async def cmd_start_plan(self, event: AstrMessageEvent, content: str = ""):
        """标记计划进行中。"""
        body = command_body(event, PLAN_START_COMMANDS, content)
        if not body:
            yield event.plain_result("请提供要开始的计划关键词。")
            return
        yield event.plain_result(await self._start_plan(event, body))

    async def cmd_plan_review(self, event: AstrMessageEvent, content: str = ""):
        """生成计划复盘。"""
        yield event.plain_result(await self._review_plans(event))

    async def cmd_briefing(self, event: AstrMessageEvent, content: str = ""):
        """生成今日晨报。"""
        result = await self._generate_briefing(event)
        yield event.plain_result(result)

    async def cmd_summary(self, event: AstrMessageEvent, content: str = ""):
        """生成今日日总结。"""
        result = await self._generate_daily_summary(event)
        yield event.plain_result(result)

    async def cmd_diary_draft(self, event: AstrMessageEvent, content: str = ""):
        """生成今日日记草稿。"""
        result = await self._generate_diary_draft(event)
        yield event.plain_result(result)

    async def cmd_quote_weekly(self, event: AstrMessageEvent, content: str = ""):
        """生成本周语录精选。"""
        result = await self._generate_quote_weekly(event)
        yield event.plain_result(result)

    async def cmd_weekly_summary(self, event: AstrMessageEvent, content: str = ""):
        """生成本周周报。"""
        result = await self._generate_weekly_summary(event)
        yield event.plain_result(result)

    async def _handle_auto_record_intent(self, event: AstrMessageEvent, intent: AutoRecordIntent) -> str | None:
        if intent.kind == "confirm_pending":
            return await self._confirm_pending_action(event)

        if intent.kind == "cancel_pending":
            return await self._cancel_pending_action(event)

        if intent.kind == "system_status":
            return await self._system_status(event)

        if intent.kind == "help":
            return self._help_text(intent.content or "all")

        if intent.kind == "recover_index":
            return await self._recover_index(event)

        if intent.kind == "set_push_target":
            return await self._set_push_target(event)

        if intent.kind == "needs_confirmation":
            return await self._save_confirmation_request(event, intent)

        if intent.kind == "undo":
            return await self._undo_last_write(event)

        if intent.kind == "amend":
            return await self._amend_last_write(event, intent.content)

        if intent.kind == "briefing":
            return await self._generate_briefing(event)

        if intent.kind == "diary_draft":
            return await self._generate_diary_draft(event, date_text=intent.date)

        if intent.kind == "daily_summary":
            return await self._generate_daily_summary(event, date_text=intent.date)

        if intent.kind == "quote_weekly":
            return await self._generate_quote_weekly(event)

        if intent.kind == "weekly_summary":
            return await self._generate_weekly_summary(event)

        if intent.kind == "plan_query":
            return await self._query_plans(event, intent.content or "all")

        if intent.kind == "reminder_query":
            return await self._query_reminders(event, intent.content or "all")

        if intent.kind == "todo_query":
            return await self._query_todos(event, intent.content or "all")

        if intent.kind == "plan_complete":
            return await self._complete_plan(event, intent.content)

        if intent.kind == "plan_cancel":
            return await self._cancel_plan(event, intent.content)

        if intent.kind == "plan_update":
            return await self._update_plan(event, intent.content, intent.note)

        if intent.kind == "plan_postpone":
            return await self._postpone_plan(event, intent)

        if intent.kind == "plan_start":
            return await self._start_plan(event, intent.content)

        if intent.kind == "plan_review":
            return await self._review_plans(event)

        if intent.kind == "plan":
            if not self.config.enable_plans:
                return "计划功能已关闭。"
            result = await self._record_plan(event, intent)
            return self._format_auto_record_reply("计划", result)

        if intent.kind == "reminder":
            result = await self._record_reminder(event, intent)
            return self._format_auto_record_reply("备忘", result)

        if intent.kind == "finance_query":
            return await self._query_finance(event, intent.content or "month")

        if intent.kind == "finance":
            if not self.config.enable_finance:
                return "记账功能已关闭。"
            if intent.amount is None:
                return None
            result = await self._record_finance(
                event,
                amount=float(intent.amount),
                direction=intent.direction or "支出",
                category=intent.category or infer_finance_category(intent.note),
                note=intent.note,
                wallet=intent.wallet,
                counterparty=intent.counterparty,
                date_text=intent.date,
                time_text=intent.time,
                trigger=intent.trigger,
                original_text=intent.note,
            )
            return self._format_auto_record_reply("账目", result)

        if intent.kind == "finance_cancel":
            return await self._cancel_finance(event, intent.content)

        if intent.kind == "finance_update":
            return await self._update_finance(event, intent.content, intent.note)

        if intent.kind == "health_query":
            return await self._query_health(event, intent.content or "month")

        if intent.kind == "health":
            if not self.config.enable_health:
                return "健康记录功能已关闭。"
            result = await self._record_health(event, intent)
            return self._format_auto_record_reply("健康", result)

        if intent.kind == "diary":
            if not self.config.enable_diary:
                return "日记记录功能已关闭。"
            result = await self._record_diary(
                event,
                content=intent.content,
                category=intent.category or "日记",
                date_text=intent.date,
                time_text=intent.time,
                trigger=intent.trigger,
                original_text=intent.content,
            )
            return self._format_auto_record_reply("日记", result)

        if intent.kind == "note":
            if not self.config.enable_notes:
                return "生活笔记功能已关闭。"
            result = await self._write_note(
                event,
                note_type=intent.note_type or "随想",
                title=intent.title or truncate(intent.content, 30),
                content=intent.content,
                date_text=intent.date,
                time_text=intent.time,
                trigger=intent.trigger,
                original_text=intent.content,
            )
            return self._format_auto_record_reply("笔记", result)

        if intent.kind == "inbox":
            if not self.config.enable_inbox:
                return "Inbox 记录功能已关闭。"
            message = intent.content
            if intent.date:
                stamp = f"{intent.date} {intent.time or ''}".strip()
                message = f"[补记 {stamp}] {message}"
            result = await self.writer.append_inbox(
                platform=event_platform(event),
                sender=event_sender_name(event),
                sender_id=event_sender_id(event),
                message=message,
                raw_type="text",
            )
            await self._remember_write(
                event,
                action_type="inbox",
                trigger=intent.trigger,
                result=result,
                original_text=message,
            )
            return self._format_inbox_reply(result)

        return None

    async def _record_diary(
        self,
        event: AstrMessageEvent,
        *,
        content: str,
        category: str,
        mood: str | None = None,
        date_text: str | None = None,
        time_text: str | None = None,
        trigger: str = "",
        original_text: str = "",
    ) -> dict[str, Any]:
        await self._remember_session(event)
        default_date, default_time = now_date_time()
        date_text = date_text or default_date
        time_text = time_text or default_time
        record_uid = _new_record_uid("diary")
        result = await self.writer.write_diary(
            date=date_text,
            time=time_text,
            content=content,
            category=category or "日记",
            mood=mood,
            record_uid=record_uid,
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self.db.add_life_event(
            event_session_id(event),
            date_text,
            time_text,
            category or "日记",
            content,
            record_uid=record_uid,
            mood=mood,
            markdown_path=result.get("path"),
        )
        await self._remember_write(
            event,
            action_type="diary",
            trigger=trigger,
            result=result,
            original_text=original_text or content,
        )
        return result

    async def _write_note(
        self,
        event: AstrMessageEvent,
        *,
        note_type: str,
        title: str,
        content: str,
        date_text: str | None = None,
        time_text: str | None = None,
        trigger: str = "",
        original_text: str = "",
    ) -> dict[str, Any]:
        await self._remember_session(event)
        default_date, default_time = now_date_time()
        date_text = date_text or default_date
        time_text = time_text or default_time
        category = normalize_note_category(note_type)
        storage_title = _storage_note_title(category, date_text, title)
        record_uid = _new_record_uid("note")
        polished = None
        if self.config.auto_polish:
            polished = await self._get_llm(
                event_session_id(event),
                prompts.POLISH_NOTE_PROMPT.format(note_type=category, title=title, content=content),
            )
        write_content = polished or content
        result = await self.writer.write_note(
            date=date_text,
            time=time_text,
            title=storage_title,
            content=write_content,
            original_content=content if polished else None,
            category=category,
            record_uid=record_uid,
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self.db.add_life_note(
            event_session_id(event),
            date_text,
            time_text,
            category,
            title,
            content,
            record_uid=record_uid,
            polished_content=polished,
            markdown_path=result.get("path"),
        )
        await self._remember_write(
            event,
            action_type="note",
            trigger=trigger,
            result=result,
            original_text=original_text or content,
        )
        return result

    async def _record_finance(
        self,
        event: AstrMessageEvent,
        *,
        amount: float,
        direction: str,
        category: str,
        note: str,
        merchant: str | None = None,
        wallet: str | None = None,
        counterparty: str | None = None,
        status: str = "已记录",
        date_text: str | None = None,
        time_text: str | None = None,
        trigger: str = "",
        original_text: str = "",
    ) -> dict[str, Any]:
        await self._remember_session(event)
        default_date, default_time = now_date_time()
        date_text = date_text or default_date
        time_text = time_text or default_time
        use_direction = _normalize_finance_direction(direction)
        use_category = category or infer_finance_category(note or merchant or "")
        record_uid = _new_record_uid("fin")
        result = await self.writer.write_finance(
            date=date_text,
            time=time_text,
            amount=amount,
            direction=use_direction,
            category=use_category,
            note=note,
            merchant=merchant,
            wallet=wallet,
            counterparty=counterparty,
            status=status,
            record_uid=record_uid,
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self.db.add_finance_record(
            event_session_id(event),
            date_text,
            time_text,
            amount,
            use_direction,
            use_category,
            merchant=merchant,
            note=note,
            wallet=wallet,
            counterparty=counterparty,
            status=status,
            record_uid=record_uid,
            markdown_path=result.get("path"),
        )
        await self._remember_write(
            event,
            action_type="finance",
            trigger=trigger,
            result=result,
            original_text=original_text or note,
        )
        return result

    async def _query_finance(self, event: AstrMessageEvent, query_type: str) -> str:
        if not self.config.enable_finance:
            return "记账功能已关闭。"
        await self._remember_session(event)
        session_id = event_session_id(event)
        today = date.today()

        if query_type == "today":
            start = end = today
            title = "今日财务"
            records = await self.db.query_finance_records(session_id, start_date=_date_text(start), end_date=_date_text(end), limit=50)
            return _format_finance_overview(title, records, currency_symbol=self.config.currency_symbol)

        if query_type == "week":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            records = await self.db.query_finance_records(session_id, start_date=_date_text(start), end_date=_date_text(end), limit=100)
            return _format_finance_overview("本周财务", records, currency_symbol=self.config.currency_symbol)

        if query_type == "loan":
            records = await self.db.query_finance_records(
                session_id,
                directions=("借入", "借出", "还款", "收款"),
                limit=300,
            )
            return _format_loan_summary(records, currency_symbol=self.config.currency_symbol)

        if query_type == "wallet":
            records = await self.db.query_finance_records(session_id, limit=500)
            return _format_wallet_summary(records, currency_symbol=self.config.currency_symbol)

        if query_type == "budget":
            start = today.replace(day=1)
            next_month = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
            end = next_month - timedelta(days=1)
            records = await self.db.query_finance_records(session_id, start_date=_date_text(start), end_date=_date_text(end), limit=500)
            return _format_budget_summary(records, monthly_budget=self.config.monthly_budget, currency_symbol=self.config.currency_symbol)

        if query_type in {"week_report", "month_report"}:
            if query_type == "week_report":
                start = today - timedelta(days=today.weekday())
                end = start + timedelta(days=6)
                title = "财务周报"
            else:
                start = today.replace(day=1)
                next_month = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
                end = next_month - timedelta(days=1)
                title = "财务月报"
            records = await self.db.query_finance_records(session_id, start_date=_date_text(start), end_date=_date_text(end), limit=500)
            return _format_finance_report(
                title,
                records,
                monthly_budget=self.config.monthly_budget if query_type == "month_report" else 0.0,
                currency_symbol=self.config.currency_symbol,
            )

        start = today.replace(day=1)
        next_month = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        end = next_month - timedelta(days=1)
        records = await self.db.query_finance_records(session_id, start_date=_date_text(start), end_date=_date_text(end), limit=200)
        return _format_finance_overview(
            "本月财务",
            records,
            monthly_budget=self.config.monthly_budget,
            currency_symbol=self.config.currency_symbol,
        )

    async def _cancel_finance(self, event: AstrMessageEvent, keyword: str) -> str:
        if not self.config.enable_finance:
            return "记账功能已关闭。"
        await self._remember_session(event)
        record = await self.db.cancel_finance_by_keyword(event_session_id(event), keyword)
        if not record:
            return f"没有找到匹配的账目：{keyword}"

        _, time_text = now_date_time()
        title = _finance_record_title(record)
        result = await self.writer.write_finance_status(
            date=str(record["record_date"]),
            time=time_text,
            title=title,
            status="作废",
            note=f"匹配关键词：{keyword}",
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self._remember_write(
            event,
            action_type="finance_status",
            trigger="作废账目",
            result=result,
            original_text=json.dumps({"record_id": record.get("id"), "keyword": keyword}, ensure_ascii=False),
        )
        return f"已作废账目：{title}"

    async def _update_finance(self, event: AstrMessageEvent, keyword: str, new_content: str) -> str:
        candidate = classify_auto_record(new_content, mode=self.config.auto_record_mode)
        if not candidate:
            candidate = classify_auto_record(f"记账 {new_content}", mode=self.config.auto_record_mode)
        if not candidate or candidate.kind != "finance" or candidate.amount is None:
            return "新账目没有识别成功。用法：修改账目 午饭 为 支出 午饭10元 支付宝"

        cancel_reply = await self._cancel_finance(event, keyword)
        if not cancel_reply.startswith("已作废账目"):
            return cancel_reply

        result = await self._record_finance(
            event,
            amount=float(candidate.amount),
            direction=candidate.direction or "支出",
            category=candidate.category or infer_finance_category(candidate.note),
            note=candidate.note,
            wallet=candidate.wallet,
            counterparty=candidate.counterparty,
            date_text=candidate.date,
            time_text=candidate.time,
            trigger="修改账目",
            original_text=new_content,
        )
        return f"{cancel_reply}\n{self._format_auto_record_reply('账目', result)}"

    async def _record_plan(self, event: AstrMessageEvent, intent: AutoRecordIntent) -> dict[str, Any]:
        await self._remember_session(event)
        default_date, default_time = now_date_time()
        created_date = default_date
        created_time = default_time
        target_date = intent.date
        target_time = intent.time
        plan_scope = intent.plan_scope or ("短期" if target_date else "其它")
        priority = intent.priority or "中"
        title = intent.title or truncate(intent.content, 30)
        record_uid = _new_record_uid("plan")
        result = await self.writer.write_plan(
            date=created_date,
            time=created_time,
            title=title,
            content=intent.content,
            plan_scope=plan_scope,
            priority=priority,
            status="未开始",
            target_date=target_date,
            target_time=target_time,
            record_uid=record_uid,
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self.db.add_plan(
            event_session_id(event),
            created_date,
            created_time,
            title,
            intent.content,
            plan_scope,
            priority,
            status="未开始",
            target_date=target_date,
            target_time=target_time,
            record_uid=record_uid,
            markdown_path=result.get("path"),
        )
        await self._remember_write(
            event,
            action_type="plan",
            trigger=intent.trigger,
            result=result,
            original_text=intent.content,
        )
        return result

    async def _record_reminder(self, event: AstrMessageEvent, intent: AutoRecordIntent) -> dict[str, Any]:
        await self._remember_session(event)
        created_date, created_time = now_date_time()
        due_date = intent.date
        due_time = intent.time
        due_text = " ".join(part for part in (due_date, due_time) if part) or "未设置"
        title = intent.title or truncate(intent.content, 30)
        record_uid = _new_record_uid("rem")
        content = (
            f"截止时间：{due_text}\n\n"
            f"{intent.content}"
        )
        result = await self.writer.write_note(
            date=created_date,
            time=created_time,
            title=_storage_note_title("备忘录", created_date, title),
            content=content,
            original_content=None,
            category="备忘录",
            record_uid=record_uid,
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self.db.add_reminder(
            event_session_id(event),
            created_date,
            created_time,
            title,
            intent.content,
            due_date=due_date,
            due_time=due_time,
            record_uid=record_uid,
            markdown_path=result.get("path"),
        )
        await self._remember_write(
            event,
            action_type="reminder",
            trigger=intent.trigger,
            result=result,
            original_text=intent.content,
        )
        return result

    async def _query_reminders(self, event: AstrMessageEvent, query_type: str) -> str:
        await self._remember_session(event)
        session_id = event_session_id(event)
        today = date.today()
        if query_type == "today":
            records = await self.db.query_reminders(
                session_id,
                start_date=_date_text(today),
                end_date=_date_text(today),
                include_undated=False,
                limit=30,
            )
            return _format_reminder_list("今日备忘", records)
        if query_type == "soon":
            end = today + timedelta(days=7)
            records = await self.db.query_reminders(
                session_id,
                start_date=_date_text(today),
                end_date=_date_text(end),
                include_undated=False,
                limit=50,
            )
            return _format_reminder_list("近期备忘", records)
        records = await self.db.query_reminders(session_id, limit=50)
        return _format_reminder_list("我的备忘", records)

    async def _query_todos(self, event: AstrMessageEvent, query_type: str) -> str:
        await self._remember_session(event)
        session_id = event_session_id(event)
        today = date.today()
        if query_type == "today":
            reminders = await self.db.query_reminders(
                session_id,
                start_date=_date_text(today),
                end_date=_date_text(today),
                include_undated=False,
                limit=30,
            )
            plans = await self.db.query_plans(session_id, target_date=_date_text(today), limit=20)
            return _format_todo_list("今日待办", reminders, plans)
        if query_type == "soon":
            end = today + timedelta(days=7)
            reminders = await self.db.query_reminders(
                session_id,
                start_date=_date_text(today),
                end_date=_date_text(end),
                include_undated=False,
                limit=50,
            )
            plans = await self.db.query_plans(
                session_id,
                scopes=("短期",),
                start_date=_date_text(today),
                end_date=_date_text(end),
                limit=30,
            )
            return _format_todo_list("近期待办", reminders, plans)
        reminders = await self.db.query_reminders(session_id, limit=50)
        plans = await self.db.query_plans(session_id, limit=50)
        return _format_todo_list("我的待办", reminders, plans)

    async def _cancel_plan(self, event: AstrMessageEvent, keyword: str) -> str:
        if not self.config.enable_plans:
            return "计划功能已关闭。"
        await self._remember_session(event)
        plan = await self.db.cancel_plan_by_keyword(event_session_id(event), keyword)
        if not plan:
            return f"没有找到匹配的未完成计划：{keyword}"

        date_text, time_text = now_date_time()
        result = await self.writer.write_plan_status(
            date=date_text,
            time=time_text,
            title=str(plan["title"]),
            status="已取消",
            note=f"匹配关键词：{keyword}",
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self._remember_write(
            event,
            action_type="plan_status",
            trigger="取消计划",
            result=result,
            original_text=json.dumps(
                {
                    "plan_id": plan.get("id"),
                    "previous_status": plan.get("previous_status") or "未开始",
                    "keyword": keyword,
                },
                ensure_ascii=False,
            ),
        )
        return f"已取消计划：{plan['title']}"

    async def _update_plan(self, event: AstrMessageEvent, keyword: str, new_content: str) -> str:
        candidate = classify_auto_record(f"计划 {new_content}", mode=self.config.auto_record_mode)
        if not candidate or candidate.kind != "plan":
            return "新计划没有识别成功。用法：修改计划 插件 为 明天 高优先级 整理插件配置"

        await self._remember_session(event)
        plan = await self.db.update_plan_by_keyword(
            event_session_id(event),
            keyword,
            title=candidate.title or truncate(candidate.content, 30),
            content=candidate.content,
            plan_scope=candidate.plan_scope or ("短期" if candidate.date else "其它"),
            priority=candidate.priority or "中",
            target_date=candidate.date,
            target_time=candidate.time,
        )
        if not plan:
            return f"没有找到匹配的未完成计划：{keyword}"

        date_text, time_text = now_date_time()
        result = await self.writer.write_plan_status(
            date=date_text,
            time=time_text,
            title=str(plan["title"]),
            status="已修改",
            note=f"改为：{candidate.content}",
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self._remember_write(
            event,
            action_type="plan_status",
            trigger="修改计划",
            result=result,
            original_text=json.dumps(
                {
                    "plan_id": plan.get("id"),
                    "previous_status": plan.get("status") or "未开始",
                    "keyword": keyword,
                    "new_content": candidate.content,
                },
                ensure_ascii=False,
            ),
        )
        return f"已修改计划：{plan['title']} -> {candidate.title}"

    async def _complete_plan(self, event: AstrMessageEvent, keyword: str) -> str:
        if not self.config.enable_plans:
            return "计划功能已关闭。"
        await self._remember_session(event)
        plan = await self.db.complete_plan_by_keyword(event_session_id(event), keyword)
        if not plan:
            return f"没有找到匹配的未完成计划：{keyword}"

        date_text, time_text = now_date_time()
        result = await self.writer.write_plan_status(
            date=date_text,
            time=time_text,
            title=str(plan["title"]),
            status="已完成",
            note=f"匹配关键词：{keyword}",
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self._remember_write(
            event,
            action_type="plan_status",
            trigger="完成计划",
            result=result,
            original_text=json.dumps(
                {
                    "plan_id": plan.get("id"),
                    "previous_status": plan.get("previous_status") or "未开始",
                    "keyword": keyword,
                },
                ensure_ascii=False,
            ),
        )
        return f"已完成计划：{plan['title']}"

    async def _start_plan(self, event: AstrMessageEvent, keyword: str) -> str:
        if not self.config.enable_plans:
            return "计划功能已关闭。"
        await self._remember_session(event)
        plan = await self.db.start_plan_by_keyword(event_session_id(event), keyword)
        if not plan:
            return f"没有找到匹配的未完成计划：{keyword}"

        date_text, time_text = now_date_time()
        result = await self.writer.write_plan_status(
            date=date_text,
            time=time_text,
            title=str(plan["title"]),
            status="进行中",
            note=f"匹配关键词：{keyword}",
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self._remember_write(
            event,
            action_type="plan_status",
            trigger="开始计划",
            result=result,
            original_text=json.dumps(
                {
                    "plan_id": plan.get("id"),
                    "previous_status": plan.get("previous_status") or "未开始",
                    "keyword": keyword,
                },
                ensure_ascii=False,
            ),
        )
        return f"已标记进行中：{plan['title']}"

    async def _postpone_plan(self, event: AstrMessageEvent, intent: AutoRecordIntent) -> str:
        if not self.config.enable_plans:
            return "计划功能已关闭。"
        if not intent.date and not intent.time:
            return "请给出推迟后的日期或时间。用法：推迟计划 整理宿舍 到 明天"
        await self._remember_session(event)
        plan = await self.db.postpone_plan_by_keyword(
            event_session_id(event),
            intent.content,
            target_date=intent.date,
            target_time=intent.time,
            note=intent.note,
        )
        if not plan:
            return f"没有找到匹配的未完成计划：{intent.content}"

        date_text, time_text = now_date_time()
        target = " ".join(part for part in (intent.date, intent.time) if part) or "未定"
        result = await self.writer.write_plan_status(
            date=date_text,
            time=time_text,
            title=str(plan["title"]),
            status="已推迟",
            note=f"推迟到：{target}",
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self._remember_write(
            event,
            action_type="plan_status",
            trigger="推迟计划",
            result=result,
            original_text=json.dumps(
                {
                    "plan_id": plan.get("id"),
                    "previous_status": plan.get("previous_status") or "未开始",
                    "keyword": intent.content,
                    "target": target,
                },
                ensure_ascii=False,
            ),
        )
        return f"已推迟计划：{plan['title']} -> {target}"

    async def _review_plans(self, event: AstrMessageEvent) -> str:
        if not self.config.enable_plans:
            return "计划功能已关闭。"
        await self._remember_session(event)
        session_id = event_session_id(event)
        today = date.today()
        today_text = _date_text(today)
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        today_plans = await self.db.query_plans(session_id, target_date=today_text, include_completed=True, limit=50)
        week_plans = await self.db.query_plans(
            session_id,
            scopes=("短期",),
            start_date=_date_text(week_start),
            end_date=_date_text(week_end),
            include_completed=True,
            limit=100,
        )
        overdue = await self.db.query_plans(
            session_id,
            scopes=("短期",),
            end_date=_date_text(today - timedelta(days=1)),
            limit=20,
        )
        long_term = await self.db.query_plans(session_id, scopes=("长期",), limit=5)
        return _format_plan_review(today_plans=today_plans, week_plans=week_plans, overdue=overdue, long_term=long_term)

    async def _query_plans(self, event: AstrMessageEvent, query_type: str) -> str:
        if not self.config.enable_plans:
            return "计划功能已关闭。"
        await self._remember_session(event)
        today = date.today()
        session_id = event_session_id(event)
        if query_type == "today":
            plans = await self.db.query_plans(session_id, target_date=today.strftime("%Y-%m-%d"), limit=20)
            title = "今日计划"
        elif query_type == "week":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            plans = await self.db.query_plans(
                session_id,
                scopes=("短期",),
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                limit=30,
            )
            title = "本周计划"
        elif query_type == "month":
            start = today.replace(day=1)
            next_month = (start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1))
            end = next_month - timedelta(days=1)
            plans = await self.db.query_plans(
                session_id,
                scopes=("短期",),
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                limit=50,
            )
            title = "本月计划"
        elif query_type == "long_term":
            plans = await self.db.query_plans(session_id, scopes=("长期",), limit=30)
            title = "长期计划"
        elif query_type == "free":
            plans = await self.db.query_plans(session_id, scopes=("其它",), limit=20)
            title = "空闲计划"
        else:
            plans = await self.db.query_plans(session_id, limit=30)
            title = "我的计划"
        return _format_plan_list(title, plans)

    async def _record_health(self, event: AstrMessageEvent, intent: AutoRecordIntent) -> dict[str, Any]:
        await self._remember_session(event)
        default_date, default_time = now_date_time()
        date_text = intent.date or default_date
        time_text = intent.time or default_time
        metric_type = intent.category or "健康"
        record_uid = _new_record_uid("health")
        result = await self.writer.write_health(
            date=date_text,
            time=time_text,
            metric_type=metric_type,
            value=intent.value,
            unit=intent.unit,
            duration_minutes=intent.duration_minutes,
            distance_km=intent.distance_km,
            status="已记录",
            record_uid=record_uid,
            note=intent.note,
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )
        await self.db.add_health_record(
            event_session_id(event),
            date_text,
            time_text,
            metric_type,
            value=intent.value,
            unit=intent.unit,
            duration_minutes=intent.duration_minutes,
            distance_km=intent.distance_km,
            note=intent.note,
            status="已记录",
            record_uid=record_uid,
            markdown_path=result.get("path"),
        )
        await self._remember_write(
            event,
            action_type="health",
            trigger=intent.trigger,
            result=result,
            original_text=intent.content,
        )
        return result

    async def _query_health(self, event: AstrMessageEvent, query_type: str) -> str:
        if not self.config.enable_health:
            return "健康记录功能已关闭。"
        await self._remember_session(event)
        session_id = event_session_id(event)
        today = date.today()
        if query_type == "today":
            start = end = today
            title = "今日健康"
        elif query_type == "week":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            title = "本周健康"
        else:
            start = today.replace(day=1)
            next_month = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
            end = next_month - timedelta(days=1)
            title = "本月健康"
        records = await self.db.query_health_records(
            session_id,
            start_date=_date_text(start),
            end_date=_date_text(end),
            limit=200,
        )
        return _format_health_overview(title, records)

    async def _build_briefing_context(self, session_id: str, date_text: str) -> str:
        today_reminders = await self.db.query_reminders(
            session_id,
            start_date=date_text,
            end_date=date_text,
            include_undated=False,
            limit=5,
        )
        rows: list[tuple[str, str]] = []
        if today_reminders:
            rows.extend((item["title"], item.get("due_time") or "") for item in today_reminders[:5])
        if not rows:
            return "| 内容 | 时间 |\n|---|---|\n| 暂无今日备忘 | |"
        lines = ["| 内容 | 时间 |", "|---|---|"]
        lines.extend(f"| {title} | {time} |" for title, time in rows[:10])
        return "\n".join(lines)

    async def _generate_briefing(self, event: AstrMessageEvent) -> str:
        await self._remember_session(event)
        return await self._generate_briefing_for_session(
            event_session_id(event),
            platform=event_platform(event),
            sender_id=event_sender_id(event),
            remember_event=event,
        )

    async def _generate_briefing_for_session(
        self,
        session_id: str,
        *,
        platform: str = "scheduler",
        sender_id: str = "scheduler",
        remember_event: AstrMessageEvent | None = None,
    ) -> str:
        if not self.config.enable_morning_briefing:
            return "晨报功能已关闭。"
        date_text, time_text = now_date_time()
        plan_context = await self._build_briefing_context(session_id, date_text)
        text = await generate_briefing_text(
            config=self.config,
            llm_call=lambda prompt: self._get_llm(session_id, prompt),
            plan_context=plan_context,
        )
        if self.config.write_briefing_to_obsidian:
            result = await self.writer.write_briefing(
                date=date_text,
                time=time_text,
                title=f"{date_text} 晨报",
                content=text,
                platform=platform,
                sender_id=sender_id,
            )
            await self.db.add_summary_job(session_id, date_text, "晨报", "synced", result.get("path"))
            await self._remember_write_by_session(
                session_id,
                action_type="briefing",
                trigger="晨报",
                result=result,
                original_text=text,
            )
        return text

    async def _generate_daily_summary(self, event: AstrMessageEvent, date_text: str | None = None) -> str:
        await self._remember_session(event)
        session_id = event_session_id(event)
        default_date, time_text = now_date_time()
        return await self._generate_daily_summary_for_session(
            session_id,
            date_text=date_text or default_date,
            time_text=time_text,
            platform=event_platform(event),
            sender_id=event_sender_id(event),
            remember_event=event,
        )

    async def _generate_daily_summary_for_session(
        self,
        session_id: str,
        *,
        date_text: str,
        time_text: str,
        platform: str = "scheduler",
        sender_id: str = "scheduler",
        remember_event: AstrMessageEvent | None = None,
    ) -> str:
        if not self.config.enable_daily_summary:
            return "日总结功能已关闭。"
        day_data = await self.db.query_day(session_id, date_text)
        day_data["summary_date"] = date_text
        target_day = datetime.strptime(date_text, "%Y-%m-%d").date()
        day_data["upcoming_reminders"] = await self.db.query_reminders(
            session_id,
            start_date=_date_text(target_day + timedelta(days=1)),
            end_date=_date_text(target_day + timedelta(days=2)),
            include_undated=False,
            limit=10,
        )
        if self.config.enable_finance:
            week_start = target_day - timedelta(days=target_day.weekday())
            week_end = week_start + timedelta(days=6)
            month_start = target_day.replace(day=1)
            next_month = month_start.replace(year=month_start.year + 1, month=1) if month_start.month == 12 else month_start.replace(month=month_start.month + 1)
            month_end = next_month - timedelta(days=1)
            week_records = await self.db.query_finance_records(
                session_id,
                start_date=_date_text(week_start),
                end_date=_date_text(week_end),
                limit=300,
            )
            month_records = await self.db.query_finance_records(
                session_id,
                start_date=_date_text(month_start),
                end_date=_date_text(month_end),
                limit=500,
            )
            day_data["finance_brief"] = [
                f"今日：{_brief_finance_line(day_data.get('finance') or [], self.config.currency_symbol)}",
                f"本周：{_brief_finance_line(week_records, self.config.currency_symbol)}",
                f"本月：{_brief_finance_line(month_records, self.config.currency_symbol, monthly_budget=self.config.monthly_budget)}",
            ]
            day_data["finance_summary"] = [
                _finance_summary_row("今日", day_data.get("finance") or [], self.config.currency_symbol),
                _finance_summary_row("本周", week_records, self.config.currency_symbol),
                _finance_summary_row("本月", month_records, self.config.currency_symbol),
            ]
        text, success = await generate_daily_summary_text(
            day_data=day_data,
            llm_call=lambda prompt: self._get_llm(session_id, prompt),
            include_conversations=self.config.include_conversations_in_summaries,
        )
        if success:
            result = await self.writer.write_summary(
                date=date_text,
                time=time_text,
                title=f"{date_text} 日总结",
                content=text,
                document_type="日总结",
                platform=platform,
                sender_id=sender_id,
            )
            await self.db.add_summary_job(session_id, date_text, "日总结", "synced", result.get("path"))
            if remember_event is not None:
                await self._remember_write(remember_event, action_type="summary", trigger="日总结", result=result, original_text=text)
            else:
                await self._remember_write_by_session(
                    session_id,
                    action_type="summary",
                    trigger="日总结",
                    result=result,
                    original_text=text,
                )
        return text

    async def _generate_diary_draft(self, event: AstrMessageEvent, date_text: str | None = None) -> str:
        await self._remember_session(event)
        session_id = event_session_id(event)
        default_date, time_text = now_date_time()
        date_text = date_text or default_date
        return await self._generate_diary_draft_for_session(
            session_id,
            date_text=date_text,
            time_text=time_text,
            platform=event_platform(event),
            sender_id=event_sender_id(event),
            remember_event=event,
        )

    async def _generate_diary_draft_for_session(
        self,
        session_id: str,
        *,
        date_text: str,
        time_text: str,
        platform: str = "scheduler",
        sender_id: str = "scheduler",
        remember_event: AstrMessageEvent | None = None,
    ) -> str:
        if not self.config.enable_daily_summary:
            return "日记草稿功能已关闭。"
        day_data = await self.db.query_day(session_id, date_text)
        text, success = await generate_diary_draft_text(
            day_data=day_data,
            llm_call=lambda prompt: self._get_llm(session_id, prompt),
            include_conversations=self.config.include_conversations_in_summaries,
        )
        if success:
            result = await self.writer.write_summary(
                date=date_text,
                time=time_text,
                title=f"{date_text} 日记草稿",
                content=text,
                document_type="日记草稿",
                platform=platform,
                sender_id=sender_id,
            )
            await self.db.add_summary_job(session_id, date_text, "日记草稿", "synced", result.get("path"))
            await self._remember_write_by_session(
                session_id,
                action_type="diary_draft",
                trigger="今日总结",
                result=result,
                original_text=text,
            )
        return text

    async def _generate_weekly_summary(self, event: AstrMessageEvent) -> str:
        await self._remember_session(event)
        today = date.today()
        start = today - timedelta(days=today.weekday())
        return await self._generate_weekly_summary_for_session(
            event_session_id(event),
            start_date=start.strftime("%Y-%m-%d"),
            end_date=today.strftime("%Y-%m-%d"),
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )

    async def _generate_weekly_summary_for_session(
        self,
        session_id: str,
        *,
        start_date: str,
        end_date: str,
        platform: str = "scheduler",
        sender_id: str = "scheduler",
    ) -> str:
        if not self.config.enable_daily_summary:
            return "周报功能已关闭。"
        range_data = await self.db.query_range(session_id, start_date, end_date)
        text, success = await generate_weekly_summary_text(
            range_data=range_data,
            llm_call=lambda prompt: self._get_llm(session_id, prompt),
        )
        if success:
            _, time_text = now_date_time()
            result = await self.writer.write_summary(
                date=end_date,
                time=time_text,
                title=f"{start_date} 至 {end_date} 周报",
                content=text,
                document_type="周报",
                platform=platform,
                sender_id=sender_id,
            )
            await self.db.add_summary_job(session_id, end_date, "周报", "synced", result.get("path"))
            await self._remember_write_by_session(
                session_id,
                action_type="weekly_summary",
                trigger="周报",
                result=result,
                original_text=text,
            )
        return text

    async def _generate_quote_weekly(self, event: AstrMessageEvent) -> str:
        await self._remember_session(event)
        today = date.today()
        start = today - timedelta(days=today.weekday())
        return await self._generate_quote_weekly_for_session(
            event_session_id(event),
            start_date=start.strftime("%Y-%m-%d"),
            end_date=today.strftime("%Y-%m-%d"),
            platform=event_platform(event),
            sender_id=event_sender_id(event),
        )

    async def _generate_quote_weekly_for_session(
        self,
        session_id: str,
        *,
        start_date: str,
        end_date: str,
        platform: str = "scheduler",
        sender_id: str = "scheduler",
    ) -> str:
        if not self.config.enable_notes:
            return "语录笔记功能已关闭。"
        notes = await self.db.get_notes_by_category(
            session_id,
            "语录笔记",
            start_date=start_date,
            end_date=end_date,
            limit=100,
        )
        text, success = await generate_quote_weekly_text(
            notes=notes,
            llm_call=lambda prompt: self._get_llm(session_id, prompt),
        )
        if success:
            _, time_text = now_date_time()
            result = await self.writer.write_summary(
                date=end_date,
                time=time_text,
                title=f"{start_date} 至 {end_date} 语录周精选",
                content=text,
                document_type="语录周精选",
                platform=platform,
                sender_id=sender_id,
            )
            await self.db.add_summary_job(session_id, end_date, "语录周精选", "synced", result.get("path"))
            await self._remember_write_by_session(
                session_id,
                action_type="quote_weekly",
                trigger="语录周精选",
                result=result,
                original_text=text,
            )
        return text

    async def _save_confirmation_request(self, event: AstrMessageEvent, intent: AutoRecordIntent) -> str:
        pending_text = intent.pending_text or event_message_text(event)
        candidates = build_confirmation_candidate_intents(pending_text, mode=self.config.auto_record_mode)
        if not candidates:
            return intent.content

        summary = _format_pending_intents(candidates)
        await self.db.add_pending_action(
            event_session_id(event),
            action_type="auto_record",
            summary=summary,
            payload_json=json.dumps([asdict(candidate) for candidate in candidates], ensure_ascii=False),
            ttl_minutes=10,
        )
        return (
            f"{intent.content}\n\n"
            "我先不直接写入。我的拆分理解是：\n"
            f"{summary}\n\n"
            "回复“确认”写入，回复“取消”放弃。10 分钟内有效。"
        )

    async def _confirm_pending_action(self, event: AstrMessageEvent) -> str:
        await self._remember_session(event)
        pending = await self.db.get_pending_action(event_session_id(event))
        if not pending:
            return "没有待确认的写入。"

        try:
            payload = json.loads(str(pending.get("payload_json") or "[]"))
            intents = [_intent_from_dict(item) for item in payload]
        except (TypeError, ValueError, json.JSONDecodeError):
            await self.db.resolve_pending_action(int(pending["id"]), "failed")
            return "待确认内容已经损坏，请用固定触发词重新发送。"

        replies: list[str] = []
        for candidate in intents:
            if candidate.kind in {"confirm_pending", "cancel_pending", "needs_confirmation"}:
                continue
            reply = await self._handle_auto_record_intent(event, candidate)
            if reply:
                replies.append(reply)
        await self.db.resolve_pending_action(int(pending["id"]), "confirmed")
        if not replies:
            return "已确认，但没有可执行的写入内容。"
        return "已确认写入：\n" + _compact_reply_lines(replies)

    async def _cancel_pending_action(self, event: AstrMessageEvent) -> str:
        await self._remember_session(event)
        pending = await self.db.get_pending_action(event_session_id(event))
        if not pending:
            return "没有待取消的写入。"
        await self.db.resolve_pending_action(int(pending["id"]), "cancelled")
        return "已取消这次待确认写入。"

    async def _system_status(self, event: AstrMessageEvent) -> str:
        await self._remember_session(event)
        session_id = event_session_id(event)
        counts = await self.db.record_counts(session_id)
        pending_count = await self.db.count_pending_actions(session_id)

        writer_line = "writer：未知"
        git_line = "Git：未知"
        try:
            health = await self.writer.health()
            writer_line = f"writer：正常（{health.get('service', 'obsidian-inbox-writer')}）"
        except Exception as exc:
            writer_line = f"writer：异常（{safe_error_text(exc)}）"

        try:
            git_status = await self.writer.git_status()
            head = str(git_status.get("head") or "")[:8] or "unknown"
            dirty = "有未提交改动" if git_status.get("status") else "干净"
            git_line = f"Git：{dirty}，HEAD {head}"
        except Exception as exc:
            git_line = f"Git：无法读取（{safe_error_text(exc)}）"

        enabled_parts = [
            "自动记录" if self.config.enable_auto_record else "",
            "原生提醒桥接" if self.config.enable_native_future_task_bridge else "",
            "计划" if self.config.enable_plans else "",
            "财务" if self.config.enable_finance else "",
            "健康" if self.config.enable_health else "",
            "定时任务" if self.config.enable_scheduler else "",
        ]
        enabled_text = "、".join(part for part in enabled_parts if part) or "无"
        count_text = "，".join(f"{key}{value}" for key, value in counts.items())
        return (
            f"{self.config.assistant_display_name}状态\n"
            f"{writer_line}\n"
            f"{git_line}\n"
            f"功能：{enabled_text}\n"
            f"待确认：{pending_count}\n"
            f"本会话索引：{count_text}"
        )

    async def _recover_index(self, event: AstrMessageEvent) -> str:
        await self._remember_session(event)
        try:
            response = await self.writer.recovery_index()
        except Exception as exc:
            return f"恢复索引失败：{safe_error_text(exc)}"

        records = response.get("records") or {}
        stats = await self.db.import_recovery_records(event_session_id(event), records)
        legacy = _count_recovery_records(records) - sum(bucket["imported"] + bucket["skipped"] for bucket in stats.values())
        lines = ["索引恢复完成"]
        labels = {"finance": "财务", "plans": "计划", "health": "健康"}
        for key, label in labels.items():
            bucket = stats.get(key, {"imported": 0, "skipped": 0})
            lines.append(f"- {label}：导入 {bucket['imported']}，跳过 {bucket['skipped']}")
        if legacy > 0:
            lines.append(f"- 旧格式无 ID 记录：{legacy}（保持原样，不强行导入）")
        return "\n".join(lines)

    def _help_text(self, topic: str = "all") -> str:
        help_map = {
            "finance": (
                "记账帮助\n"
                "记录：记账 / 支出 / 收入 / 借入 / 借出 / 还款 / 收款 / 转账\n"
                "查询：今日财务 / 本周财务 / 本月财务 / 借贷情况 / 钱包统计 / 预算情况\n"
                "修正：撤销上一条 / 作废账目 ... / 修改账目 ...\n\n"
                "示例：\n"
                "支出 午饭9元 支付宝\n"
                "借出 给张三100元 微信\n"
                "修改账目 午饭 为 支出 午饭10元 支付宝"
            ),
            "plan": (
                "计划帮助\n"
                "记录：计划 / 备忘 / DDL\n"
                "查询：今日计划 / 本周计划 / 本月计划 / 长期计划 / 空闲计划\n"
                "闭环：开始计划 / 完成计划 / 推迟计划 / 取消计划 / 修改计划 / 计划复盘\n\n"
                "示例：\n"
                "计划 明天 整理插件配置\n"
                "备忘 明天 20:00 交材料\n"
                "完成计划 插件配置"
            ),
            "health": (
                "健康帮助\n"
                "记录：体重 / 跑步 / 睡眠 / 健身 / 运动\n"
                "查询：今日健康 / 本周健康 / 本月健康 / 健康概览\n\n"
                "示例：\n"
                "体重 75.5kg\n"
                "跑步 5公里 30分钟\n"
                "睡眠 7.5小时"
            ),
            "summary": (
                "报告帮助\n"
                "晨报\n"
                "今日总结 / 日记草稿\n"
                "周报 / 语录周精选\n"
                "推送到这里"
            ),
        }
        if topic in help_map:
            return help_map[topic]
        return (
            f"{self.config.assistant_display_name} 触发词\n\n"
            "【记录】\n"
            "记账 / 支出 / 收入 / 借入 / 借出 / 还款 / 收款 / 转账\n"
            "日记 / 记事 / 随想 / 语录 / 补记\n"
            "计划 / 备忘 / DDL\n"
            "体重 / 跑步 / 睡眠 / 健身\n\n"
            "【查询】\n"
            "今日财务 / 本周财务 / 本月财务 / 借贷情况 / 钱包统计\n"
            "今日计划 / 本周计划 / 本月计划 / 长期计划 / 空闲计划\n"
            "今日备忘 / 近期备忘\n"
            "今日健康 / 本周健康 / 本月健康\n\n"
            "【修正】\n"
            "撤销上一条\n"
            "改上一条 ...\n"
            "作废账目 ... / 修改账目 ...\n"
            "取消计划 ... / 修改计划 ...\n"
            "开始计划 ... / 完成计划 ... / 推迟计划 ...\n\n"
            "【报告】\n"
            "晨报\n"
            "今日总结 / 日记草稿\n"
            "周报 / 语录周精选\n\n"
            "【系统】\n"
            "Obsidian状态\n"
            "恢复索引\n"
            "推送到这里\n\n"
            "示例：\n"
            "支出 午饭9元 支付宝\n"
            "计划 明天 整理插件配置\n"
            "备忘 明天 20:00 交材料\n"
            "提醒我 明天 20:00 跑步"
        )

    async def _set_push_target(self, event: AstrMessageEvent) -> str:
        session_id = event_session_id(event)
        await self.db.set_setting("push_target_session", session_id)
        await self.db.set_setting("last_session_id", session_id)
        return "已把当前会话设为定时推送目标。"

    async def _undo_last_write(self, event: AstrMessageEvent) -> str:
        session_id = event_session_id(event)
        history = await self.db.get_last_active_write(session_id)
        if not history:
            return "没有找到可撤销的上一条写入。"

        commit_hash = str(history.get("commit_hash") or "")
        if not commit_hash:
            return "上一条写入没有可撤销的 Git commit。"

        await self.writer.revert_commit(commit_hash)
        if history.get("action_type") == "plan_status":
            await self._restore_plan_status_after_undo(history)
        await self.db.mark_write_undone(int(history["id"]))
        path = history.get("markdown_path") or "Obsidian"
        return f"已撤销上一条写入：{path}"

    async def _restore_plan_status_after_undo(self, history: dict[str, Any]) -> None:
        try:
            payload = json.loads(str(history.get("original_text") or "{}"))
            plan_id = int(payload["plan_id"])
            previous_status = str(payload.get("previous_status") or "未开始")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            logger.warning("ObsidianLifeHub could not restore plan status after undo")
            return
        await self.db.set_plan_status(plan_id, previous_status)

    async def _amend_last_write(self, event: AstrMessageEvent, new_content: str) -> str:
        intents = classify_auto_record_batch(new_content, mode=self.config.auto_record_mode)
        if not intents:
            return "新内容没有识别为可写入记录，上一条未撤销。请用固定触发词重发。"

        undo_reply = await self._undo_last_write(event)
        if not undo_reply.startswith("已撤销"):
            return undo_reply

        replies: list[str] = [undo_reply]
        for intent in intents:
            if intent.kind in {"undo", "amend"}:
                continue
            reply = await self._handle_auto_record_intent(event, intent)
            if reply:
                replies.append(reply)
        return "\n".join(replies)

    async def _remember_session(self, event: AstrMessageEvent) -> None:
        try:
            await self.db.set_setting("last_session_id", event_session_id(event))
        except Exception as exc:
            logger.warning(f"[ObsidianLifeHub] remember session failed: {safe_error_text(exc)}")

    async def _remember_write(
        self,
        event: AstrMessageEvent,
        *,
        action_type: str,
        trigger: str,
        result: dict[str, Any],
        original_text: str = "",
    ) -> None:
        await self._remember_write_by_session(
            event_session_id(event),
            action_type=action_type,
            trigger=trigger,
            result=result,
            original_text=original_text,
        )

    async def _remember_write_by_session(
        self,
        session_id: str,
        *,
        action_type: str,
        trigger: str,
        result: dict[str, Any],
        original_text: str = "",
    ) -> None:
        commit_hash = result.get("commit_hash")
        if not commit_hash:
            return
        await self.db.add_write_history(
            session_id=session_id,
            action_type=action_type,
            trigger=trigger,
            commit_hash=str(commit_hash),
            markdown_path=result.get("path"),
            original_text=truncate(original_text, 2000),
        )

    async def _scheduler_loop(self) -> None:
        await asyncio.sleep(5)
        while True:
            try:
                await self._run_scheduler_tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"[ObsidianLifeHub] scheduler tick failed: {safe_error_text(exc)}")
            await asyncio.sleep(30)

    async def _run_scheduler_tick(self) -> None:
        if not self.config.enabled or not self.config.enable_scheduler:
            return

        session_id = await self._scheduler_session_id()
        if not session_id:
            return

        now = datetime.now()
        today = date.today()
        date_text = today.strftime("%Y-%m-%d")
        time_text = now.strftime("%H:%M")

        if self._scheduled_now("morning", now, self.config.morning_briefing_time):
            text = await self._generate_briefing_for_session(session_id)
            await self._push_message(session_id, text, render_report=True)

        if self._scheduled_now("evening", now, self.config.evening_checkin_time):
            await self._push_message(session_id, "今天要不要总结？需要的话回复“今日总结”，我会整理待办、财务和日记草稿。")

        if self._scheduled_now("daily_summary", now, self.config.daily_summary_time):
            text = await self._generate_daily_summary_for_session(
                session_id,
                date_text=date_text,
                time_text=time_text,
            )
            await self._push_message(session_id, text, render_report=True)

        if self._scheduled_now("weekly", now, self.config.weekly_summary_time, weekly_day=self.config.weekly_summary_day):
            start = today - timedelta(days=today.weekday())
            start_text = start.strftime("%Y-%m-%d")
            quote_text = await self._generate_quote_weekly_for_session(
                session_id,
                start_date=start_text,
                end_date=date_text,
            )
            summary_text = await self._generate_weekly_summary_for_session(
                session_id,
                start_date=start_text,
                end_date=date_text,
            )
            await self._push_message(session_id, f"{quote_text}\n\n{summary_text}".strip(), render_report=True)

    async def _scheduler_session_id(self) -> str:
        configured = str(self.config.push_target_session or "").strip()
        if configured:
            return configured
        stored = await self.db.get_setting("push_target_session", "")
        if stored:
            return stored
        return await self.db.get_setting("last_session_id", "")

    def _scheduled_now(
        self,
        task_name: str,
        now: datetime,
        clock_text: str,
        *,
        weekly_day: int | None = None,
    ) -> bool:
        target = _parse_clock_time(clock_text)
        if target is None:
            return False
        if weekly_day is not None and now.isoweekday() != weekly_day:
            return False
        if (now.hour, now.minute) != target:
            return False

        key_prefix = now.strftime("%G-W%V") if weekly_day is not None else now.strftime("%Y-%m-%d")
        key = f"{key_prefix}:{task_name}"
        if key in self._scheduler_seen:
            return False
        self._scheduler_seen.add(key)
        if len(self._scheduler_seen) > 1000:
            self._scheduler_seen = set(sorted(self._scheduler_seen)[-500:])
        return True

    async def _push_message(self, session_id: str, text: str, *, render_report: bool = False) -> bool:
        if not session_id or not text:
            return False
        try:
            message = await self._build_push_message(text, render_report=render_report)
            await self.context.send_message(session_id, message)
            return True
        except Exception as exc:
            logger.warning(f"[ObsidianLifeHub] push message failed: {safe_error_text(exc)}")
            return False

    async def _build_push_message(self, text: str, *, render_report: bool = False):
        if not render_report:
            return _build_message_chain(text)

        image_message = await self._try_render_report_image(text)
        if image_message is not None:
            return image_message
        return _build_message_chain(f"\u200b{markdown_to_push_text(text)}\u200b")

    async def _try_render_report_image(self, text: str):
        try:
            renderer = getattr(self, "text_to_image", None)
            if not callable(renderer):
                return None
            try:
                image_url = renderer(text, return_url=True)
            except TypeError:
                image_url = renderer(text)
            if inspect.isawaitable(image_url):
                image_url = await image_url
            image_url = str(image_url or "").strip()
            if not image_url:
                return None
            return _build_image_message_chain(image_url)
        except Exception as exc:
            logger.warning(f"[ObsidianLifeHub] report image render failed, fallback to text: {safe_error_text(exc)}")
            return None

    async def _log_conversation(self, event: AstrMessageEvent, role: str):
        message = event_message_text(event)
        if not message:
            return
        if is_command_message(message, ALL_COMMANDS) or is_low_signal_life_message(message):
            return
        await self.db.add_conversation_log(event_session_id(event), role, truncate(message, 2000))

    async def _get_llm(self, session_id: str, prompt: str) -> str | None:
        try:
            provider_id = await self.context.get_current_chat_provider_id(session_id)
        except Exception:
            provider_id = None
        if not provider_id:
            return None
        try:
            response = await self.context.llm_generate(chat_provider_id=provider_id, prompt=prompt)
            text = getattr(response, "completion_text", "") or ""
            return text.strip() or None
        except Exception as exc:
            logger.warning(f"[ObsidianLifeHub] LLM failed: {exc}")
            return None

    def _is_unmentioned_group_message(self, event: AstrMessageEvent) -> bool:
        try:
            message_type = str(event.get_message_type()).lower()
        except Exception:
            return False
        if "group" not in message_type:
            return False
        return not bool(getattr(event, "is_at_or_wake_command", False))

    def _format_auto_record_reply(self, label: str, result: dict[str, Any]) -> str:
        path = result.get("path", "生活/")
        if self.config.reply_on_success:
            return f"已自动写入{label}：{path}"
        return f"{label}已自动记录。"

    def _format_write_reply(self, label: str, result: dict[str, Any]) -> str:
        path = result.get("path", "生活/")
        if self.config.reply_on_success:
            return f"已写入{label}：{path}"
        return f"{label}已记录。"

    def _format_inbox_reply(self, result: dict[str, Any]) -> str:
        path = result.get("path", "raw/inbox")
        category = result.get("category", "随手记")
        if self.config.reply_on_success:
            return f"已写入 Inbox：{path}（{category}）"
        return "Inbox 已记录。"

    async def terminate(self):
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        self.db.close()
        logger.info("[ObsidianLifeHub] plugin terminated")


def _plan_query_from_message(message: str) -> str:
    text = str(message or "")
    if "计划清单" in text or "所有计划" in text or "我的计划" in text:
        return "all"
    if "今日计划" in text:
        return "today"
    if "本周计划" in text:
        return "week"
    if "本月计划" in text:
        return "month"
    if "长期计划" in text:
        return "long_term"
    if "空闲计划" in text:
        return "free"
    return "all"


def _finance_query_from_message(message: str) -> str:
    text = str(message or "")
    if "今日财务" in text:
        return "today"
    if "本周财务" in text:
        return "week"
    if "财务周报" in text:
        return "week_report"
    if "财务月报" in text:
        return "month_report"
    if "借贷情况" in text:
        return "loan"
    if "钱包统计" in text:
        return "wallet"
    if "预算情况" in text:
        return "budget"
    return "month"


def _finance_trigger_from_message(message: str) -> str:
    text = str(message or "").lstrip("/")
    for trigger in ("借入", "借出", "还款", "收款", "转账", "支出", "收入", "记账", "账目"):
        if text.startswith(trigger):
            return trigger
    return "记账"


def _direction_from_finance_trigger(trigger: str) -> str | None:
    mapping = {
        "支出": "支出",
        "收入": "收入",
        "借入": "借入",
        "借出": "借出",
        "还款": "还款",
        "收款": "收款",
        "转账": "转账",
    }
    return mapping.get(trigger)


def _normalize_finance_direction(direction: str) -> str:
    text = str(direction or "").strip()
    if text in {"支出", "收入", "借入", "借出", "还款", "收款", "转账"}:
        return text
    return "收入" if text == "income" else "支出"


def _finance_category_for(direction: str, note: str) -> str:
    if direction in {"借入", "借出", "还款", "收款"}:
        return "借贷"
    if direction == "转账":
        return "转账"
    return infer_finance_category(note)


def _date_text(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _new_record_uid(prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _count_recovery_records(records: dict[str, list[dict[str, Any]]]) -> int:
    return sum(len(items) for items in records.values() if isinstance(items, list))


def _format_finance_overview(
    title: str,
    records: list[dict[str, Any]],
    *,
    monthly_budget: float = 0.0,
    currency_symbol: str = "¥",
) -> str:
    if not records:
        return f"{title}\n暂无财务记录。"

    totals = _totals_by_direction(records)
    category_totals = _totals_by_key([item for item in records if item.get("direction") == "支出"], "category")
    expense_total = totals.get("支出", 0)
    lines = [
        title,
        (
            f"收入 {currency_symbol}{totals.get('收入', 0):.2f}，支出 {currency_symbol}{expense_total:.2f}，"
            f"借入 {currency_symbol}{totals.get('借入', 0):.2f}，借出 {currency_symbol}{totals.get('借出', 0):.2f}，"
            f"还款 {currency_symbol}{totals.get('还款', 0):.2f}，收款 {currency_symbol}{totals.get('收款', 0):.2f}"
        ),
    ]
    transfer = totals.get("转账", 0)
    if transfer:
        lines.append(f"转账流水 {currency_symbol}{transfer:.2f}")
    if monthly_budget > 0:
        remaining = monthly_budget - expense_total
        rate = min(max(expense_total / monthly_budget, 0), 9.99)
        lines.append(f"预算进度：{currency_symbol}{expense_total:.2f} / {currency_symbol}{monthly_budget:.2f}（{rate:.0%}），剩余 {currency_symbol}{remaining:.2f}")
    if category_totals:
        top_categories = "，".join(
            f"{category} {currency_symbol}{amount:.2f}" for category, amount in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)[:5]
        )
        lines.append(f"支出分类：{top_categories}")
    lines.append("最近明细：")
    for item in records[:8]:
        wallet = f"｜{item.get('wallet')}" if item.get("wallet") else ""
        counterparty = f"｜{item.get('counterparty')}" if item.get("counterparty") else ""
        status = "" if item.get("status") in {"", None, "已记录"} else f"｜{item.get('status')}"
        uid = f" #{item.get('record_uid')}" if item.get("record_uid") else ""
        lines.append(
            f"- {item['record_date']} {item['record_time']} {item['direction']} {currency_symbol}{float(item['amount']):.2f} "
            f"[{item['category']}{wallet}{counterparty}{status}] {item.get('note') or ''}{uid}"
        )
    return "\n".join(lines)


def _format_budget_summary(
    records: list[dict[str, Any]],
    *,
    monthly_budget: float = 0.0,
    currency_symbol: str = "¥",
) -> str:
    expense_total = sum(float(item.get("amount") or 0) for item in records if item.get("direction") == "支出")
    lines = ["预算情况"]
    if monthly_budget <= 0:
        lines.append("当前未设置月预算。可在插件配置中设置 monthly_budget。")
        lines.append(f"本月已记录支出：{currency_symbol}{expense_total:.2f}")
        return "\n".join(lines)
    remaining = monthly_budget - expense_total
    rate = min(max(expense_total / monthly_budget, 0), 9.99)
    lines.append(f"本月支出：{currency_symbol}{expense_total:.2f}")
    lines.append(f"月预算：{currency_symbol}{monthly_budget:.2f}")
    lines.append(f"剩余额度：{currency_symbol}{remaining:.2f}")
    lines.append(f"使用进度：{rate:.0%}")
    if rate >= 1:
        lines.append("提醒：预算已超出，接下来适合收紧非必要支出。")
    elif rate >= 0.8:
        lines.append("提醒：预算使用已超过 80%，留意后续大额支出。")
    else:
        lines.append("提醒：预算状态正常。")
    return "\n".join(lines)


def _brief_finance_line(
    records: list[dict[str, Any]],
    currency_symbol: str = "¥",
    *,
    monthly_budget: float = 0.0,
) -> str:
    if not records:
        if monthly_budget > 0:
            return f"暂无记录，月预算 {currency_symbol}{monthly_budget:.2f}"
        return "暂无记录"

    totals = _totals_by_direction(records)
    income = totals.get("收入", 0.0)
    expense = totals.get("支出", 0.0)
    parts = [
        f"收入 {currency_symbol}{income:.2f}",
        f"支出 {currency_symbol}{expense:.2f}",
        f"净流入 {currency_symbol}{income - expense:.2f}",
    ]
    loan_flow = totals.get("借入", 0.0) + totals.get("借出", 0.0) + totals.get("还款", 0.0) + totals.get("收款", 0.0)
    if loan_flow:
        parts.append(
            f"借贷 {currency_symbol}{totals.get('借入', 0.0):.2f}/{currency_symbol}{totals.get('借出', 0.0):.2f}"
        )
    if monthly_budget > 0:
        remaining = monthly_budget - expense
        rate = min(max(expense / monthly_budget, 0), 9.99)
        parts.append(f"预算 {rate:.0%}，剩余 {currency_symbol}{remaining:.2f}")

    category_totals = _totals_by_key([item for item in records if item.get("direction") == "支出"], "category")
    if category_totals:
        category, amount = max(category_totals.items(), key=lambda item: item[1])
        parts.append(f"主要支出 {category} {currency_symbol}{amount:.2f}")
    return "，".join(parts)


def _finance_summary_row(scope: str, records: list[dict[str, Any]], currency_symbol: str = "¥") -> dict[str, Any]:
    totals = _totals_by_direction(records)
    return {
        "scope": scope,
        "expense": totals.get("支出", 0.0),
        "income": totals.get("收入", 0.0),
        "currency_symbol": currency_symbol,
    }


def _format_finance_report(
    title: str,
    records: list[dict[str, Any]],
    *,
    monthly_budget: float = 0.0,
    currency_symbol: str = "¥",
) -> str:
    if not records:
        return f"{title}\n暂无财务记录。"
    totals = _totals_by_direction(records)
    expense_records = [item for item in records if item.get("direction") == "支出"]
    income = totals.get("收入", 0)
    expense = totals.get("支出", 0)
    category_totals = _totals_by_key(expense_records, "category")
    wallet_lines = _wallet_summary_lines(records, currency_symbol=currency_symbol)[:5]
    lines = [
        title,
        "## 总览",
        f"- 收入：{currency_symbol}{income:.2f}",
        f"- 支出：{currency_symbol}{expense:.2f}",
        f"- 净流入：{currency_symbol}{income - expense:.2f}",
        f"- 借入/借出：{currency_symbol}{totals.get('借入', 0):.2f} / {currency_symbol}{totals.get('借出', 0):.2f}",
        f"- 还款/收款：{currency_symbol}{totals.get('还款', 0):.2f} / {currency_symbol}{totals.get('收款', 0):.2f}",
    ]
    if monthly_budget > 0:
        remaining = monthly_budget - expense
        lines.append(f"- 预算：{currency_symbol}{expense:.2f} / {currency_symbol}{monthly_budget:.2f}，剩余 {currency_symbol}{remaining:.2f}")
    if category_totals:
        lines.append("## 主要支出")
        for category, amount in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)[:5]:
            lines.append(f"- {category}：{currency_symbol}{amount:.2f}")
    if wallet_lines:
        lines.append("## 钱包分布")
        lines.extend(wallet_lines)
    loan_records = [item for item in records if item.get("direction") in {"借入", "借出", "还款", "收款"}]
    if loan_records:
        lines.append("## 借贷提醒")
        lines.extend(_loan_summary_lines(loan_records, currency_symbol=currency_symbol)[:5])
    lines.append("## 最近明细")
    for item in records[:8]:
        wallet = f"｜{item.get('wallet')}" if item.get("wallet") else ""
        lines.append(
            f"- {item['record_date']} {item['record_time']} {item['direction']} "
            f"{currency_symbol}{float(item['amount']):.2f} [{item['category']}{wallet}] {item.get('note') or ''}"
        )
    return "\n".join(lines)


def _format_loan_summary(records: list[dict[str, Any]], *, currency_symbol: str = "¥") -> str:
    if not records:
        return "借贷情况\n暂无借贷记录。"
    totals = _totals_by_direction(records)
    payable = max(totals.get("借入", 0) - totals.get("还款", 0), 0)
    receivable = max(totals.get("借出", 0) - totals.get("收款", 0), 0)
    lines = [
        "借贷情况",
        f"应还粗略估算：{currency_symbol}{payable:.2f}（借入 - 还款）",
        f"应收粗略估算：{currency_symbol}{receivable:.2f}（借出 - 收款）",
        (
            f"借入 {currency_symbol}{totals.get('借入', 0):.2f}，还款 {currency_symbol}{totals.get('还款', 0):.2f}；"
            f"借出 {currency_symbol}{totals.get('借出', 0):.2f}，收款 {currency_symbol}{totals.get('收款', 0):.2f}"
        ),
        "按对象：",
    ]
    lines.extend(_loan_summary_lines(records, currency_symbol=currency_symbol))
    lines.extend([
        "最近明细：",
    ])
    for item in records[:10]:
        who = item.get("counterparty") or "未标注对象"
        wallet = item.get("wallet") or "未标注钱包"
        lines.append(
            f"- {item['record_date']} {item['direction']} {currency_symbol}{float(item['amount']):.2f}｜{who}｜{wallet}｜{item.get('note') or ''}"
        )
    return "\n".join(lines)


def _format_wallet_summary(records: list[dict[str, Any]], *, currency_symbol: str = "¥") -> str:
    if not records:
        return "钱包统计\n暂无财务记录。"
    lines = ["钱包统计", "这是按已记录流水聚合，不等于真实账户余额。"]
    lines.extend(_wallet_summary_lines(records, currency_symbol=currency_symbol))
    return "\n".join(lines)


def _wallet_summary_lines(records: list[dict[str, Any]], *, currency_symbol: str = "¥") -> list[str]:
    stats: dict[str, dict[str, float]] = {}
    for item in records:
        wallet = str(item.get("wallet") or "未标注").strip() or "未标注"
        direction = str(item.get("direction") or "支出")
        amount = float(item.get("amount") or 0)
        bucket = stats.setdefault(wallet, {"流入": 0.0, "流出": 0.0, "转账": 0.0})
        if direction in {"收入", "借入", "收款"}:
            bucket["流入"] += amount
        elif direction in {"支出", "借出", "还款"}:
            bucket["流出"] += amount
        else:
            bucket["转账"] += amount

    lines: list[str] = []
    for wallet, bucket in sorted(stats.items()):
        lines.append(
            f"- {wallet}：流入 {currency_symbol}{bucket['流入']:.2f}，流出 {currency_symbol}{bucket['流出']:.2f}，转账 {currency_symbol}{bucket['转账']:.2f}"
        )
    return lines


def _loan_summary_lines(records: list[dict[str, Any]], *, currency_symbol: str = "¥") -> list[str]:
    by_person: dict[str, dict[str, float]] = {}
    for item in records:
        who = str(item.get("counterparty") or "未标注对象")
        bucket = by_person.setdefault(who, {"借入": 0.0, "还款": 0.0, "借出": 0.0, "收款": 0.0})
        direction = str(item.get("direction") or "")
        if direction in bucket:
            bucket[direction] += float(item.get("amount") or 0)
    lines: list[str] = []
    for who, bucket in sorted(by_person.items()):
        person_payable = max(bucket.get("借入", 0) - bucket.get("还款", 0), 0)
        person_receivable = max(bucket.get("借出", 0) - bucket.get("收款", 0), 0)
        lines.append(f"- {who}：应还 {currency_symbol}{person_payable:.2f}，应收 {currency_symbol}{person_receivable:.2f}")
    return lines


def _format_health_overview(title: str, records: list[dict[str, Any]]) -> str:
    if not records:
        return f"{title}\n暂无健康记录。"

    latest_weight = next((item for item in records if item.get("metric_type") == "体重" and item.get("value") is not None), None)
    weight_records = [item for item in records if item.get("metric_type") == "体重" and item.get("value") is not None]
    sleep_values = [float(item["value"]) for item in records if item.get("metric_type") == "睡眠" and item.get("value") is not None]
    run_distance = sum(float(item.get("distance_km") or 0) for item in records if item.get("metric_type") == "跑步")
    run_minutes = sum(float(item.get("duration_minutes") or 0) for item in records if item.get("metric_type") == "跑步")
    workout_minutes = sum(float(item.get("duration_minutes") or 0) for item in records if item.get("metric_type") == "健身")

    lines = [title]
    if latest_weight:
        lines.append(f"最近体重：{float(latest_weight['value']):.1f}kg（{latest_weight['record_date']}）")
    if len(weight_records) >= 2:
        newest = float(weight_records[0]["value"])
        oldest = float(weight_records[-1]["value"])
        delta = newest - oldest
        lines.append(f"体重趋势：{delta:+.1f}kg（按当前查询范围）")
    if sleep_values:
        lines.append(f"平均睡眠：{sum(sleep_values) / len(sleep_values):.1f}小时")
    if run_distance:
        lines.append(f"跑步合计：{run_distance:.2f}公里，{run_minutes:.0f}分钟")
    if workout_minutes:
        lines.append(f"健身合计：{workout_minutes:.0f}分钟")

    lines.append("最近明细：")
    for item in records[:8]:
        value = ""
        if item.get("value") is not None:
            value = f" {float(item['value']):g}{item.get('unit') or ''}"
        duration = f" {float(item['duration_minutes']):g}分钟" if item.get("duration_minutes") else ""
        distance = f" {float(item['distance_km']):g}公里" if item.get("distance_km") else ""
        note = item.get("note") or ""
        lines.append(f"- {item['record_date']} {item['record_time']} {item['metric_type']}{value}{distance}{duration} {note}".rstrip())
    return "\n".join(lines)


def _brief_health_lines(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        return ["- 暂无健康记录"]

    lines: list[str] = []
    latest_weight = next((item for item in records if item.get("metric_type") == "体重" and item.get("value") is not None), None)
    sleep_values = [float(item["value"]) for item in records if item.get("metric_type") == "睡眠" and item.get("value") is not None]
    run_distance = sum(float(item.get("distance_km") or 0) for item in records if item.get("metric_type") == "跑步")
    run_minutes = sum(float(item.get("duration_minutes") or 0) for item in records if item.get("metric_type") == "跑步")
    workout_minutes = sum(float(item.get("duration_minutes") or 0) for item in records if item.get("metric_type") == "健身")
    if latest_weight:
        lines.append(f"- 最近体重：{float(latest_weight['value']):.1f}kg（{latest_weight['record_date']}）")
    if run_distance:
        lines.append(f"- 本月跑步：{run_distance:.2f} 公里，{run_minutes:.0f} 分钟")
    if sleep_values:
        lines.append(f"- 平均睡眠：{sum(sleep_values) / len(sleep_values):.1f} 小时")
    if workout_minutes:
        lines.append(f"- 本月健身：{workout_minutes:.0f} 分钟")
    return lines or ["- 暂无可汇总的健康趋势"]


def _totals_by_direction(records: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for item in records:
        direction = str(item.get("direction") or "支出")
        totals[direction] = totals.get(direction, 0.0) + float(item.get("amount") or 0)
    return totals


def _totals_by_key(records: list[dict[str, Any]], key: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    for item in records:
        bucket = str(item.get(key) or "未分类")
        totals[bucket] = totals.get(bucket, 0.0) + float(item.get("amount") or 0)
    return totals


def _format_plan_list(title: str, plans: list[dict[str, Any]]) -> str:
    if not plans:
        return f"{title}\n暂无未完成计划。"
    lines = [title]
    for index, plan in enumerate(plans, start=1):
        target = plan.get("target_date") or "未定"
        priority = plan.get("priority") or "中"
        scope = plan.get("plan_scope") or "其它"
        status = plan.get("status") or "未开始"
        lines.append(f"{index}. [{scope}/{priority}/{status}] {plan['title']}（目标：{target}）")
    return "\n".join(lines)


def _format_reminder_list(title: str, reminders: list[dict[str, Any]]) -> str:
    if not reminders:
        return f"{title}\n暂无备忘提醒。"
    lines = [title]
    for index, item in enumerate(reminders, start=1):
        due = " ".join(part for part in (item.get("due_date"), item.get("due_time")) if part) or "未设置截止"
        lines.append(f"{index}. {item['title']}（{due}）")
    return "\n".join(lines)


def _format_todo_list(title: str, reminders: list[dict[str, Any]], plans: list[dict[str, Any]]) -> str:
    lines = [title]
    active_reminders = [item for item in reminders if item.get("status") not in {"已完成", "取消", "已取消"}]
    active_plans = [item for item in plans if item.get("status") not in {"已完成", "取消", "已取消"}]
    if not active_reminders and not active_plans:
        return f"{title}\n暂无待办。"
    if active_reminders:
        lines.append("\n备忘：")
        for index, item in enumerate(active_reminders, start=1):
            due = " ".join(part for part in (item.get("due_date"), item.get("due_time")) if part) or "未设置截止"
            lines.append(f"{index}. {item['title']}（{due}）")
    if active_plans:
        lines.append("\n计划：")
        for index, plan in enumerate(active_plans, start=1):
            target = " ".join(part for part in (plan.get("target_date"), plan.get("target_time")) if part) or "未定"
            lines.append(f"{index}. [{plan.get('plan_scope') or '其它'}/{plan.get('status') or '未开始'}] {plan['title']}（开始：{target}）")
    return "\n".join(lines)


def _brief_reminder_lines(reminders: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in reminders[:5]:
        due = " ".join(part for part in (item.get("due_date"), item.get("due_time")) if part) or "未设置截止"
        lines.append(f"- {item['title']}（{due}）")
    return lines


def _storage_note_title(category: str, date_text: str, title: str) -> str:
    if category in {"语录笔记", "备忘录"}:
        month_text = date_text[:7] if date_text else datetime.now().strftime("%Y-%m")
        return f"{month_text} {category}"
    return title


def _format_plan_review(
    *,
    today_plans: list[dict[str, Any]],
    week_plans: list[dict[str, Any]],
    overdue: list[dict[str, Any]],
    long_term: list[dict[str, Any]],
) -> str:
    completed_today = [plan for plan in today_plans if plan.get("status") == "已完成"]
    active_today = [plan for plan in today_plans if plan.get("status") not in {"已完成", "取消", "已取消"}]
    completed_week = [plan for plan in week_plans if plan.get("status") == "已完成"]
    open_week = [plan for plan in week_plans if plan.get("status") not in {"已完成", "取消", "已取消"}]
    lines = [
        "计划复盘",
        f"本周完成：{len(completed_week)} 项，未完成/推进中：{len(open_week)} 项",
    ]
    if completed_today:
        lines.append("今日完成：")
        lines.extend(f"- {plan['title']}" for plan in completed_today[:5])
    if active_today:
        lines.append("今日仍需处理：")
        lines.extend(f"- [{plan.get('status') or '未开始'}] {plan['title']}" for plan in active_today[:5])
    if overdue:
        lines.append("候选遗留：")
        lines.extend(f"- {plan['title']}（目标：{plan.get('target_date') or '未定'}）" for plan in overdue[:5])
    if long_term:
        lines.append("长期计划轻提醒：")
        lines.extend(f"- {plan['title']}" for plan in long_term[:3])
    if not any((completed_today, active_today, overdue, long_term)):
        lines.append("暂无需要复盘的计划。")
    else:
        lines.append("下一步建议：只挑 1-3 件真正要推进的事，其他先放回计划池。")
    return "\n".join(lines)


def _format_pending_intents(intents: list[AutoRecordIntent]) -> str:
    lines: list[str] = []
    for index, intent in enumerate(intents, start=1):
        if intent.kind == "finance":
            lines.append(
                f"{index}. 账目：{intent.direction or '支出'} ¥{float(intent.amount or 0):.2f} "
                f"[{intent.category or '其他'}] {intent.note}"
            )
        elif intent.kind == "plan":
            target = intent.date or "未定"
            lines.append(f"{index}. 计划：[{intent.plan_scope or '其它'}] {intent.title or intent.content}（目标：{target}）")
        elif intent.kind == "health":
            value = f" {intent.value:g}{intent.unit}" if intent.value is not None else ""
            lines.append(f"{index}. 健康：{intent.category}{value} {intent.note}".rstrip())
        else:
            lines.append(f"{index}. {intent.kind}：{intent.content or intent.note or intent.title}")
    return "\n".join(lines)


def _intent_from_dict(data: dict[str, Any]) -> AutoRecordIntent:
    allowed = AutoRecordIntent.__dataclass_fields__
    values = {key: value for key, value in dict(data).items() if key in allowed}
    if "tags" in values:
        values["tags"] = tuple(values["tags"] or ())
    return AutoRecordIntent(**values)


def _compact_reply_lines(replies: list[str]) -> str:
    if not replies:
        return ""
    grouped: dict[tuple[str, str, str], int] = {}
    passthrough: list[str] = []
    pattern = re.compile(r"^(已自动写入|已写入)([^：]+)：(.+)$")
    for reply in replies:
        match = pattern.match(reply.strip())
        if not match:
            passthrough.append(reply)
            continue
        prefix, label, path = match.groups()
        grouped[(prefix, label, path)] = grouped.get((prefix, label, path), 0) + 1

    lines: list[str] = []
    for (prefix, label, path), count in grouped.items():
        if count == 1:
            lines.append(f"{prefix}{label}：{path}")
        else:
            lines.append(f"{prefix} {count} 条{label}：{path}")
    lines.extend(passthrough)
    return "\n".join(lines)


def _finance_record_title(record: dict[str, Any]) -> str:
    return (
        f"{record.get('record_date')} {record.get('record_time')} "
        f"{record.get('direction')} ¥{float(record.get('amount') or 0):.2f} "
        f"{record.get('note') or record.get('category') or ''}"
    ).strip()


def _parse_clock_time(value: str) -> tuple[int, int] | None:
    try:
        hour_text, minute_text = str(value or "").strip().split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour, minute


def _build_message_chain(text: str):
    try:
        from astrbot.core.message.message_event_result import MessageChain

        chain = MessageChain()
        if hasattr(chain, "message"):
            return chain.message(text)
        return MessageChain(text)
    except Exception:
        return text


def _build_image_message_chain(image_url: str):
    try:
        from astrbot.core.message.message_event_result import MessageChain

        chain = MessageChain()
        if image_url.startswith(("http://", "https://")):
            message = _call_first_available(chain, ("url_image", "image", "file_image"), image_url)
        else:
            message = _call_first_available(chain, ("file_image", "image"), image_url)
        if message is not None:
            return message
    except Exception:
        return None
    return None


def _call_first_available(target: Any, method_names: tuple[str, ...], value: str):
    for method_name in method_names:
        method = getattr(target, method_name, None)
        if callable(method):
            return method(value)
    return None
