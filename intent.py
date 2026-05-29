from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re

from .utils import count_money_amounts, infer_finance_category, parse_finance_record, remove_money_amounts, truncate


NO_BODY_TRIGGERS = {
    "确认写入",
    "取消写入",
    "确认",
    "取消",
    "撤销上一条",
    "晨报",
    "今日总结",
    "日总结",
    "总结",
    "日记草稿",
    "语录周精选",
    "周报",
    "推送到这里",
    "我的计划",
    "今日计划",
    "本周计划",
    "本月计划",
    "长期计划",
    "空闲计划",
    "计划清单",
    "所有计划",
    "今日备忘",
    "近期备忘",
    "我的备忘",
    "今日待办",
    "近期待办",
    "我的待办",
    "今日财务",
    "本周财务",
    "本月财务",
    "借贷情况",
    "钱包统计",
    "预算情况",
    "财务周报",
    "财务月报",
    "计划复盘",
    "今日健康",
    "本周健康",
    "本月健康",
    "健康概览",
    "系统状态",
    "Obsidian状态",
    "恢复索引",
    "重建索引",
    "查看触发词",
    "Obsidian帮助",
    "使用帮助",
    "记账帮助",
    "计划帮助",
    "健康帮助",
    "总结帮助",
}
TRIGGERS = (
    "确认写入",
    "取消写入",
    "查看触发词",
    "Obsidian帮助",
    "使用帮助",
    "记账帮助",
    "计划帮助",
    "健康帮助",
    "总结帮助",
    "Obsidian状态",
    "系统状态",
    "恢复索引",
    "重建索引",
    "语录周精选",
    "撤销上一条",
    "推送到这里",
    "修改计划",
    "取消计划",
    "删除计划",
    "作废计划",
    "推迟计划",
    "开始计划",
    "完成计划",
    "计划复盘",
    "今日计划",
    "本周计划",
    "本月计划",
    "长期计划",
    "空闲计划",
    "计划清单",
    "所有计划",
    "我的计划",
    "今日备忘",
    "近期备忘",
    "我的备忘",
    "今日待办",
    "近期待办",
    "我的待办",
    "今日财务",
    "本周财务",
    "本月财务",
    "借贷情况",
    "钱包统计",
    "预算情况",
    "财务周报",
    "财务月报",
    "作废账目",
    "删除账目",
    "修改账目",
    "改账目",
    "今日健康",
    "本周健康",
    "本月健康",
    "健康概览",
    "晨报",
    "今日总结",
    "日记草稿",
    "日总结",
    "总结",
    "改上一条",
    "改计划",
    "存一下",
    "补记",
    "借入",
    "借出",
    "还款",
    "收款",
    "转账",
    "记账",
    "支出",
    "收入",
    "日记",
    "记事",
    "随想",
    "语录",
    "计划",
    "备忘录",
    "备忘",
    "DDL",
    "体重",
    "跑步",
    "睡眠",
    "健身",
    "运动",
    "收集",
    "周报",
    "确认",
    "取消",
    "记",
)
SEPARATORS = " \t，,。:：、"
DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+|[,，:：、]*)")
MONTH_DAY_RE = re.compile(r"^(\d{1,2})月(\d{1,2})日?(?:\s+|[,，:：、]*)")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?:\s+|[,，:：、]*)")
CHINESE_TIME_RE = re.compile(r"^(凌晨|早上|上午|中午|下午|晚上|今晚)?([零〇一二两三四五六七八九十\d]{1,3})点(半|[零〇一二三四五六七八九十\d]{1,3}分?)?(?:\s+|[,，:：、]*)?")
NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)")
MONEY_SEGMENT_RE = re.compile(
    r"([^¥￥\d;；\n]+?(?:[¥￥]\s*)?\d+(?:\.\d+)?\s*(?:块钱|快钱|元钱|元|块|快|rmb|RMB)?)"
)


@dataclass(frozen=True)
class AutoRecordIntent:
    kind: str
    confidence: float
    reason: str
    content: str = ""
    category: str = ""
    title: str = ""
    note_type: str = ""
    amount: float | None = None
    direction: str = ""
    note: str = ""
    wallet: str = ""
    counterparty: str = ""
    date: str | None = None
    time: str | None = None
    trigger: str = ""
    source: str = ""
    author: str = ""
    tags: tuple[str, ...] = ()
    comment: str = ""
    plan_scope: str = ""
    priority: str = ""
    pending_text: str = ""
    value: float | None = None
    unit: str = ""
    duration_minutes: float | None = None
    distance_km: float | None = None


@dataclass(frozen=True)
class ParsedPrefix:
    trigger: str
    body: str


@dataclass(frozen=True)
class ParsedRecordMeta:
    body: str
    date: str | None = None
    time: str | None = None


