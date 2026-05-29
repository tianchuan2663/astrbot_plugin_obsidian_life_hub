from __future__ import annotations

from typing import Awaitable, Callable

from . import prompts


def build_day_data_text(day_data: dict[str, list[dict]], *, include_conversations: bool = False) -> str:
    lines: list[str] = []

    if day_data["events"]:
        lines.append("生活事件：")
        for item in day_data["events"]:
            lines.append(f"- {item['event_time']} [{item['category']}] {item['content']}")

    if day_data["notes"]:
        lines.append("\n生活笔记：")
        for item in day_data["notes"]:
            lines.append(f"- {item['note_time']} [{item['category']}] {item['title']}：{item['content']}")

    if day_data["finance"]:
        lines.append("\n财务记录：")
        for item in day_data["finance"]:
            extra = _finance_extra(item)
            lines.append(
                f"- {item['record_time']} {item['direction']} ¥{item['amount']:.2f} "
                f"[{item['category']}{extra}] {item.get('note') or ''}"
            )

    if day_data.get("health"):
        lines.append("\n健康记录：")
        for item in day_data["health"]:
            lines.append(f"- {item['record_time']} {_format_health_item(item)}")

    if day_data.get("plans"):
        lines.append("\n计划：")
        for item in day_data["plans"]:
            target = item.get("target_date") or "未定"
            lines.append(
                f"- [{item['plan_scope']}/{item['priority']}/{item['status']}] "
                f"{item['title']}（目标：{target}）"
            )

    if day_data.get("reminders"):
        lines.append("\n备忘提醒：")
        for item in day_data["reminders"]:
            due = " ".join(part for part in (item.get("due_date"), item.get("due_time")) if part) or "未设置截止"
            lines.append(f"- {item['title']}（截止：{due}）")

    if day_data.get("finance_brief"):
        lines.append("\n财务简讯：")
        lines.append("| 范围 | 简讯 |")
        lines.append("|---|---|")
        for item in day_data["finance_brief"]:
            scope, _, brief = str(item).partition("：")
            lines.append(f"| {scope or '概览'} | {brief or item} |")

    if include_conversations and day_data["conversations"]:
        lines.append("\n未结构化对话片段（仅作背景，不要当成已确认的日记、账目或笔记）：")
        for item in day_data["conversations"][-20:]:
            created = str(item.get("created_at", ""))[11:16]
            lines.append(f"- {created} {item['role']}: {item['content']}")

    return "\n".join(lines).strip()


def build_range_data_text(range_data: dict[str, list[dict]]) -> str:
    lines: list[str] = []

    if range_data["events"]:
        lines.append("生活事件：")
        for item in range_data["events"]:
            lines.append(f"- {item['event_date']} {item['event_time']} [{item['category']}] {item['content']}")

    if range_data["notes"]:
        lines.append("\n生活笔记：")
        for item in range_data["notes"]:
            lines.append(f"- {item['note_date']} {item['note_time']} [{item['category']}] {item['title']}：{item['content']}")

    if range_data["finance"]:
        income = sum(float(item["amount"]) for item in range_data["finance"] if item["direction"] == "收入")
        expense = sum(float(item["amount"]) for item in range_data["finance"] if item["direction"] == "支出")
        lines.append(f"\n财务记录：收入 ¥{income:.2f}，支出 ¥{expense:.2f}")
        for item in range_data["finance"]:
            extra = _finance_extra(item)
            lines.append(
                f"- {item['record_date']} {item['record_time']} {item['direction']} ¥{item['amount']:.2f} "
                f"[{item['category']}{extra}] {item.get('note') or ''}"
            )

    if range_data.get("health"):
        run_distance = sum(float(item.get("distance_km") or 0) for item in range_data["health"] if item.get("metric_type") == "跑步")
        lines.append(f"\n健康记录：跑步 {run_distance:.2f} 公里")
        for item in range_data["health"]:
            lines.append(f"- {item['record_date']} {item['record_time']} {_format_health_item(item)}")

    if range_data.get("plans"):
        lines.append("\n计划：")
        for item in range_data["plans"]:
            target = item.get("target_date") or "未定"
            lines.append(
                f"- [{item['plan_scope']}/{item['priority']}/{item['status']}] "
                f"{item['title']}（目标：{target}）"
            )

    return "\n".join(lines).strip()


