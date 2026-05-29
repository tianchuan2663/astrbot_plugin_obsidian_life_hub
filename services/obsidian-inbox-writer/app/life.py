from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
import re


DEFAULT_LIFE_ROOT = "生活"
DEFAULT_DIARY_FOLDER = "日记"
DEFAULT_NOTES_FOLDER = "笔记"
DEFAULT_FINANCE_FOLDER = "财务"
DEFAULT_SUMMARY_FOLDER = "总结"
DEFAULT_PLAN_FOLDER = "待办"
DEFAULT_HEALTH_FOLDER = "健康"
REMINDER_FOLDER = "备忘录"
PLAN_LIST_FOLDER = "计划"


@dataclass(frozen=True)
class LifeWriteResult:
    path: Path
    relative_path: str
    kind: str


@dataclass(frozen=True)
class DiaryEvent:
    date: str
    time: str
    content: str
    category: str = "日记"
    mood: str | None = None
    platform: str = "QQ"
    sender_id: str = "unknown"
    record_uid: str | None = None
    life_root: str = DEFAULT_LIFE_ROOT
    diary_folder: str = DEFAULT_DIARY_FOLDER


@dataclass(frozen=True)
class LifeNote:
    date: str
    time: str
    title: str
    content: str
    category: str = "随想笔记"
    original_content: str | None = None
    platform: str = "QQ"
    sender_id: str = "unknown"
    record_uid: str | None = None
    life_root: str = DEFAULT_LIFE_ROOT
    notes_folder: str = DEFAULT_NOTES_FOLDER


@dataclass(frozen=True)
class FinanceRecord:
    date: str
    time: str
    amount: float
    direction: str = "支出"
    category: str = "其他"
    note: str | None = None
    merchant: str | None = None
    wallet: str | None = None
    counterparty: str | None = None
    status: str = "已记录"
    platform: str = "QQ"
    sender_id: str = "unknown"
    record_uid: str | None = None
    life_root: str = DEFAULT_LIFE_ROOT
    finance_folder: str = DEFAULT_FINANCE_FOLDER


@dataclass(frozen=True)
class FinanceStatusUpdate:
    date: str
    time: str
    title: str
    status: str
    note: str | None = None
    platform: str = "QQ"
    sender_id: str = "unknown"
    life_root: str = DEFAULT_LIFE_ROOT
    finance_folder: str = DEFAULT_FINANCE_FOLDER


@dataclass(frozen=True)
class PlanRecord:
    date: str
    time: str
    title: str
    content: str
    plan_scope: str = "其它"
    priority: str = "中"
    status: str = "未开始"
    target_date: str | None = None
    target_time: str | None = None
    platform: str = "QQ"
    sender_id: str = "unknown"
    record_uid: str | None = None
    life_root: str = DEFAULT_LIFE_ROOT
    plan_folder: str = DEFAULT_PLAN_FOLDER


@dataclass(frozen=True)
class HealthRecord:
    date: str
    time: str
    metric_type: str
    value: float | None = None
    unit: str | None = None
    duration_minutes: float | None = None
    distance_km: float | None = None
    note: str | None = None
    status: str = "已记录"
    platform: str = "QQ"
    sender_id: str = "unknown"
    record_uid: str | None = None
    life_root: str = DEFAULT_LIFE_ROOT
    health_folder: str = DEFAULT_HEALTH_FOLDER


@dataclass(frozen=True)
class PlanStatusUpdate:
    date: str
    time: str
    title: str
    status: str
    note: str | None = None
    platform: str = "QQ"
    sender_id: str = "unknown"
    life_root: str = DEFAULT_LIFE_ROOT
    plan_folder: str = DEFAULT_PLAN_FOLDER


@dataclass(frozen=True)
class LifeDocument:
    date: str
    time: str
    content: str
    title: str | None = None
    document_type: str = "日总结"
    platform: str = "QQ"
    sender_id: str = "unknown"
    life_root: str = DEFAULT_LIFE_ROOT
    summary_folder: str = DEFAULT_SUMMARY_FOLDER