def classify_auto_record(message: str, *, mode: str = "explicit") -> AutoRecordIntent | None:
    text = _normalize_message(message)
    if not text:
        return None
    if (mode or "explicit").strip().lower() not in {"explicit", "conservative"}:
        return None

    parsed = _parse_trigger_prefix(text)
    if not parsed:
        return None

    if parsed.trigger == "撤销上一条":
        return AutoRecordIntent(kind="undo", confidence=1.0, reason="explicit_undo_trigger", trigger=parsed.trigger)
    if parsed.trigger in {"确认", "确认写入"}:
        return AutoRecordIntent(kind="confirm_pending", confidence=1.0, reason="explicit_confirm_trigger", trigger=parsed.trigger)
    if parsed.trigger in {"取消", "取消写入"}:
        return AutoRecordIntent(kind="cancel_pending", confidence=1.0, reason="explicit_cancel_trigger", trigger=parsed.trigger)
    if parsed.trigger in {"系统状态", "Obsidian状态"}:
        return AutoRecordIntent(kind="system_status", confidence=1.0, reason="explicit_status_trigger", trigger=parsed.trigger)
    if parsed.trigger in {"恢复索引", "重建索引"}:
        return AutoRecordIntent(kind="recover_index", confidence=1.0, reason="explicit_recovery_trigger", trigger=parsed.trigger)
    if parsed.trigger in {"查看触发词", "Obsidian帮助", "使用帮助", "记账帮助", "计划帮助", "健康帮助", "总结帮助"}:
        help_topic = {
            "查看触发词": "all",
            "Obsidian帮助": "all",
            "使用帮助": "all",
            "记账帮助": "finance",
            "计划帮助": "plan",
            "健康帮助": "health",
            "总结帮助": "summary",
        }[parsed.trigger]
        return AutoRecordIntent(
            kind="help",
            confidence=1.0,
            reason="explicit_help_trigger",
            content=help_topic,
            trigger=parsed.trigger,
        )
    if parsed.trigger == "推送到这里":
        return AutoRecordIntent(
            kind="set_push_target",
            confidence=1.0,
            reason="explicit_push_target_trigger",
            trigger=parsed.trigger,
        )
    if parsed.trigger in {"计划复盘"}:
        return AutoRecordIntent(kind="plan_review", confidence=1.0, reason="explicit_plan_review_trigger", trigger=parsed.trigger)
    if parsed.trigger in {"我的计划", "今日计划", "本周计划", "本月计划", "长期计划", "空闲计划", "计划清单", "所有计划"}:
        query_scope = {
            "今日计划": "today",
            "本周计划": "week",
            "本月计划": "month",
            "长期计划": "long_term",
            "空闲计划": "free",
            "我的计划": "all",
            "计划清单": "all",
            "所有计划": "all",
        }[parsed.trigger]
        return AutoRecordIntent(
            kind="plan_query",
            confidence=1.0,
            reason="explicit_plan_query_trigger",
            content=query_scope,
            trigger=parsed.trigger,
        )
    if parsed.trigger in {"今日备忘", "近期备忘", "我的备忘", "今日待办", "近期待办", "我的待办"}:
        query_scope = {
            "今日备忘": "today",
            "近期备忘": "soon",
            "我的备忘": "all",
            "今日待办": "today",
            "近期待办": "soon",
            "我的待办": "all",
        }[parsed.trigger]
        return AutoRecordIntent(
            kind="todo_query" if "待办" in parsed.trigger else "reminder_query",
            confidence=1.0,
            reason="explicit_todo_query_trigger" if "待办" in parsed.trigger else "explicit_reminder_query_trigger",
            content=query_scope,
            trigger=parsed.trigger,
        )
    if parsed.trigger in {"今日财务", "本周财务", "本月财务", "借贷情况", "钱包统计", "预算情况", "财务周报", "财务月报"}:
        query_scope = {
            "今日财务": "today",
            "本周财务": "week",
            "本月财务": "month",
            "借贷情况": "loan",
            "钱包统计": "wallet",
            "预算情况": "budget",
            "财务周报": "week_report",
            "财务月报": "month_report",
        }[parsed.trigger]
        return AutoRecordIntent(
            kind="finance_query",
            confidence=1.0,
            reason="explicit_finance_query_trigger",
            content=query_scope,
            trigger=parsed.trigger,
        )
    if parsed.trigger in {"今日健康", "本周健康", "本月健康", "健康概览"}:
        query_scope = {
            "今日健康": "today",
            "本周健康": "week",
            "本月健康": "month",
            "健康概览": "month",
        }[parsed.trigger]
        return AutoRecordIntent(
            kind="health_query",
            confidence=1.0,
            reason="explicit_health_query_trigger",
            content=query_scope,
            trigger=parsed.trigger,
        )
    if parsed.trigger in {"取消计划", "删除计划", "作废计划"}:
        body = parsed.body.strip()
        if not body:
            return None
        return AutoRecordIntent(
            kind="plan_cancel",
            confidence=1.0,
            reason="explicit_plan_cancel_trigger",
            content=body,
            trigger=parsed.trigger,
        )
    if parsed.trigger in {"修改计划", "改计划"}:
        parsed_update = _parse_update_body(parsed.body)
        if not parsed_update:
            return None
        keyword, new_content = parsed_update
        return AutoRecordIntent(
            kind="plan_update",
            confidence=1.0,
            reason="explicit_plan_update_trigger",
            content=keyword,
            note=new_content,
            trigger=parsed.trigger,
        )
    if parsed.trigger == "推迟计划":
        parsed_postpone = _parse_postpone_body(parsed.body)
        if not parsed_postpone:
            return None
        keyword, meta = parsed_postpone
        return AutoRecordIntent(
            kind="plan_postpone",
            confidence=1.0,
            reason="explicit_plan_postpone_trigger",
            content=keyword,
            date=meta.date,
            time=meta.time,
            note=meta.body,
            trigger=parsed.trigger,
        )
    if parsed.trigger == "开始计划":
        body = parsed.body.strip()
        if not body:
            return None
        return AutoRecordIntent(
            kind="plan_start",
            confidence=1.0,
            reason="explicit_plan_start_trigger",
            content=body,
            trigger=parsed.trigger,
        )
    if parsed.trigger in {"作废账目", "删除账目"}:
        body = parsed.body.strip()
        if not body:
            return None
        return AutoRecordIntent(
            kind="finance_cancel",
            confidence=1.0,
            reason="explicit_finance_cancel_trigger",
            content=body,
            trigger=parsed.trigger,
        )
    if parsed.trigger in {"修改账目", "改账目"}:
        parsed_update = _parse_update_body(parsed.body)
        if not parsed_update:
            return None
        keyword, new_content = parsed_update
        return AutoRecordIntent(
            kind="finance_update",
            confidence=1.0,
            reason="explicit_finance_update_trigger",
            content=keyword,
            note=new_content,
            trigger=parsed.trigger,
        )
    if parsed.trigger == "完成计划":
        body = parsed.body.strip()
        if not body:
            return None
        return AutoRecordIntent(
            kind="plan_complete",
            confidence=1.0,
            reason="explicit_plan_complete_trigger",
            content=body,
            trigger=parsed.trigger,
        )
    if parsed.trigger in {"晨报", "今日总结", "日总结", "总结", "日记草稿", "语录周精选", "周报"}:
        meta = _parse_record_meta(parsed.body) if parsed.body else ParsedRecordMeta(body="")
        kind = {
            "晨报": "briefing",
            "今日总结": "daily_summary",
            "日总结": "daily_summary",
            "总结": "daily_summary",
            "日记草稿": "diary_draft",
            "语录周精选": "quote_weekly",
            "周报": "weekly_summary",
        }[parsed.trigger]
        return AutoRecordIntent(
            kind=kind,
            confidence=1.0,
            reason=f"explicit_{kind}_trigger",
            content=meta.body,
            date=meta.date,
            time=meta.time,
            trigger=parsed.trigger,
        )
    if parsed.trigger == "改上一条":
        body = parsed.body.strip()
        if not body:
            return None
        return AutoRecordIntent(
            kind="amend",
            confidence=1.0,
            reason="explicit_amend_trigger",
            content=body,
            trigger=parsed.trigger,
        )
    if parsed.trigger == "补记":
        return _build_backfill_intent(parsed.body)

    meta = _parse_record_meta(parsed.body)
    body = meta.body.strip()
    if not body:
        return None

    risk = _risky_single_record_message(parsed.trigger, body)
    if risk:
        return AutoRecordIntent(
            kind="needs_confirmation",
            confidence=1.0,
            reason="risky_single_record_message",
            content=risk,
            pending_text=text,
            trigger=parsed.trigger,
        )

    return _build_record_intent(parsed.trigger, body, meta)