def build_quote_data_text(notes: list[dict]) -> str:
    lines: list[str] = []
    for item in notes:
        lines.append(f"- {item['note_date']} {item['title']}：{item['content']}")
    return "\n".join(lines).strip()


def _finance_extra(item: dict) -> str:
    parts = []
    if item.get("wallet"):
        parts.append(str(item["wallet"]))
    if item.get("counterparty"):
        parts.append(str(item["counterparty"]))
    return "｜" + "｜".join(parts) if parts else ""


def _format_health_item(item: dict) -> str:
    value = ""
    if item.get("value") is not None:
        value = f" {float(item['value']):g}{item.get('unit') or ''}"
    distance = f" {float(item['distance_km']):g}公里" if item.get("distance_km") else ""
    duration = f" {float(item['duration_minutes']):g}分钟" if item.get("duration_minutes") else ""
    note = item.get("note") or ""
    return f"{item['metric_type']}{value}{distance}{duration} {note}".strip()


def _finance_summary_table(day_data: dict[str, list[dict]]) -> str:
    finance_summary = day_data.get("finance_summary") or []
    if finance_summary:
        lines = ["| 范围 | 支出 | 收入 |", "|---|---:|---:|"]
        for item in finance_summary[:3]:
            currency_symbol = item.get("currency_symbol") or "¥"
            lines.append(
                f"| {item.get('scope') or '概览'} | "
                f"{currency_symbol}{float(item.get('expense') or 0):.2f} | "
                f"{currency_symbol}{float(item.get('income') or 0):.2f} |"
            )
        return "\n".join(lines)

    finance = day_data.get("finance") or []
    income = sum(float(item.get("amount") or 0) for item in finance if item.get("direction") == "收入")
    expense = sum(float(item.get("amount") or 0) for item in finance if item.get("direction") == "支出")
    return "\n".join(
        [
            "| 范围 | 支出 | 收入 |",
            "|---|---:|---:|",
            f"| 今日 | ¥{expense:.2f} | ¥{income:.2f} |",
        ]
    )


def _reminder_table(day_data: dict[str, list[dict]]) -> str:
    reminders = [
        item for item in (day_data.get("upcoming_reminders") or [])
        if item.get("status") not in {"已完成", "取消", "已取消"}
    ]
    lines = ["| 内容 | 截止时间 |", "|---|---|"]
    if not reminders:
        lines.append("| 暂无明后天备忘 | |")
        return "\n".join(lines)
    summary_date = str(day_data.get("summary_date") or "")
    lines.extend(f"| {item.get('title') or ''} | {_format_due_text(item, summary_date)} |" for item in reminders[:8])
    return "\n".join(lines)


def _format_due_text(item: dict, summary_date: str) -> str:
    due_date = item.get("due_date") or ""
    due_time = item.get("due_time") or ""
    label = due_date
    if summary_date and due_date:
        from datetime import datetime, timedelta

        base = datetime.strptime(summary_date, "%Y-%m-%d").date()
        due = datetime.strptime(str(due_date), "%Y-%m-%d").date()
        if due == base + timedelta(days=1):
            label = "明日"
        elif due == base + timedelta(days=2):
            label = "后日"
    if due_time:
        if label in {"明日", "后日"}:
            return f"{label} {due_time}"
        return " ".join(part for part in (label, due_time) if part)
    return label


def _daily_diary_fallback(day_data: dict[str, list[dict]]) -> str:
    pieces: list[str] = []
    for item in (day_data.get("events") or [])[:2]:
        pieces.append(str(item.get("content") or ""))
    for item in (day_data.get("notes") or [])[:2]:
        content = item.get("content") or item.get("title") or ""
        pieces.append(str(content))
    for item in (day_data.get("health") or [])[:1]:
        pieces.append(f"健康记录：{_format_health_item(item)}")
    pieces = [piece for piece in pieces if piece]
    if not pieces:
        return "今天的结构化生活记录还不多，先把备忘和财务信息留好，晚点再补一两句日记素材也可以。"
    return "今天主要留下了这些记录：" + "；".join(pieces[:4]) + "。"


def _compact_daily_summary(day_data: dict[str, list[dict]], diary_draft: str | None = None) -> str:
    return (
        "# 🌙 今日总结\n\n"
        "## ⏰ 待办提醒\n"
        f"{_reminder_table(day_data)}\n\n"
        "## 💰 财务简讯\n"
        f"{_finance_summary_table(day_data)}\n\n"
        "## 📝 日记草稿\n\n"
        f"{(diary_draft or _daily_diary_fallback(day_data)).strip()}"
    )