def append_diary_event(vault_root: Path, item: DiaryEvent) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _diary_path(root, item)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _write_text(path, _initial_daily_content(item.date, "life-diary", "日记", "diary"))

    entry = (
        "\n\n"
        f"## {_one_line(item.time)}\n\n"
        f"{item.content.strip()}\n\n"
        f"{_record_meta_comment('diary', item.record_uid, item.platform, item.sender_id)}\n"
    )
    _append_text(path, entry)
    return _result(root, path, "diary")


def write_life_note(vault_root: Path, item: LifeNote) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _note_path(root, item)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _write_text(path, _initial_note_content(item.date, item.category))

    entry = _note_table_row(item)
    _append_text(path, entry)
    return _result(root, path, "note")


def append_finance_record(vault_root: Path, item: FinanceRecord) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _finance_path(root, item)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _write_text(path, _initial_finance_content(item.date))

    note = _finance_note(item)
    row = (
        f"| {_one_line(item.date)} | {_one_line(item.time)} | "
        f"{_one_line(item.direction)} | {_format_amount(item.amount)} | "
        f"{_one_line(item.category)} | {_table_cell(item.wallet)} | "
        f"{_table_cell(item.counterparty)} | {_one_line(item.status)} | {_table_cell(note)} |\n"
    )
    _append_text(path, _row_with_record_meta(row, "finance", item.record_uid, item.platform, item.sender_id))
    return _result(root, path, "finance")


def append_finance_status_update(vault_root: Path, item: FinanceStatusUpdate) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _finance_status_path(root, item)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _write_text(path, _initial_finance_content(item.date))
    _ensure_finance_status_log(path)

    note = f"；{_one_line(item.note)}" if item.note else ""
    entry = (
        f"- {item.date} {item.time}：`{_one_line(item.title)}` 标记为 **{_one_line(item.status)}**"
        f"{note}\n"
    )
    _append_text(path, entry)
    return _result(root, path, "finance")


def append_plan_record(vault_root: Path, item: PlanRecord) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _plan_path(root, item.life_root, item.plan_folder)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _write_text(path, _initial_plan_content(item.date))

    section = _plan_section(item.plan_scope)
    start_time = _join_date_time(item.target_date, item.target_time)
    row = (
        f"| {_table_cell(item.content or item.title)} | {_one_line(item.status)} | "
        f"{_table_cell(start_time)} |  | {_one_line(item.date)} |  |\n"
    )
    _append_row_to_section(path, section, _row_with_record_meta(row, "plan", item.record_uid, item.platform, item.sender_id))
    return _result(root, path, "plan")


def append_health_record(vault_root: Path, item: HealthRecord) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _health_path(root, item)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _write_text(path, _initial_health_content(item.date))

    note = _health_note(item)
    row = (
        f"| {_one_line(item.date)} | {_one_line(item.time)} | {_one_line(item.metric_type)} | "
        f"{_table_cell(_format_optional_number(item.value))} | {_table_cell(item.unit)} | "
        f"{_table_cell(_format_optional_number(item.duration_minutes))} | "
        f"{_table_cell(_format_optional_number(item.distance_km))} | {_one_line(item.status)} | "
        f"{_table_cell(note)} |\n"
    )
    _append_text(path, _row_with_record_meta(row, "health", item.record_uid, item.platform, item.sender_id))
    return _result(root, path, "health")


def collect_life_recovery_records(
    vault_root: Path,
    *,
    life_root: str = DEFAULT_LIFE_ROOT,
    finance_folder: str = DEFAULT_FINANCE_FOLDER,
    plan_folder: str = DEFAULT_PLAN_FOLDER,
    health_folder: str = DEFAULT_HEALTH_FOLDER,
) -> dict[str, list[dict[str, object]]]:
    root = _require_vault_root(vault_root)
    safe_life_root = _safe_segment(life_root, "life_root")
    result: dict[str, list[dict[str, object]]] = {"finance": [], "plans": [], "health": []}

    finance_dir = _safe_life_path(root, safe_life_root, finance_folder)
    if finance_dir.exists():
        for path in sorted(finance_dir.glob("*.md")):
            result["finance"].extend(_parse_finance_markdown(root, path))

    plan_path = _plan_path(root, safe_life_root, plan_folder)
    if plan_path.exists():
        result["plans"].extend(_parse_plan_markdown(root, plan_path))

    health_dir = _safe_life_path(root, safe_life_root, health_folder)
    if health_dir.exists():
        for path in sorted(health_dir.glob("*.md")):
            result["health"].extend(_parse_health_markdown(root, path))

    return result


