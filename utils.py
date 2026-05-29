from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any


MONEY_AMOUNT_RE = re.compile(r"(?:[¥￥]\s*)?(\d+(?:\.\d+)?)\s*(?:块钱|快钱|元钱|元|块|快|rmb|RMB)?")
NON_MONEY_NEXT_CHARS = {"号", "日", "月", "年", "点", "分", "%", "％", "度"}
NON_MONEY_NEXT_WORDS = ("分钟", "小时", "秒钟", "公里", "厘米", "毫米", "米", "岁", "次", "页")

NOTE_TYPE_FOLDERS = {
    "reading": "读书笔记",
    "book": "读书笔记",
    "读书": "读书笔记",
    "gaming": "游戏笔记",
    "game": "游戏笔记",
    "游戏": "游戏笔记",
    "movie": "影视笔记",
    "影视": "影视笔记",
    "电影": "影视笔记",
    "music": "音乐笔记",
    "音乐": "音乐笔记",
    "drama": "追剧笔记",
    "追剧": "追剧笔记",
    "随想": "随想笔记",
    "idea": "随想笔记",
    "quote": "语录笔记",
    "语录": "语录笔记",
}

DIRECTION_WORDS = {
    "支出",
    "消费",
    "花费",
    "花了",
    "收入",
    "收到",
    "工资",
    "奖金",
    "报销",
    "借入",
    "借出",
    "借给",
    "借了",
    "还款",
    "还给",
    "收款",
    "转账",
}

FINANCE_DIRECTIONS = {"支出", "收入", "借入", "借出", "还款", "收款", "转账"}
LOAN_DIRECTIONS = {"借入", "借出", "还款", "收款"}
WALLET_KEYWORDS = (
    "支付宝",
    "微信",
    "中国银行",
    "建设银行",
    "工商银行",
    "农业银行",
    "招商银行",
    "交通银行",
    "银行卡",
    "信用卡",
    "花呗",
    "现金",
)


@dataclass(frozen=True)
class FinanceParse:
    amount: float
    direction: str
    description: str
    wallet: str = ""
    counterparty: str = ""


def now_date_time() -> tuple[str, str]:
    now = datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M")


def event_session_id(event: Any) -> str:
    return str(getattr(event, "unified_msg_origin", "") or event.get_sender_id() or "unknown")


def event_sender_id(event: Any) -> str:
    try:
        return str(event.get_sender_id() or "unknown")
    except Exception:
        return "unknown"


def event_platform(event: Any, default: str = "QQ") -> str:
    try:
        return str(event.get_platform_name() or default)
    except Exception:
        return default


def event_message_text(event: Any) -> str:
    try:
        return str(event.get_message_str() or "").strip()
    except Exception:
        return str(getattr(event, "message_str", "") or "").strip()


def event_sender_name(event: Any) -> str:
    try:
        return str(event.get_sender_name() or "unknown")
    except Exception:
        return "unknown"