def _weekly_snapshot(range_data: dict[str, list[dict]]) -> str:
    finance = range_data.get("finance") or []
    plans = range_data.get("plans") or []
    health = range_data.get("health") or []
    income = sum(float(item.get("amount") or 0) for item in finance if item.get("direction") == "收入")
    expense = sum(float(item.get("amount") or 0) for item in finance if item.get("direction") == "支出")
    completed = len([item for item in plans if item.get("status") == "已完成"])
    active = len([item for item in plans if item.get("status") not in {"已完成", "取消", "已取消"}])
    run_distance = sum(float(item.get("distance_km") or 0) for item in health if item.get("metric_type") == "跑步")
    quote_count = len([item for item in range_data.get("notes") or [] if item.get("category") == "语录笔记"])
    return "\n".join(
        [
            "## 本周概览",
            f"- 财务：收入 ¥{income:.2f}，支出 ¥{expense:.2f}，净流入 ¥{income - expense:.2f}",
            f"- 计划：完成 {completed} 项，未完成/推进中 {active} 项",
            f"- 健康：跑步 {run_distance:.2f} 公里，健康记录 {len(health)} 条",
            f"- 语录：{quote_count} 条可精选素材",
        ]
    )


async def generate_daily_summary_text(
    *,
    day_data: dict[str, list[dict]],
    llm_call: Callable[[str], Awaitable[str | None]],
    include_conversations: bool = False,
) -> tuple[str, bool]:
    data_text = build_day_data_text(day_data, include_conversations=include_conversations)
    if not data_text:
        return "今天还没有可总结的生活记录。", False

    diary_draft = await llm_call(prompts.DAILY_SUMMARY_PROMPT.format(data=data_text))

    return _compact_daily_summary(day_data, diary_draft=diary_draft), True


async def generate_diary_draft_text(
    *,
    day_data: dict[str, list[dict]],
    llm_call: Callable[[str], Awaitable[str | None]],
    include_conversations: bool = False,
) -> tuple[str, bool]:
    data_text = build_day_data_text(day_data, include_conversations=include_conversations)
    if not data_text:
        return "今天还没有可整理成日记草稿的生活记录。", False

    llm_text = await llm_call(prompts.DIARY_DRAFT_PROMPT.format(data=data_text))
    if llm_text:
        return llm_text, True

    return (
        "# 日记草稿\n\n"
        "今天的记录可以整理成下面这些线索。\n\n"
        "## 素材\n"
        f"{data_text}\n\n"
        "## 成文提示\n"
        "今天发生了什么，我做了哪些选择，有什么情绪和收获，明天想怎样继续。"
    ), True


async def generate_weekly_summary_text(
    *,
    range_data: dict[str, list[dict]],
    llm_call: Callable[[str], Awaitable[str | None]],
) -> tuple[str, bool]:
    data_text = build_range_data_text(range_data)
    if not data_text:
        return "本周还没有可总结的生活记录。", False

    llm_text = await llm_call(prompts.WEEKLY_SUMMARY_PROMPT.format(data=data_text))
    if llm_text:
        return llm_text, True

    return (
        "# 本周生活周报\n\n"
        f"{_weekly_snapshot(range_data)}\n\n"
        "## 本周事实\n"
        f"{data_text}\n\n"
        "## 下周建议\n"
        "- 计划：只保留 1-3 件真正重要的推进项。\n"
        "- 财务：优先复盘最大支出分类和借贷变化。\n"
        "- 健康：保留已经有效的运动/睡眠节奏。"
    ), True


async def generate_quote_weekly_text(
    *,
    notes: list[dict],
    llm_call: Callable[[str], Awaitable[str | None]],
) -> tuple[str, bool]:
    data_text = build_quote_data_text(notes)
    if not data_text:
        return "本周还没有可精选的语录笔记。", False

    llm_text = await llm_call(prompts.QUOTE_WEEKLY_PROMPT.format(data=data_text))
    if llm_text:
        return llm_text, True

    return (
        "# 每周语录精选\n\n"
        "## 候选语录\n"
        f"{data_text}\n\n"
        "## 精选提示\n"
        "挑出最能提醒当前自己的句子，并写一句为什么它值得留下。"
    ), True