def append_plan_status_update(vault_root: Path, item: PlanStatusUpdate) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _plan_path(root, item.life_root, item.plan_folder)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _write_text(path, _initial_plan_content(item.date))

    if not _update_plan_row_status(path, item.title, item.status, item.date, item.time, item.note):
        note = f"；{_one_line(item.note)}" if item.note else ""
        _ensure_plan_status_log(path)
        entry = f"- {item.date} {item.time}：`{_one_line(item.title)}` 标记为 **{_one_line(item.status)}**{note}\n"
        _append_text(path, entry)
    return _result(root, path, "plan")


def write_summary_document(vault_root: Path, item: LifeDocument) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _summary_path(root, item)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        title = item.title or f"{item.date} {item.document_type}"
        _write_text(path, _initial_summary_content(item.date, title, item.document_type))

    entry = (
        "\n\n"
        f"## {_one_line(item.date)} {_one_line(item.time)}\n\n"
        f"{item.content.strip()}\n"
    )
    _append_text(path, entry)
    return _result(root, path, _document_kind(item.document_type))


def _diary_path(root: Path, item: DiaryEvent) -> Path:
    date = _parse_date(item.date)
    return _safe_life_path(
        root,
        item.life_root,
        item.diary_folder,
        str(date.year),
        f"{date.year}-{date.month:02d}",
        f"{item.date}.md",
    )


def _note_path(root: Path, item: LifeNote) -> Path:
    month = item.date[:7]
    category = _note_category(item.category)
    if category == REMINDER_FOLDER:
        return _safe_life_path(
            root,
            item.life_root,
            DEFAULT_PLAN_FOLDER,
            REMINDER_FOLDER,
            f"{month} {REMINDER_FOLDER}.md",
        )
    return _safe_life_path(
        root,
        item.life_root,
        item.notes_folder,
        category,
        f"{month} {category}.md",
    )


def _finance_path(root: Path, item: FinanceRecord) -> Path:
    date = _parse_date(item.date)
    return _safe_life_path(
        root,
        item.life_root,
        item.finance_folder,
        f"{date.year}-{date.month:02d} 财务.md",
    )


def _finance_status_path(root: Path, item: FinanceStatusUpdate) -> Path:
    date = _parse_date(item.date)
    return _safe_life_path(
        root,
        item.life_root,
        item.finance_folder,
        f"{date.year}-{date.month:02d} 财务.md",
    )


def _health_path(root: Path, item: HealthRecord) -> Path:
    date = _parse_date(item.date)
    return _safe_life_path(
        root,
        item.life_root,
        item.health_folder,
        f"{date.year}-{date.month:02d} 健康.md",
    )


def _summary_path(root: Path, item: LifeDocument) -> Path:
    document_type = _safe_segment(item.document_type, "document_type")
    return _safe_life_path(
        root,
        item.life_root,
        item.summary_folder,
        document_type,
        f"{item.date}.md",
    )


def _plan_path(root: Path, life_root: str, plan_folder: str) -> Path:
    return _safe_life_path(root, life_root, plan_folder, PLAN_LIST_FOLDER, "计划清单.md")


def _safe_life_path(root: Path, life_root: str, *parts: str) -> Path:
    safe_parts = [_safe_segment(life_root, "life_root")]
    safe_parts.extend(_safe_segment(part, "path segment") for part in parts)
    candidate = root.joinpath(*safe_parts).resolve()
    life_root_path = root.joinpath(safe_parts[0]).resolve()

    if not _is_relative_to(candidate, life_root_path):
        raise ValueError("resolved life path escaped life root")
    if not _is_relative_to(candidate, root):
        raise ValueError("resolved life path escaped vault root")
    return candidate


def _require_vault_root(vault_root: Path) -> Path:
    root = vault_root.resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"vault root does not exist: {root}")
    return root


