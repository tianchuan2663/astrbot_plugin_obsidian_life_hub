from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re


DEFAULT_LIFE_ROOT = "生活"
DEFAULT_DIARY_FOLDER = "日记"
DEFAULT_NOTES_FOLDER = "笔记"
DEFAULT_FINANCE_FOLDER = "财务"
DEFAULT_SUMMARY_FOLDER = "总结"
DEFAULT_PLAN_FOLDER = "计划"
DEFAULT_HEALTH_FOLDER = "健康"


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
    plan_scope: str = "近期"
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

    mood_line = f"\n- 心情：{_one_line(item.mood)}" if item.mood else ""
    entry = (
        "\n\n"
        f"## {_one_line(item.time)} | {_one_line(item.category)}\n\n"
        f"{item.content.strip()}\n\n"
        f"- 来源：{_one_line(item.platform)}\n"
        f"- sender_id: {_one_line(item.sender_id)}\n"
        f"{_record_id_bullet(item.record_uid)}"
        "- 状态：未总结"
        f"{mood_line}\n"
    )
    _append_text(path, entry)
    return _result(root, path, "diary")


def write_life_note(vault_root: Path, item: LifeNote) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _note_path(root, item)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        title = _safe_filename(item.title)
        _write_text(path, _initial_note_content(item.date, title, item.category))

    original = ""
    if item.original_content and item.original_content.strip() != item.content.strip():
        original = f"\n\n### 原文\n\n{item.original_content.strip()}\n"

    entry = (
        "\n\n"
        f"## {_one_line(item.date)} {_one_line(item.time)}\n\n"
        f"{item.content.strip()}\n\n"
        f"- 分类：{_one_line(item.category)}\n"
        f"- 来源：{_one_line(item.platform)}\n"
        f"- sender_id: {_one_line(item.sender_id)}"
        f"{_record_id_inline(item.record_uid)}"
        f"{original}\n"
    )
    _append_text(path, entry)
    return _result(root, path, "note")


def append_finance_record(vault_root: Path, item: FinanceRecord) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _finance_path(root, item)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _write_text(path, _initial_finance_content(item.date))
    else:
        _ensure_finance_v2_table(path)

    note = _finance_note(item)
    row = (
        f"| {_one_line(item.date)} | {_one_line(item.time)} | "
        f"{_one_line(item.direction)} | {_format_amount(item.amount)} | "
        f"{_one_line(item.category)} | {_table_cell(item.wallet)} | "
        f"{_table_cell(item.counterparty)} | {_one_line(item.status)} | {note} |\n"
    )
    _append_text(path, row)
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
        f"{note}（来源：{_one_line(item.platform)}，sender_id: {_one_line(item.sender_id)}）\n"
    )
    _append_text(path, entry)
    return _result(root, path, "finance")


def append_plan_record(vault_root: Path, item: PlanRecord) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _plan_path(root, item.life_root, item.plan_folder)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _write_text(path, _initial_plan_content(item.date))

    content = item.content
    if item.record_uid:
        content = f"{content}<br>record_id: {item.record_uid}"
    row = (
        f"| {_one_line(item.date)} | {_one_line(item.time)} | {_one_line(item.plan_scope)} | "
        f"{_table_cell(item.target_date)} | {_table_cell(item.target_time)} | "
        f"{_one_line(item.priority)} | {_one_line(item.status)} | {_one_line(item.title)} | "
        f"{_table_cell(content)} | {_one_line(item.platform)} | {_one_line(item.sender_id)} |\n"
    )
    _append_text(path, row)
    return _result(root, path, "plan")


def append_health_record(vault_root: Path, item: HealthRecord) -> LifeWriteResult:
    root = _require_vault_root(vault_root)
    path = _health_path(root, item)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _write_text(path, _initial_health_content(item.date))

    row = (
        f"| {_one_line(item.date)} | {_one_line(item.time)} | {_one_line(item.metric_type)} | "
        f"{_table_cell(_format_optional_number(item.value))} | {_table_cell(item.unit)} | "
        f"{_table_cell(_format_optional_number(item.duration_minutes))} | "
        f"{_table_cell(_format_optional_number(item.distance_km))} | {_one_line(item.status)} | "
        f"{_health_note(item)} |\n"
    )
    _append_text(path, row)
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

    note = f"；{_one_line(item.note)}" if item.note else ""
    entry = (
        "\n"
        f"- {item.date} {item.time}：`{_one_line(item.title)}` 标记为 **{_one_line(item.status)}**"
        f"{note}（来源：{_one_line(item.platform)}，sender_id: {_one_line(item.sender_id)}）\n"
    )
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
        f"{item.content.strip()}\n\n"
        f"- 来源：{_one_line(item.platform)}\n"
        f"- sender_id: {_one_line(item.sender_id)}\n"
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
    filename = f"{_safe_filename(item.title)}.md"
    return _safe_life_path(root, item.life_root, item.notes_folder, item.category, filename)