def normalize_string_list(value: Any, default: tuple[str, ...] = ()) -> list[str]:
    if value is None:
        return list(default)

    if isinstance(value, str):
        parts = value.replace("\n", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        parts = list(value)
    else:
        return list(default)

    normalized: list[str] = []
    for item in parts:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized or list(default)


def is_sender_allowed(*, sender_id: str, allowed_sender_ids: Any) -> bool:
    allowed = normalize_string_list(allowed_sender_ids)
    if not allowed:
        return True
    return str(sender_id or "").strip() in allowed


def command_body(event: Any, command_names: Any, fallback: str = "") -> str:
    """Return the full text after an AstrBot command, even when command args are truncated."""
    raw = event_message_text(event)
    body = strip_command_name(raw, command_names)
    if body != raw:
        return body
    return str(fallback or "").strip()


def is_command_message(message: str, command_names: Any) -> bool:
    text = _strip_leading_at_segments(str(message or "").strip())
    if not text:
        return False

    for command_name in normalize_string_list(command_names):
        name = command_name.lstrip("/")
        for candidate in (f"/{name}", name):
            if text == candidate or text.startswith(f"{candidate} "):
                return True
    return False


def strip_command_name(message: str, command_names: Any) -> str:
    text = _strip_leading_at_segments(str(message or "").strip())
    if not text:
        return ""

    for command_name in normalize_string_list(command_names):
        name = command_name.lstrip("/")
        candidates = (f"/{name}", name)
        for candidate in candidates:
            if text == candidate:
                return ""
            prefix = f"{candidate} "
            if text.startswith(prefix):
                return text[len(prefix) :].strip()

    return text


def normalize_note_category(note_type: str) -> str:
    text = str(note_type or "").strip()
    return NOTE_TYPE_FOLDERS.get(text, text or "随想笔记")


def infer_finance_category(description: str) -> str:
    text = str(description or "")
    rules = [
        ("餐饮", ("饭", "早餐", "午饭", "晚饭", "咖啡", "奶茶", "外卖", "餐", "拉面", "烧烤")),
        ("交通", ("打车", "地铁", "公交", "高铁", "火车", "机票", "油费", "停车")),
        ("购物", ("买", "购物", "衣服", "鞋", "淘宝", "京东", "拼多多")),
        ("娱乐", ("电影", "游戏", "会员", "演出", "唱歌")),
        ("医疗", ("药", "医院", "体检", "挂号")),
        ("运动", ("健身", "球", "羽毛球", "跑步")),
        ("学习", ("书", "课程", "论文", "资料")),
    ]
    for category, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return category
    return "其他"


def parse_note_command(content: str) -> tuple[str, str, str] | None:
    text = str(content or "").strip()
    if not text:
        return None
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    note_type = parts[0]
    rest = parts[1].strip().replace("｜", "|", 1)
    if "|" in rest:
        title, body = (part.strip() for part in rest.split("|", 1))
    else:
        title, body = rest[:30].strip(), rest
    if not title or not body:
        return None
    return note_type, title, body


def parse_leading_tag(content: str, default_category: str) -> tuple[str, str]:
    text = str(content or "").strip()
    match = re.match(r"^#([^\s#]+)\s*(.*)$", text)
    if not match:
        return default_category, text
    category = match.group(1).strip() or default_category
    body = match.group(2).strip()
    return category, body or text


def parse_finance_command(content: str) -> tuple[float, str, str] | None:
    parsed = parse_finance_record(content)
    if not parsed:
        return None
    return parsed.amount, parsed.direction, parsed.description


def parse_finance_record(content: str, *, direction_override: str | None = None) -> FinanceParse | None:
    text = str(content or "").strip()
    if not text:
        return None
    match = find_money_amount_match(text)
    if not match:
        return None
    amount = float(match.group(1))
    description = (text[: match.start()] + text[match.end() :]).strip(" ，,。")
    description = _strip_direction_words(description)
    if not description:
        description = text
    direction = _normalize_finance_direction(direction_override) or _infer_finance_direction(text)
    wallet = infer_wallet(text)
    counterparty = infer_counterparty(text, direction=direction, wallet=wallet)
    return FinanceParse(amount, direction, description, wallet=wallet, counterparty=counterparty)


def _normalize_finance_direction(value: str | None) -> str:
    text = str(value or "").strip()
    return text if text in FINANCE_DIRECTIONS else ""


def _infer_finance_direction(text: str) -> str:
    value = str(text or "")
    if any(keyword in value for keyword in ("转账", "转到", "转入", "转出")):
        return "转账"
    if any(keyword in value for keyword in ("借出", "借给")):
        return "借出"
    if any(keyword in value for keyword in ("借入", "借款", "借了", "借到", "从")) and "还" not in value:
        return "借入"
    if any(keyword in value for keyword in ("收款", "还我", "收到还款")):
        return "收款"
    if any(keyword in value for keyword in ("还款", "还给", "还了")):
        return "还款"
    if any(keyword in value for keyword in ("收入", "工资", "奖金", "报销", "收到")):
        return "收入"
    return "支出"


def infer_wallet(text: str) -> str:
    value = str(text or "")
    for wallet in WALLET_KEYWORDS:
        if wallet in value:
            return wallet
    return ""


def infer_counterparty(text: str, *, direction: str = "", wallet: str = "") -> str:
    value = str(text or "")
    if direction not in LOAN_DIRECTIONS and direction != "转账":
        return ""

    if direction == "转账":
        transfer_match = re.search(r"(?:转到|转入)([A-Za-z_\-\u4e00-\u9fff]{1,20})", value)
        if transfer_match:
            target = transfer_match.group(1).strip(" ，,。")
            if target and target != wallet:
                return target

    patterns = (
        r"(?:给|向|找|从)([A-Za-z_\-\u4e00-\u9fff]{1,20})",
        r"([A-Za-z_\-\u4e00-\u9fff]{1,20})(?:还我|还给我)",
    )
    for pattern in patterns:
        match = re.search(pattern, value)
        if not match:
            continue
        name = match.group(1).strip(" ，,。")
        if not name or name == wallet or name in WALLET_KEYWORDS:
            continue
        if any(word in name for word in ("支付宝", "微信", "银行", "现金", "转到", "转入", "转出")):
            continue
        return name
    return ""


def find_money_amount_match(text: str) -> re.Match[str] | None:
    for match in MONEY_AMOUNT_RE.finditer(str(text or "")):
        if not _is_non_money_number(text, match):
            return match
    return None


def count_money_amounts(text: str) -> int:
    return sum(1 for match in MONEY_AMOUNT_RE.finditer(str(text or "")) if not _is_non_money_number(text, match))


def remove_money_amounts(text: str) -> str:
    value = str(text or "")
    pieces: list[str] = []
    last = 0
    for match in MONEY_AMOUNT_RE.finditer(value):
        if _is_non_money_number(value, match):
            continue
        pieces.append(value[last : match.start()])
        last = match.end()
    pieces.append(value[last:])
    return "".join(pieces)


def is_low_signal_life_message(message: str) -> bool:
    text = str(message or "").strip(" ，,。")
    return text in DIRECTION_WORDS


def truncate(text: str, limit: int) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def safe_error_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"(Bearer\s+)[^\s]+", r"\1***", text, flags=re.IGNORECASE)
    text = re.sub(r'("?(?:token|key|authorization)"?\s*[:=]\s*)[^,\s}]+', r"\1***", text, flags=re.IGNORECASE)
    return text[:500]


def _strip_leading_at_segments(text: str) -> str:
    current = text
    while True:
        cleaned = re.sub(r"^\s*\[At:[^\]]+\]\s*", "", current, count=1, flags=re.IGNORECASE)
        if cleaned == current:
            return current.strip()
        current = cleaned


def _strip_direction_words(text: str) -> str:
    value = str(text or "").strip()
    changed = True
    while changed:
        changed = False
        for word in sorted(DIRECTION_WORDS, key=len, reverse=True):
            if value == word:
                return ""
            if value.startswith(word):
                next_index = len(word)
                if next_index >= len(value) or value[next_index].isspace():
                    value = value[next_index:].strip(" ，,。")
                    changed = True
                    break
    return value


def _is_non_money_number(text: str, match: re.Match[str]) -> bool:
    suffix = str(text or "")[match.end() :]
    if suffix[:1] in NON_MONEY_NEXT_CHARS:
        return True
    return any(suffix.startswith(word) for word in NON_MONEY_NEXT_WORDS)