def _initial_daily_content(date_text: str, page_type: str, title: str, tag: str) -> str:
    return (
        "---\n"
        f"type: {page_type}\n"
        "status: active\n"
        f"created: {date_text}\n"
        f"updated: {date_text}\n"
        f"tags: [life, {tag}]\n"
        "---\n\n"
        f"# {date_text} {title}"
    )


def _initial_note_content(date_text: str, category: str) -> str:
    month = date_text[:7]
    normalized = _note_category(category)
    if normalized == "语录笔记":
        table = (
            "| 日期 | 来源 | 作者/账号 | 语录 | 标签 | 一句话感想 |\n"
            "|---|---|---|---|---|---|\n"
        )
    elif normalized == REMINDER_FOLDER:
        table = (
            "| 内容 | 截止日期 | 截止时间 | 状态 | 创建时间 |\n"
            "|---|---|---|---|---|\n"
        )
    else:
        table = (
            "| 日期 | 内容 | 标签 | 备注 |\n"
            "|---|---|---|---|\n"
        )
    return (
        "---\n"
        "type: life-note\n"
        "status: active\n"
        f"created: {date_text}\n"
        f"updated: {date_text}\n"
        "tags: [life, note]\n"
        "---\n\n"
        f"# {month} {normalized}\n\n"
        f"{table}"
    )


def _initial_finance_content(date_text: str) -> str:
    month = date_text[:7]
    return (
        "---\n"
        "type: life-finance\n"
        "status: active\n"
        f"created: {date_text}\n"
        f"updated: {date_text}\n"
        "tags: [life, finance]\n"
        "---\n\n"
        f"# {month} 财务\n\n"
        "| 日期 | 时间 | 类型 | 金额 | 类别 | 钱包/渠道 | 对象 | 状态 | 备注 |\n"
        "|---|---:|---|---:|---|---|---|---|---|\n"
    )


def _initial_health_content(date_text: str) -> str:
    month = date_text[:7]
    return (
        "---\n"
        "type: life-health\n"
        "status: active\n"
        f"created: {date_text}\n"
        f"updated: {date_text}\n"
        "tags: [life, health]\n"
        "---\n\n"
        f"# {month} 健康\n\n"
        "| 日期 | 时间 | 类型 | 数值 | 单位 | 时长分钟 | 距离公里 | 状态 | 备注 |\n"
        "|---|---:|---|---:|---|---:|---:|---|---|\n"
    )


def _initial_plan_content(date_text: str) -> str:
    table = (
        "| 计划内容 | 状态 | 开始时间 | 完成时间 | 创建时间 | 备注 |\n"
        "|---|---|---|---|---|---|\n"
    )
    return (
        "---\n"
        "type: life-plan\n"
        "status: active\n"
        f"created: {date_text}\n"
        f"updated: {date_text}\n"
        "tags: [life, plan]\n"
        "---\n\n"
        "# 计划清单\n\n"
        f"## 短期计划\n\n{table}\n"
        f"## 长期计划\n\n{table}\n"
        f"## 其它计划\n\n{table}"
    )


def _initial_summary_content(date_text: str, title: str, document_type: str) -> str:
    return (
        "---\n"
        "type: life-summary\n"
        "status: active\n"
        f"created: {date_text}\n"
        f"updated: {date_text}\n"
        "tags: [life, summary]\n"
        "---\n\n"
        f"# {title}\n\n"
        f"- 类型：{_one_line(document_type)}"
    )


def _finance_note(item: FinanceRecord) -> str:
    parts = []
    if item.merchant:
        parts.append(_one_line(item.merchant))
    if item.note:
        parts.append(_one_line(item.note))
    return "<br>".join(parts)


def _health_note(item: HealthRecord) -> str:
    parts = []
    if item.note:
        parts.append(_one_line(item.note))
    return "<br>".join(parts)