def classify_auto_record_batch(message: str, *, mode: str = "explicit") -> list[AutoRecordIntent]:
    intents: list[AutoRecordIntent] = []
    for line in _record_lines(message):
        expanded = _classify_expanded_record_line(line, mode=mode)
        if expanded:
            intents.extend(expanded)
            continue
        intent = classify_auto_record(line, mode=mode)
        if intent:
            intents.append(intent)
    return intents


def _classify_expanded_record_line(line: str, *, mode: str = "explicit") -> list[AutoRecordIntent]:
    text = _normalize_message(line)
    if not text or (mode or "explicit").strip().lower() not in {"explicit", "conservative"}:
        return []
    parsed = _parse_trigger_prefix(text)
    if not parsed:
        return []

    if parsed.trigger in {"记账", "支出", "收入", "借入", "借出", "还款", "收款", "转账"}:
        meta = _parse_record_meta(parsed.body)
        segments = _split_finance_segments(meta.body)
        if len(segments) <= 1:
            return []
        intents: list[AutoRecordIntent] = []
        for segment in segments:
            item_meta = ParsedRecordMeta(body=segment, date=meta.date, time=meta.time)
            intent = _build_record_intent(parsed.trigger, segment, item_meta)
            if intent:
                intents.append(intent)
        return intents

    if parsed.trigger == "计划":
        meta = _parse_record_meta(parsed.body)
        content, plan_scope = _parse_plan_scope(meta.body, has_target_date=bool(meta.date))
        segments = _split_plan_segments(content)
        if len(segments) <= 1:
            return []
        return [_build_plan_intent_from_parts("计划", segment, meta, plan_scope) for segment in segments]

    return []