def _finance_path(root: Path, item: FinanceRecord) -> Path:
    date = _parse_date(item.date)
    return _safe_life_path(
        root,
        item.life_root,
        item.finance_folder,
        f"{date.year}-{date.month:02d}.md",
    )


def _finance_status_path(root: Path, item: FinanceStatusUpdate) -> Path:
    date = _parse_date(item.date)
    return _safe_life_path(
        root,
        item.life_root,
        item.finance_folder,
        f"{date.year}-{date.month:02d}.md",
    )


def _health_path(root: Path, item: HealthRecord) -> Path:
    date = _parse_date(item.date)
    return _safe_life_path(
        root,
        item.life_root,
        item.health_folder,
        f"{date.year}-{date.month:02d}.md",
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
    return _safe_life_path(root, life_root, plan_folder, "计划清单.md")


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


def _initial_note_content(date_text: str, title: str, category: str) -> str:
    return (
        "---\n"
        "type: life-note\n"
        "status: active\n"
        f"created: {date_text}\n"
        f"updated: {date_text}\n"
        "tags: [life, note]\n"
        "---\n\n"
        f"# {title}\n\n"
        f"- 分类：{_one_line(category)}"
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
    return (
        "---\n"
        "type: life-plan\n"
        "status: active\n"
        f"created: {date_text}\n"
        f"updated: {date_text}\n"
        "tags: [life, plan]\n"
        "---\n\n"
        "# 计划清单\n\n"
        "| 创建日期 | 时间 | 层级 | 目标日期 | 目标时间 | 优先级 | 状态 | 标题 | 内容 | 来源 | sender_id |\n"
        "|---|---:|---|---|---:|---|---|---|---|---|---|\n"
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
    parts.append(f"来源：{_one_line(item.platform)}")
    if item.sender_id:
        parts.append(f"sender_id: {_one_line(item.sender_id)}")
    if item.record_uid:
        parts.append(f"record_id: {_one_line(item.record_uid)}")
    return "<br>".join(parts)


def _health_note(item: HealthRecord) -> str:
    parts = []
    if item.note:
        parts.append(_one_line(item.note))
    parts.append(f"来源：{_one_line(item.platform)}")
    if item.sender_id:
        parts.append(f"sender_id: {_one_line(item.sender_id)}")
    if item.record_uid:
        parts.append(f"record_id: {_one_line(item.record_uid)}")
    return "<br>".join(parts)


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
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = _markdown_table_cells(line)
        if len(cells) != 11 or cells[0] == "创建日期" or cells[0].startswith("---"):
            continue
        record_uid = _extract_record_uid(line)
        if not record_uid:
            continue
        records.append(
            {
                "record_uid": record_uid,
                "plan_date": cells[0],
                "plan_time": cells[1],
                "plan_scope": cells[2],
                "target_date": cells[3] or None,
                "target_time": cells[4] or None,
                "priority": cells[5] or "中",
                "status": cells[6] or "未开始",
                "title": cells[7],
                "content": _metadata_to_text(_strip_record_uid(cells[8])),
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
    text = line.strip()
    if not text.startswith("|") or not text.endswith("|"):
        return []
    return [_clean_cell(cell) for cell in text.strip("|").split("|")]


def _clean_cell(value: str) -> str:
    return str(value or "").strip().replace("｜", "|")


def _extract_record_uid(text: str) -> str:
    match = re.search(r"record_id:\s*([A-Za-z0-9_-]+)", str(text or ""))
    return match.group(1) if match else ""


def _strip_record_uid(text: str) -> str:
    return re.sub(r"(?:<br>)?\s*record_id:\s*[A-Za-z0-9_-]+", "", str(text or "")).strip()


def _metadata_to_text(text: str) -> str:
    parts = []
    for part in str(text or "").split("<br>"):
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


def _record_id_bullet(value: str | None) -> str:
    return f"- record_id: {_one_line(value)}\n" if value else ""


def _record_id_inline(value: str | None) -> str:
    return f"\n- record_id: {_one_line(value)}" if value else ""


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