def _note_table_row(item: LifeNote) -> str:
    category = _note_category(item.category)
    if category == "语录笔记":
        fields = _quote_fields(item)
        row = (
            f"| {_one_line(item.date)} | {_table_cell(fields['source'])} | {_table_cell(fields['author'])} | "
            f"{_table_cell(fields['quote'])} | {_table_cell(fields['tags'])} | {_table_cell(fields['comment'])} |\n"
        )
        return _row_with_record_meta(row, "note", item.record_uid, item.platform, item.sender_id)
    if category == REMINDER_FOLDER:
        due_date, due_time, body = _reminder_fields(item.content)
        row = (
            f"| {_table_cell(body)} | {_table_cell(due_date)} | {_table_cell(due_time)} | "
            f"未完成 | {_one_line(item.date)} |\n"
        )
        return _row_with_record_meta(row, "reminder", item.record_uid, item.platform, item.sender_id)
    content = _table_cell(_strip_note_labels(item.content))
    tags = _tags_from_text(item.content)
    row = f"| {_one_line(item.date)} | {content} | {_table_cell(tags)} |  |\n"
    return _row_with_record_meta(row, "note", item.record_uid, item.platform, item.sender_id)


def _note_category(category: str) -> str:
    text = _one_line(category)
    if text in {"语录", "语录笔记"}:
        return "语录笔记"
    if text in {"备忘", "备忘录", "DDL"}:
        return REMINDER_FOLDER
    if text in {"随想", "随想笔记"}:
        return "随想笔记"
    return text


def _quote_fields(item: LifeNote) -> dict[str, str]:
    content = item.content
    return {
        "source": _field_value(content, ("来源",)) or getattr(item, "source", "") or "",
        "author": _field_value(content, ("作者或账号", "作者", "账号")) or "",
        "quote": _field_value(content, ("原句", "语录")) or item.title or _strip_note_labels(content),
        "tags": _field_value(content, ("标签",)) or _tags_from_text(content),
        "comment": _field_value(content, ("一句话感想", "感想")) or "",
    }


def _reminder_fields(content: str) -> tuple[str, str, str]:
    lines = [line.strip() for line in str(content or "").splitlines() if line.strip()]
    due_text = ""
    body_parts: list[str] = []
    for line in lines:
        if line.startswith("截止时间："):
            due_text = line.removeprefix("截止时间：").strip()
        else:
            body_parts.append(line)
    due_date = ""
    due_time = ""
    if due_text and due_text != "未设置":
        match = re.match(r"(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?", due_text)
        if match:
            due_date = match.group(1) or ""
            due_time = match.group(2) or ""
        else:
            due_date = due_text
    return due_date, due_time, " ".join(body_parts).strip()


def _field_value(text: str, labels: Iterable[str]) -> str:
    for label in labels:
        pattern = rf"{re.escape(label)}[：:]\s*([^\n]+)"
        match = re.search(pattern, str(text or ""))
        if match:
            return match.group(1).strip()
    return ""


def _strip_note_labels(text: str) -> str:
    lines = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if re.match(r"^(来源|作者或账号|作者|账号|标签|一句话感想|感想|原句|语录)[：:]", stripped):
            continue
        lines.append(stripped)
    return " ".join(line for line in lines if line).strip()


def _tags_from_text(text: str) -> str:
    tags = re.findall(r"#([\w\u4e00-\u9fff-]+)", str(text or ""))
    return " ".join(f"#{tag}" for tag in tags)


def _row_with_record_meta(
    row: str,
    kind: str,
    record_uid: str | None,
    platform: str | None,
    sender_id: str | None,
) -> str:
    comment = _record_meta_comment(kind, record_uid, platform, sender_id)
    line = str(row or "").rstrip("\n")
    if not comment:
        return f"{line}\n"
    return f"{line} {comment}\n"


def _record_meta_comment(kind: str, record_uid: str | None, platform: str | None, sender_id: str | None) -> str:
    parts = [f"kind={_one_line(kind)}"]
    if record_uid:
        parts.append(f"record_id={_one_line(record_uid)}")
    if len(parts) == 1:
        return ""
    return f"<!-- olh {';'.join(parts)} -->"


def _join_date_time(date_text: str | None, time_text: str | None) -> str:
    return " ".join(part for part in (date_text, time_text) if part).strip()


def _split_date_time(value: str) -> tuple[str | None, str | None]:
    text = str(value or "").strip()
    if not text:
        return None, None
    match = re.match(r"(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?", text)
    if not match:
        return text, None
    return match.group(1), match.group(2)