def build_confirmation_candidate_intents(message: str, *, mode: str = "explicit") -> list[AutoRecordIntent]:
    text = _normalize_message(message)
    if not text or (mode or "explicit").strip().lower() not in {"explicit", "conservative"}:
        return []
    parsed = _parse_trigger_prefix(text)
    if not parsed:
        return []

    if parsed.trigger in {"记账", "支出", "收入", "借入", "借出", "还款", "收款", "转账"}:
        meta = _parse_record_meta(parsed.body)
        segments = _split_finance_segments_loose(meta.body)
        intents: list[AutoRecordIntent] = []
        for segment in segments:
            intent = _build_record_intent(parsed.trigger, segment, ParsedRecordMeta(segment, meta.date, meta.time))
            if intent:
                intents.append(intent)
        return intents if len(intents) > 1 else []

    if parsed.trigger == "计划":
        meta = _parse_record_meta(parsed.body)
        content, plan_scope = _parse_plan_scope(meta.body, has_target_date=bool(meta.date))
        segments = _split_plan_segments_loose(content)
        if len(segments) <= 1:
            return []
        return [_build_plan_intent_from_parts("计划", segment, meta, plan_scope) for segment in segments]

    return []


def _build_record_intent(trigger: str, body: str, meta: ParsedRecordMeta) -> AutoRecordIntent | None:
    if trigger in {"记账", "支出", "收入", "借入", "借出", "还款", "收款", "转账"}:
        direction_override = {
            "支出": "支出",
            "收入": "收入",
            "借入": "借入",
            "借出": "借出",
            "还款": "还款",
            "收款": "收款",
            "转账": "转账",
        }.get(trigger)
        return _build_finance_intent(trigger, body, meta, direction_override=direction_override)
    if trigger in {"日记", "记事"}:
        return _build_diary_intent(trigger, body, meta)
    if trigger == "随想":
        return _build_note_intent(trigger, body, meta, note_type="随想")
    if trigger == "语录":
        return _build_quote_intent(trigger, body, meta)
    if trigger == "计划":
        return _build_plan_intent(trigger, body, meta)
    if trigger in {"备忘", "备忘录", "DDL"}:
        return _build_reminder_intent(trigger, body, meta)
    if trigger in {"体重", "跑步", "睡眠", "健身", "运动"}:
        return _build_health_intent(trigger, body, meta)
    if trigger in {"收集", "存一下", "记"}:
        return AutoRecordIntent(
            kind="inbox",
            confidence=1.0,
            reason="explicit_collect_trigger",
            content=body,
            category="收集",
            date=meta.date,
            time=meta.time,
            trigger=trigger,
        )
    return None


def _build_health_intent(trigger: str, body: str, meta: ParsedRecordMeta) -> AutoRecordIntent:
    value: float | None = None
    unit = ""
    duration_minutes: float | None = None
    distance_km: float | None = None
    health_type = trigger if trigger != "运动" else _infer_health_type(body)

    if health_type == "体重":
        value = _extract_number(body)
        unit = "kg"
    elif health_type == "睡眠":
        value = _extract_number(body)
        unit = "小时"
    elif health_type == "跑步":
        distance_km = _extract_unit_number(body, ("公里", "km", "KM"))
        duration_minutes = _extract_duration_minutes(body)
        value = None
        unit = ""
    else:
        duration_minutes = _extract_duration_minutes(body)
        value = duration_minutes
        unit = "分钟" if duration_minutes is not None else ""

    note = _strip_health_metric_note(body, health_type)

    return AutoRecordIntent(
        kind="health",
        confidence=1.0,
        reason="explicit_health_trigger",
        content=body.strip(),
        category=health_type,
        note=note,
        date=meta.date,
        time=meta.time,
        trigger=trigger,
        value=value,
        unit=unit,
        duration_minutes=duration_minutes,
        distance_km=distance_km,
    )


