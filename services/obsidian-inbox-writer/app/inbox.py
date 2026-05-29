from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import threading


TAG_CATEGORIES = {
    "#日记": "日记",
    "#灵感": "灵感",
    "#金句": "金句",
    "#链接": "链接",
    "#待办": "待办",
    "#来源": "来源",
    "#随手记": "随手记",
}

DEFAULT_CATEGORY = "随手记"
_WRITE_LOCK = threading.RLock()


@dataclass(frozen=True)
class InboxMessage:
    platform: str
    sender: str
    sender_id: str
    message: str
    raw_type: str
    received_at: datetime


@dataclass(frozen=True)
class InboxWriteResult:
    path: Path
    relative_path: str
    category: str


@contextmanager
def inbox_write_lock():
    with _WRITE_LOCK:
        yield


def append_message(vault_root: Path, item: InboxMessage) -> InboxWriteResult:
    with _WRITE_LOCK:
        root = vault_root.resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"vault root does not exist: {root}")

        inbox_path = resolve_inbox_path(root, item.received_at)
        inbox_path.parent.mkdir(parents=True, exist_ok=True)

        if not inbox_path.exists():
            with inbox_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(_initial_inbox_content(item.received_at))

        category, body = parse_category(item.message)
        entry = render_entry(item, category, body)
        with inbox_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(entry)

        relative_path = inbox_path.relative_to(root).as_posix()
        return InboxWriteResult(path=inbox_path, relative_path=relative_path, category=category)


def resolve_inbox_path(vault_root: Path, received_at: datetime) -> Path:
    date_text = received_at.strftime("%Y-%m-%d")
    inbox_dir = (vault_root / "raw" / "inbox").resolve()
    inbox_path = (inbox_dir / f"{date_text}.md").resolve()

    if inbox_path.parent != inbox_dir:
        raise ValueError("resolved inbox path escaped raw/inbox")

    return inbox_path


def parse_category(message: str) -> tuple[str, str]:
    text = message.strip()
    for tag, category in TAG_CATEGORIES.items():
        if text == tag:
            return category, ""
        if text.startswith(tag) and _is_boundary(text, len(tag)):
            return category, text[len(tag) :].lstrip()
    return DEFAULT_CATEGORY, text


def render_entry(item: InboxMessage, category: str, body: str) -> str:
    received_date = item.received_at.strftime("%Y-%m-%d %H:%M:%S")
    received_time = item.received_at.strftime("%H:%M")
    body_text = body.strip() or "(empty)"

    return (
        "\n\n"
        f"## {received_time} | {_one_line(item.platform)} | {category}\n\n"
        f"{body_text}\n\n"
        f"- sender: {_one_line(item.sender)}\n"
        f"- sender_id: {_one_line(item.sender_id)}\n"
        f"- platform: {_one_line(item.platform)}\n"
        f"- raw_type: {_one_line(item.raw_type)}\n"
        "- status: unprocessed\n"
        f"- received_at: {received_date}\n"
    )


def _initial_inbox_content(received_at: datetime) -> str:
    date_text = received_at.strftime("%Y-%m-%d")
    return (
        "---\n"
        "type: inbox\n"
        "status: active\n"
        f"created: {date_text}\n"
        f"updated: {date_text}\n"
        "source: bot\n"
        "tags: [inbox]\n"
        "---\n\n"
        f"# Inbox {date_text}"
    )


def _is_boundary(text: str, index: int) -> bool:
    return index >= len(text) or bool(re.match(r"\s", text[index]))


def _one_line(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or "unknown"