def _plan_section(plan_scope: str) -> str:
    text = _one_line(plan_scope)
    if text in {"长期", "长期计划", "long_term"}:
        return "长期计划"
    if text in {"短期", "短期计划", "近期", "日", "周", "月", "today", "week", "month"}:
        return "短期计划"
    return "其它计划"


def _append_row_to_section(path: Path, section_title: str, row: str) -> None:
    content = path.read_text(encoding="utf-8")
    marker = f"## {section_title}"
    start = content.find(marker)
    if start == -1:
        _append_text(path, f"\n\n{marker}\n\n| 计划内容 | 状态 | 开始时间 | 完成时间 | 创建时间 | 备注 |\n|---|---|---|---|---|---|\n{row}")
        return
    next_section = content.find("\n## ", start + len(marker))
    insert_at = len(content) if next_section == -1 else next_section + 1
    updated = content[:insert_at].rstrip() + "\n" + row + content[insert_at:]
    _write_text(path, updated)


def _update_plan_row_status(
    path: Path,
    title: str,
    status: str,
    date_text: str,
    time_text: str,
    note: str | None,
) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    keyword = str(title or "").strip()
    if not keyword:
        return False
    changed = False
    for index, line in enumerate(lines):
        cells = _markdown_table_cells(line)
        if len(cells) != 6 or cells[0] == "计划内容" or cells[0].startswith("---"):
            continue
        if not _loose_keyword_match(keyword, cells[0]):
            continue
        cells[1] = _one_line(status)
        if status == "已完成" and not cells[3]:
            cells[3] = _join_date_time(date_text, time_text)
        if note:
            visible_note = _strip_hidden_metadata(cells[5])
            cells[5] = _table_cell(f"{visible_note}；{_one_line(note)}" if visible_note else _one_line(note))
        lines[index] = "| " + " | ".join(_table_cell(cell) for cell in cells) + " |" + _hidden_metadata_suffix(line)
        changed = True
        break
    if changed:
        _write_text(path, "\n".join(lines) + "\n")
    return changed


def _loose_keyword_match(keyword: str, text: str) -> bool:
    compact_keyword = re.sub(r"\s+", "", keyword)
    compact_text = re.sub(r"\s+", "", text)
    if not compact_keyword:
        return False
    if compact_keyword in compact_text:
        return True
    return all(char in compact_text for char in compact_keyword)