def _build_backfill_intent(body: str) -> AutoRecordIntent | None:
    first_meta = _parse_record_meta(body)
    parsed = _parse_trigger_prefix(first_meta.body)
    if parsed and parsed.trigger != "补记":
        second_meta = _parse_record_meta(parsed.body)
        combined_meta = ParsedRecordMeta(
            body=second_meta.body,
            date=first_meta.date or second_meta.date,
            time=first_meta.time or second_meta.time,
        )
        record = _build_record_intent(parsed.trigger, combined_meta.body.strip(), combined_meta)
        if record:
            return _copy_intent(record, trigger="补记", reason=f"backfill_{record.reason}")

    content = first_meta.body.strip()
    if not content:
        return None
    return AutoRecordIntent(
        kind="diary",
        confidence=1.0,
        reason="explicit_backfill_diary_trigger",
        content=content,
        category="补记",
        date=first_meta.date,
        time=first_meta.time,
        trigger="补记",
    )


def _build_finance_intent(
    trigger: str,
    body: str,
    meta: ParsedRecordMeta,
    *,
    direction_override: str | None = None,
) -> AutoRecordIntent | None:
    parsed = parse_finance_record(body, direction_override=direction_override)
    if not parsed:
        return None
    note = _clean_finance_note(body) or parsed.description
    return AutoRecordIntent(
        kind="finance",
        confidence=1.0,
        reason="explicit_finance_trigger",
        amount=parsed.amount,
        direction=parsed.direction,
        note=note,
        wallet=parsed.wallet,
        counterparty=parsed.counterparty,
        category=_finance_category_for(parsed.direction, note),
        date=meta.date,
        time=meta.time,
        trigger=trigger,
    )


def _finance_category_for(direction: str, note: str) -> str:
    if direction in {"借入", "借出", "还款", "收款"}:
        return "借贷"
    if direction == "转账":
        return "转账"
    return infer_finance_category(note)


def _build_diary_intent(trigger: str, body: str, meta: ParsedRecordMeta) -> AutoRecordIntent:
    return AutoRecordIntent(
        kind="diary",
        confidence=1.0,
        reason="explicit_diary_trigger",
        content=body,
        category="日记" if trigger == "日记" else "记事",
        date=meta.date,
        time=meta.time,
        trigger=trigger,
    )


def _build_note_intent(
    trigger: str,
    body: str,
    meta: ParsedRecordMeta,
    *,
    note_type: str,
) -> AutoRecordIntent:
    content = body.strip()
    title = _make_note_title(content, prefix=note_type)
    return AutoRecordIntent(
        kind="note",
        confidence=1.0,
        reason="explicit_note_trigger",
        content=content,
        title=title,
        note_type=note_type,
        date=meta.date,
        time=meta.time,
        trigger=trigger,
    )


def _build_quote_intent(trigger: str, body: str, meta: ParsedRecordMeta) -> AutoRecordIntent:
    quote, source, author, tags, comment = _parse_quote_fields(body)
    lines = [f"原句：{quote}"]
    lines.append(f"来源：{source or '未标注'}")
    if author:
        lines.append(f"作者或账号：{author}")
    if tags:
        lines.append("标签：" + " ".join(f"#{tag}" for tag in tags))
    if comment:
        lines.append(f"一句话感想：{comment}")

    return AutoRecordIntent(
        kind="note",
        confidence=1.0,
        reason="explicit_quote_trigger",
        content="\n".join(lines),
        title=_make_note_title(quote, prefix="语录"),
        note_type="语录",
        date=meta.date,
        time=meta.time,
        trigger=trigger,
        source=source,
        author=author,
        tags=tuple(tags),
        comment=comment,
    )


def _build_plan_intent(trigger: str, body: str, meta: ParsedRecordMeta) -> AutoRecordIntent:
    content, plan_scope = _parse_plan_scope(body, has_target_date=bool(meta.date))
    return _build_plan_intent_from_parts(trigger, content, meta, plan_scope)


def _build_plan_intent_from_parts(trigger: str, content: str, meta: ParsedRecordMeta, plan_scope: str) -> AutoRecordIntent:
    priority = _parse_plan_priority(content)
    title = _make_note_title(content, prefix="计划")
    return AutoRecordIntent(
        kind="plan",
        confidence=1.0,
        reason="explicit_plan_trigger",
        content=content,
        title=title,
        date=meta.date,
        time=meta.time,
        trigger=trigger,
        plan_scope=plan_scope,
        priority=priority,
    )


def _build_reminder_intent(trigger: str, body: str, meta: ParsedRecordMeta) -> AutoRecordIntent:
    title = truncate(body, 30)
    due_hint = " ".join(part for part in (meta.date, meta.time) if part)
    note = f"截止：{due_hint}" if due_hint else ""
    return AutoRecordIntent(
        kind="reminder",
        confidence=1.0,
        reason="explicit_reminder_trigger",
        content=body,
        title=title,
        note=note,
        date=meta.date,
        time=meta.time,
        trigger=trigger,
    )


def _parse_trigger_prefix(text: str) -> ParsedPrefix | None:
    value = text.strip()
    for trigger in TRIGGERS:
        if not value.startswith(trigger):
            continue
        body = value[len(trigger) :].strip(SEPARATORS)
        if not body and trigger not in NO_BODY_TRIGGERS:
            return None
        return ParsedPrefix(trigger=trigger, body=body)
    return None


