from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import re
from zoneinfo import ZoneInfo


AT_PREFIX_RE = re.compile(r"^\s*(?:\[At:[^\]]+\]\s*)+")
TIME_RE = re.compile(r"(?:(凌晨|早上|上午|中午|下午|晚上|今晚)\s*)?(\d{1,2})[:：点](?:(\d{1,2})分?)?")
CHINESE_TIME_RE = re.compile(
    r"(?:(凌晨|早上|上午|中午|下午|晚上|今晚)\s*)?([零〇一二两三四五六七八九十]{1,4})点(?:(半)|([零〇一二三四五六七八九十]{1,4})分?)?"
)
DATE_RE = re.compile(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?")
MONTH_DAY_RE = re.compile(r"(\d{1,2})月(\d{1,2})日?")
TRIGGER_RE = re.compile(r"提醒(?:一下)?我")


@dataclass(frozen=True)
class NativeFutureTask:
    run_at: datetime
    title: str
    note: str
    cron_expression: str | None = None
    run_once: bool = True
    repeat_label: str = ""


def parse_native_future_task(message: str, *, now: datetime | None = None, timezone: str = "Asia/Shanghai") -> NativeFutureTask | None:
    text = _normalize_message(message)
    if "提醒我" not in text and "提醒一下我" not in text:
        return None

    tz = ZoneInfo(timezone or "Asia/Shanghai")
    base = now.astimezone(tz) if now and now.tzinfo else (now.replace(tzinfo=tz) if now else datetime.now(tz))
    repeat_daily = any(word in text for word in ("每天", "每日", "天天"))
    parsed_date, date_span = _parse_date(text, base.date())
    parsed_time, time_span, explicit_period = _parse_time(text)
    if not parsed_time:
        return None

    target_date = parsed_date or base.date()
    run_at = datetime.combine(target_date, parsed_time, tzinfo=tz)
    if not repeat_daily and parsed_date is None and not explicit_period and parsed_time.hour <= 11 and run_at <= base:
        afternoon = datetime.combine(target_date, time(parsed_time.hour + 12, parsed_time.minute), tzinfo=tz)
        if afternoon > base:
            run_at = afternoon
    if repeat_daily and run_at <= base:
        run_at += timedelta(days=1)
    elif parsed_date is None and run_at <= base:
        run_at += timedelta(days=1)
    if run_at <= base:
        return None

    note = _extract_note(text, date_span, time_span)
    if not note:
        return None
    title = _title_from_note(note)
    if repeat_daily:
        note = _strip_leading_period_word(note)
        if not note:
            return None
        title = _title_from_note(note)
        return NativeFutureTask(
            run_at=run_at,
            title=title,
            note=note,
            cron_expression=f"{parsed_time.minute} {parsed_time.hour} * * *",
            run_once=False,
            repeat_label="每天",
        )
    return NativeFutureTask(run_at=run_at, title=title, note=note)


def looks_like_incomplete_native_future_task(message: str) -> bool:
    text = _normalize_message(message)
    if "提醒我" not in text and "提醒一下我" not in text:
        return False
    temporal_words = ("今天", "今晚", "明天", "后天", "大后天", "每天", "每日", "天天", "上午", "下午", "晚上", "凌晨", "中午", "点", ":", "：", "月", "日")
    return any(word in text for word in temporal_words)


def _normalize_message(message: str) -> str:
    text = AT_PREFIX_RE.sub("", str(message or "")).strip()
    return re.sub(r"\s+", " ", text)


def _parse_date(text: str, today: date) -> tuple[date | None, tuple[int, int] | None]:
    for word, offset in (("大后天", 3), ("后天", 2), ("明天", 1), ("今天", 0), ("今晚", 0)):
        idx = text.find(word)
        if idx >= 0:
            return today + timedelta(days=offset), (idx, idx + len(word))

    match = DATE_RE.search(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return date(year, month, day), match.span()

    match = MONTH_DAY_RE.search(text)
    if match:
        month, day = (int(part) for part in match.groups())
        year = today.year
        candidate = date(year, month, day)
        if candidate < today:
            candidate = date(year + 1, month, day)
        return candidate, match.span()

    return None, None


def _parse_time(text: str) -> tuple[time | None, tuple[int, int] | None, bool]:
    match = TIME_RE.search(text)
    if match:
        period, hour_text, minute_text = match.groups()
        hour = int(hour_text)
        minute = int(minute_text or 0)
        return _make_time(period, hour, minute), match.span(), bool(period)

    match = CHINESE_TIME_RE.search(text)
    if match:
        period, hour_text, half, minute_text = match.groups()
        hour = _chinese_number(hour_text)
        minute = 30 if half else (_chinese_number(minute_text) if minute_text else 0)
        return _make_time(period, hour, minute), match.span(), bool(period)

    return None, None, False


def _make_time(period: str | None, hour: int, minute: int) -> time | None:
    if not 0 <= minute <= 59:
        return None
    period = period or ""
    if period in {"下午", "晚上", "今晚"} and 1 <= hour <= 11:
        hour += 12
    elif period == "中午" and 1 <= hour <= 10:
        hour += 12
    elif period == "凌晨" and hour == 12:
        hour = 0
    if not 0 <= hour <= 23:
        return None
    return time(hour, minute)


def _chinese_number(text: str | None) -> int:
    if not text:
        return 0
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = digits.get(left, 1) if left else 1
        ones = digits.get(right, 0) if right else 0
        return tens * 10 + ones
    value = 0
    for char in text:
        value = value * 10 + digits.get(char, 0)
    return value


def _extract_note(text: str, date_span: tuple[int, int] | None, time_span: tuple[int, int] | None) -> str:
    spans = [span for span in (date_span, time_span) if span]
    cleaned = text
    for start, end in sorted(spans, reverse=True):
        cleaned = cleaned[:start] + cleaned[end:]
    cleaned = TRIGGER_RE.sub("", cleaned, count=1)
    cleaned = re.sub(r"\b(?:每天|每日|天天)\b", "", cleaned)
    cleaned = cleaned.replace("每天", "").replace("每日", "").replace("天天", "")
    cleaned = re.sub(r"(?:凌晨|早上|上午|中午|下午|晚上|今晚)\s*点", "", cleaned)
    cleaned = cleaned.strip(" ，,。.!！:：")
    return cleaned


def _title_from_note(note: str) -> str:
    title = note.strip()
    return title[:24] if len(title) > 24 else title


def _strip_leading_period_word(note: str) -> str:
    return re.sub(r"^(?:凌晨|早上|上午|中午|下午|晚上|今晚)\s*", "", note).strip()