def _ensure_plan_status_log(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    if "## 计划变更记录" in content:
        return
    _append_text(path, "\n\n## 计划变更记录\n\n")


def _ensure_finance_v2_table(path: Path) -> None:
    marker = "| 日期 | 时间 | 类型 | 金额 | 类别 | 钱包/渠道 | 对象 | 状态 | 备注 |"
    content = path.read_text(encoding="utf-8")
    if marker in content:
        return
    _append_text(
        path,
        "\n\n## V2 明细\n\n"
        f"{marker}\n"
        "|---|---:|---|---:|---|---|---|---|---|\n",
    )


def _ensure_finance_status_log(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    if "## 修正记录" in content:
        return
    _append_text(path, "\n\n## 修正记录\n\n")


def _parse_finance_markdown(root: Path, path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = _markdown_table_cells(line)
        if len(cells) != 9 or cells[0] == "日期" or cells[0].startswith("---"):
            continue
        record_uid = _extract_record_uid(line)
        if not record_uid:
            continue
        try:
            amount = float(cells[3])
        except ValueError:
            continue
        note = _strip_record_uid(cells[8])
        records.append(
            {
                "record_uid": record_uid,
                "record_date": cells[0],
                "record_time": cells[1],
                "direction": cells[2],
                "amount": amount,
                "category": cells[4],
                "wallet": cells[5],
                "counterparty": cells[6],
                "status": cells[7] or "已记录",
                "note": _metadata_to_text(note),
                "markdown_path": path.relative_to(root).as_posix(),
            }
        )
    return records


def _parse_plan_markdown(root: Path, path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    current_scope = "其它"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current_scope = line.removeprefix("## ").replace("计划", "").strip() or "其它"
            continue
        cells = _markdown_table_cells(line)
        if len(cells) != 6 or cells[0] == "计划内容" or cells[0].startswith("---"):
            continue
        record_uid = _extract_record_uid(line)
        if not record_uid:
            continue
        target_date, target_time = _split_date_time(cells[2])
        records.append(
            {
                "record_uid": record_uid,
                "plan_date": cells[4],
                "plan_time": "",
                "plan_scope": current_scope,
                "target_date": target_date,
                "target_time": target_time,
                "priority": "中",
                "status": cells[1] or "未开始",
                "title": cells[0],
                "content": cells[0],
                "markdown_path": path.relative_to(root).as_posix(),
            }
        )
    return records


def _parse_health_markdown(root: Path, path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = _markdown_table_cells(line)
        if len(cells) != 9 or cells[0] == "日期" or cells[0].startswith("---"):
            continue
        record_uid = _extract_record_uid(line)
        if not record_uid:
            continue
        records.append(
            {
                "record_uid": record_uid,
                "record_date": cells[0],
                "record_time": cells[1],
                "metric_type": cells[2],
                "value": _optional_float(cells[3]),
                "unit": cells[4],
                "duration_minutes": _optional_float(cells[5]),
                "distance_km": _optional_float(cells[6]),
                "status": cells[7] or "已记录",
                "note": _metadata_to_text(_strip_record_uid(cells[8])),
                "markdown_path": path.relative_to(root).as_posix(),
            }
        )
    return records


def _markdown_table_cells(line: str) -> list[str]:
    text = _strip_hidden_metadata(line).strip()
    if not text.startswith("|") or not text.endswith("|"):
        return []
    return [_clean_cell(cell) for cell in text.strip("|").split("|")]


def _clean_cell(value: str) -> str:
    return str(value or "").strip().replace("｜", "|")


def _extract_record_uid(text: str) -> str:
    match = re.search(r"record_id[=:]\s*([A-Za-z0-9_-]+)", str(text or ""))
    return match.group(1) if match else ""


def _strip_record_uid(text: str) -> str:
    cleaned = re.sub(r"(?:<br>)?\s*record_id[=:]\s*[A-Za-z0-9_-]+", "", str(text or ""))
    return _strip_hidden_metadata(cleaned)


def _strip_hidden_metadata(text: str) -> str:
    return re.sub(r"\s*<!--\s*olh\b.*?-->\s*", "", str(text or "")).strip()


def _hidden_metadata_suffix(text: str) -> str:
    match = re.search(r"\s*(<!--\s*olh\b.*?-->)\s*$", str(text or ""))
    return f" {match.group(1)}" if match else ""


def _metadata_to_text(text: str) -> str:
    parts = []
    for part in _strip_hidden_metadata(text).split("<br>"):
        item = part.strip()
        if not item or item.startswith("来源：") or item.startswith("sender_id:"):
            continue
        parts.append(item)
    return " ".join(parts).strip()


def _optional_float(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _table_cell(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().replace("|", "｜")


def _format_optional_number(value: float | None) -> str:
    if value is None:
        return ""
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _result(root: Path, path: Path, kind: str) -> LifeWriteResult:
    return LifeWriteResult(path=path, relative_path=path.relative_to(root).as_posix(), kind=kind)


def _document_kind(document_type: str) -> str:
    text = _one_line(document_type)
    if text == "晨报":
        return "briefing"
    return "summary"


def _parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"invalid date: {value}") from exc


def _safe_segment(value: str, field_name: str) -> str:
    text = _one_line(value)
    if not text:
        raise ValueError(f"empty {field_name}")
    if text in {".", ".."} or "/" in text or "\\" in text or ":" in text:
        raise ValueError(f"invalid {field_name}: {text}")
    return text


def _safe_filename(value: str) -> str:
    text = _one_line(value)
    text = re.sub(r'[\\/:*?"<>|]+', "-", text)
    text = text.strip(" .-")
    if not text or text in {".", ".."}:
        text = "未命名"
    return text[:80]


def _format_amount(value: float) -> str:
    return f"{float(value):.2f}"


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _append_text(path: Path, content: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def _one_line(value: str | None) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    return cleaned or "unknown"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