def _parse_record_meta(body: str) -> ParsedRecordMeta:
    value = body.strip(SEPARATORS)
    date_text: str | None = None
    time_text: str | None = None

    for _ in range(3):
        changed = False
        parsed_date, value_after_date = _consume_date(value)
        if parsed_date and not date_text:
            date_text = parsed_date
            value = value_after_date.strip(SEPARATORS)
            changed = True

        parsed_time, value_after_time = _consume_time(value)
        if parsed_time and not time_text:
            time_text = parsed_time
            value = value_after_time.strip(SEPARATORS)
            changed = True

        if not changed:
            break

    return ParsedRecordMeta(body=value.strip(), date=date_text, time=time_text)


def _consume_date(text: str) -> tuple[str | None, str]:
    value = text.strip()
    today = datetime.now().date()
    for word, delta_days in (("今天", 0), ("明天", 1), ("后天", 2), ("大后天", 3), ("昨天", -1), ("前天", -2)):
        if value.startswith(word):
            rest = value[len(word) :]
            if rest and rest[0] not in SEPARATORS:
                if word not in {"明天", "后天", "大后天"} and count_money_amounts(rest) == 0:
                    continue
                if rest[0].isdigit():
                    continue
            return (today + timedelta(days=delta_days)).strftime("%Y-%m-%d"), rest

    match = DATE_RE.match(value)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return datetime(year, month, day).strftime("%Y-%m-%d"), value[match.end() :]

    match = MONTH_DAY_RE.match(value)
    if match:
        month, day = (int(part) for part in match.groups())
        return datetime(today.year, month, day).strftime("%Y-%m-%d"), value[match.end() :]

    return None, value


def _consume_time(text: str) -> tuple[str | None, str]:
    value = text.strip()
    match = TIME_RE.match(value)
    if match:
        hour, minute = (int(part) for part in match.groups())
        if hour > 23 or minute > 59:
            return None, value
        return f"{hour:02d}:{minute:02d}", value[match.end() :]

    match = CHINESE_TIME_RE.match(value)
    if not match:
        return None, value
    period, hour_text, minute_text = match.groups()
    hour = _chinese_number_to_int(hour_text)
    if hour is None:
        return None, value
    minute = 30 if minute_text == "半" else 0
    if minute_text and minute_text != "半":
        minute = _chinese_number_to_int(minute_text.rstrip("分")) or 0
    if period in {"下午", "晚上", "今晚"} and hour < 12:
        hour += 12
    if period == "中午" and hour < 11:
        hour += 12
    if hour > 23 or minute > 59:
        return None, value
    return f"{hour:02d}:{minute:02d}", value[match.end() :]


def _chinese_number_to_int(value: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if text == "十":
        return 10
    if text.startswith("十"):
        return 10 + digits.get(text[1:], 0)
    if "十" in text:
        left, right = text.split("十", 1)
        return digits.get(left, 0) * 10 + (digits.get(right, 0) if right else 0)
    if len(text) == 1:
        return digits.get(text)
    return None


def _parse_quote_fields(body: str) -> tuple[str, str, str, list[str], str]:
    value = body.strip()
    normalized = value.replace("｜", "|")
    parts = [part.strip() for part in normalized.split("|") if part.strip()]

    source = ""
    author = ""
    quote = value
    tags_text = ""
    comment = ""

    if len(parts) >= 5:
        source, author, quote, tags_text, comment = parts[:5]
    elif len(parts) == 4:
        source, author, quote, comment = parts
    elif len(parts) == 3:
        source, author, quote = parts
    elif len(parts) == 2:
        source, quote = parts
    else:
        labeled = _parse_labeled_quote(value)
        if labeled:
            quote, source, author, tags_text, comment = labeled

    tags = _extract_tags(tags_text)
    if not tags:
        tags = _extract_tags(quote)
    quote = re.sub(r"#[\w\u4e00-\u9fff-]+", "", quote).strip()
    return quote or value, source, author, tags, comment


def _parse_plan_scope(body: str, *, has_target_date: bool) -> tuple[str, str]:
    value = body.strip(SEPARATORS)
    scope_rules = (
        ("长期计划", "长期"),
        ("长期", "长期"),
        ("短期计划", "短期"),
        ("短期", "短期"),
        ("本周", "短期"),
        ("这周", "短期"),
        ("本月", "短期"),
        ("这个月", "短期"),
        ("近期", "短期"),
        ("最近", "短期"),
    )
    for prefix, scope in scope_rules:
        if value.startswith(prefix):
            return value[len(prefix) :].strip(SEPARATORS) or value, scope
    for prefix in ("有空", "空闲", "以后"):
        if value.startswith(prefix):
            return value[len(prefix) :].strip(SEPARATORS) or value, "其它"
    if has_target_date:
        return value, "短期"
    return value, "其它"


def _parse_plan_priority(body: str) -> str:
    value = body.strip()
    if any(word in value for word in ("高优先级", "重要", "紧急", "必须", "优先")):
        return "高"
    if any(word in value for word in ("低优先级", "有空", "不急", "随缘")):
        return "低"
    return "中"


def _parse_labeled_quote(value: str) -> tuple[str, str, str, str, str] | None:
    field_re = re.compile(r"(作者或账号|一句话感想|来源|作者|账号|标签|感想|原句|语录|内容|正文)[:：]\s*")
    matches = list(field_re.finditer(value))
    if not matches:
        return None

    fields: dict[str, str] = {}
    leading_quote = value[: matches[0].start()].strip(SEPARATORS)
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        fields[match.group(1)] = value[start:end].strip(SEPARATORS)

    quote = fields.get("原句") or fields.get("语录") or fields.get("内容") or fields.get("正文") or leading_quote
    source = fields.get("来源", "")
    author = fields.get("作者或账号") or fields.get("作者") or fields.get("账号") or ""
    tags = fields.get("标签", "")
    comment = fields.get("一句话感想") or fields.get("感想", "")
    if not quote:
        quote, comment = comment, ""
    if not quote:
        return None
    return quote, source, author, tags, comment


def _strip_health_metric_note(body: str, health_type: str) -> str:
    value = str(body or "").strip(SEPARATORS)
    if health_type == "体重":
        value = re.sub(r"^\d+(?:\.\d+)?\s*(?:kg|KG|公斤|斤)?", "", value).strip(SEPARATORS)
    elif health_type == "睡眠":
        value = re.sub(r"^\d+(?:\.\d+)?\s*(?:小时|h|H)?", "", value).strip(SEPARATORS)
    elif health_type == "跑步":
        value = re.sub(r"\d+(?:\.\d+)?\s*(?:公里|km|KM)", "", value).strip(SEPARATORS)
        value = re.sub(r"\d+(?:\.\d+)?\s*(?:分钟|分|min|MIN)", "", value).strip(SEPARATORS)
    else:
        value = re.sub(r"^\d+(?:\.\d+)?\s*(?:分钟|分|min|MIN)?", "", value).strip(SEPARATORS)
    return value


def _parse_update_body(body: str) -> tuple[str, str] | None:
    value = str(body or "").strip(SEPARATORS)
    for separator in (" 为 ", " 改为 ", "改为", "改成", "为"):
        if separator not in value:
            continue
        keyword, new_content = value.split(separator, 1)
        keyword = keyword.strip(SEPARATORS)
        new_content = new_content.strip(SEPARATORS)
        if keyword and new_content:
            return keyword, new_content
    return None


def _parse_postpone_body(body: str) -> tuple[str, ParsedRecordMeta] | None:
    value = str(body or "").strip(SEPARATORS)
    for separator in (" 到 ", " 推迟到 ", "改到", "推迟到", "到"):
        if separator not in value:
            continue
        keyword, target = value.split(separator, 1)
        keyword = keyword.strip(SEPARATORS)
        target = target.strip(SEPARATORS)
        if keyword and target:
            meta = _parse_record_meta(target)
            if meta.date or meta.time or meta.body:
                return keyword, meta
    return None


def _infer_health_type(body: str) -> str:
    value = str(body or "")
    if "体重" in value:
        return "体重"
    if "睡" in value:
        return "睡眠"
    if "跑" in value or "公里" in value or "km" in value.lower():
        return "跑步"
    return "健身"


def _extract_number(text: str) -> float | None:
    match = NUMBER_RE.search(str(text or ""))
    return float(match.group(1)) if match else None


def _extract_unit_number(text: str, units: tuple[str, ...]) -> float | None:
    unit_pattern = "|".join(re.escape(unit) for unit in units)
    match = re.search(rf"(\d+(?:\.\d+)?)\s*(?:{unit_pattern})", str(text or ""), flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def _extract_duration_minutes(text: str) -> float | None:
    value = str(text or "")
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:小时|h|H)", value)
    minute_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:分钟|分|min|MIN)", value)
    minutes = 0.0
    found = False
    if hour_match:
        minutes += float(hour_match.group(1)) * 60
        found = True
    if minute_match:
        minutes += float(minute_match.group(1))
        found = True
    return minutes if found else None


def _extract_tags(text: str) -> list[str]:
    tags: list[str] = []
    for tag in re.findall(r"#([\w\u4e00-\u9fff-]+)", text or ""):
        if tag and tag not in tags:
            tags.append(tag)
    if not tags and text:
        for tag in re.split(r"[\s,，、/]+", text.strip()):
            tag = tag.strip("#" + SEPARATORS)
            if tag and tag not in tags:
                tags.append(tag)
    return tags


def _clean_finance_note(text: str) -> str:
    value = remove_money_amounts(text)
    replacements = (
        "收入",
        "支出",
        "消费",
        "花了",
        "花费",
        "借入",
        "借出",
        "借给",
        "借了",
        "还款",
        "还给",
        "收款",
        "转账",
        "买了",
        "吃了一碗",
        "吃了一个",
        "吃了一份",
        "吃了",
        "一碗",
        "一份",
        "一个",
        "的",
    )
    for word in replacements:
        value = value.replace(word, " ")
    value = re.sub(r"[，。!！?？：:、]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _split_finance_segments(body: str) -> list[str]:
    value = str(body or "").strip(SEPARATORS)
    if not value:
        return []
    parts = [part.strip(SEPARATORS) for part in re.split(r"[;；\n]+|(?<=[元块快钱])[,，、]\s*", value) if part.strip(SEPARATORS)]
    if len(parts) <= 1:
        return [value]
    if all(count_money_amounts(part) == 1 for part in parts):
        return parts
    return [value]


def _split_finance_segments_loose(body: str) -> list[str]:
    value = str(body or "").strip(SEPARATORS)
    if not value:
        return []
    parts = [match.group(1).strip(SEPARATORS) for match in MONEY_SEGMENT_RE.finditer(value)]
    if len(parts) <= 1:
        return [value]
    if all(count_money_amounts(part) == 1 for part in parts):
        return parts
    return [value]


def _split_plan_segments(body: str) -> list[str]:
    value = str(body or "").strip(SEPARATORS)
    if not value:
        return []
    parts = [part.strip(SEPARATORS) for part in re.split(r"[;；\n]+", value) if part.strip(SEPARATORS)]
    return parts if len(parts) > 1 else [value]


def _split_plan_segments_loose(body: str) -> list[str]:
    value = str(body or "").strip(SEPARATORS)
    if not value:
        return []
    explicit = _split_plan_segments(value)
    if len(explicit) > 1:
        return explicit
    parts = [part.strip(SEPARATORS) for part in re.split(r"\s+(?=(?:去|看|整理|学习|读|跑|爬|做|写|买|处理))", value)]
    return parts if len(parts) > 1 else [value]


def _risky_single_record_message(trigger: str, body: str) -> str:
    if trigger in {"记账", "支出", "收入", "借入", "借出", "还款", "收款", "转账"}:
        if count_money_amounts(body) >= 2 and len(_split_finance_segments(body)) <= 1:
            return "我识别到多个金额，但没有明确分隔。请用分号分开发送，例如：支出 午饭20元；晚饭30元"
    if trigger == "计划" and _looks_like_multiple_plan_without_separator(body):
        return "这条消息像包含多个计划。请用分号分开，例如：计划 有空 看龙族动漫；爬大珠山；去灵山岛"
    return ""


def _looks_like_multiple_plan_without_separator(body: str) -> bool:
    value = str(body or "").strip()
    if re.search(r"[;；\n]", value):
        return False
    action_hits = len(re.findall(r"(?<!\S)(去|看|整理|学习|读|跑|爬|做|写|买|处理)", value))
    return action_hits >= 2


def _make_note_title(content: str, *, prefix: str) -> str:
    value = content.strip()
    if prefix == "语录":
        if "｜" in value:
            _, quote = value.split("｜", 1)
            value = quote.strip()
        elif "|" in value:
            _, quote = value.split("|", 1)
            value = quote.strip()
    first_line = re.split(r"[\n。?!？！]", value, maxsplit=1)[0].strip()
    return truncate(first_line or content, 30)


def _copy_intent(intent: AutoRecordIntent, **updates) -> AutoRecordIntent:
    values = {
        "kind": intent.kind,
        "confidence": intent.confidence,
        "reason": intent.reason,
        "content": intent.content,
        "category": intent.category,
        "title": intent.title,
        "note_type": intent.note_type,
        "amount": intent.amount,
        "direction": intent.direction,
        "note": intent.note,
        "wallet": intent.wallet,
        "counterparty": intent.counterparty,
        "date": intent.date,
        "time": intent.time,
        "trigger": intent.trigger,
        "source": intent.source,
        "author": intent.author,
        "tags": intent.tags,
        "comment": intent.comment,
        "plan_scope": intent.plan_scope,
        "priority": intent.priority,
        "pending_text": intent.pending_text,
        "value": intent.value,
        "unit": intent.unit,
        "duration_minutes": intent.duration_minutes,
        "distance_km": intent.distance_km,
    }
    values.update(updates)
    return AutoRecordIntent(**values)


def _normalize_message(message: str) -> str:
    text = str(message or "").strip()
    text = re.sub(r"^\s*\[At:[^\]]+\]\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _record_lines(message: str) -> list[str]:
    lines = [line.strip() for line in str(message or "").splitlines()]
    return [line for line in lines if line]
