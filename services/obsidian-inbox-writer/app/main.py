from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .git_sync import git_commit_push, git_current_head, git_pull_rebase, git_revert_push, git_short_status
from .inbox import InboxMessage, append_message, inbox_write_lock
from .life import (
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


app = FastAPI(title="obsidian-inbox-writer")
DEFAULT_TIMEZONE_NAME = "Asia/Shanghai"
DEFAULT_TIMEZONE = timezone(timedelta(hours=8), DEFAULT_TIMEZONE_NAME)


class AppendRequest(BaseModel):
    platform: str = Field(default="QQ", min_length=1, max_length=40)
    sender: str = Field(default="unknown", min_length=1, max_length=120)
    sender_id: str = Field(default="unknown", min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=20000)
    raw_type: str = Field(default="text", min_length=1, max_length=40)
    received_at: str | None = None


class LifeBaseRequest(BaseModel):
    life_root: str = Field(default="生活", min_length=1, max_length=80)
    platform: str = Field(default="QQ", min_length=1, max_length=40)
    sender_id: str = Field(default="unknown", min_length=1, max_length=120)
    record_uid: str | None = Field(default=None, max_length=80)
    date: str | None = Field(default=None, max_length=20)
    time: str | None = Field(default=None, max_length=20)


class LifeDiaryRequest(LifeBaseRequest):
    diary_folder: str = Field(default="日记", min_length=1, max_length=80)
    category: str = Field(default="日记", min_length=1, max_length=80)
    mood: str | None = Field(default=None, max_length=80)
    content: str = Field(min_length=1, max_length=20000)


class LifeNoteRequest(LifeBaseRequest):
    notes_folder: str = Field(default="笔记", min_length=1, max_length=80)
    category: str = Field(default="随想笔记", min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=20000)
    original_content: str | None = Field(default=None, max_length=20000)


class LifeFinanceRequest(LifeBaseRequest):
    finance_folder: str = Field(default="财务", min_length=1, max_length=80)
    direction: str = Field(default="支出", min_length=1, max_length=40)
    amount: float = Field(gt=0)
    category: str = Field(default="其他", min_length=1, max_length=80)
    merchant: str | None = Field(default=None, max_length=160)
    wallet: str | None = Field(default=None, max_length=160)
    counterparty: str | None = Field(default=None, max_length=160)
    status: str = Field(default="已记录", min_length=1, max_length=40)
    note: str | None = Field(default=None, max_length=1000)


class LifeFinanceStatusRequest(LifeBaseRequest):
    finance_folder: str = Field(default="财务", min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    status: str = Field(min_length=1, max_length=40)
    note: str | None = Field(default=None, max_length=1000)


class LifePlanRequest(LifeBaseRequest):
    plan_folder: str = Field(default="待办", min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=20000)
    plan_scope: str = Field(default="近期", min_length=1, max_length=40)
    priority: str = Field(default="中", min_length=1, max_length=40)
    status: str = Field(default="未开始", min_length=1, max_length=40)
    target_date: str | None = Field(default=None, max_length=20)
    target_time: str | None = Field(default=None, max_length=20)


class LifeHealthRequest(LifeBaseRequest):
    health_folder: str = Field(default="健康", min_length=1, max_length=80)
    metric_type: str = Field(min_length=1, max_length=80)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    duration_minutes: float | None = None
    distance_km: float | None = None
    status: str = Field(default="已记录", min_length=1, max_length=40)
    note: str | None = Field(default=None, max_length=1000)


class LifePlanStatusRequest(LifeBaseRequest):
    plan_folder: str = Field(default="待办", min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    status: str = Field(min_length=1, max_length=40)
    note: str | None = Field(default=None, max_length=1000)


class LifeDocumentRequest(LifeBaseRequest):
    summary_folder: str = Field(default="总结", min_length=1, max_length=80)
    document_type: str = Field(default="日总结", min_length=1, max_length=80)
    title: str | None = Field(default=None, max_length=160)
    content: str = Field(min_length=1, max_length=40000)


class LifeRecoveryRequest(BaseModel):
    life_root: str = Field(default="生活", min_length=1, max_length=80)
    finance_folder: str = Field(default="财务", min_length=1, max_length=80)
    plan_folder: str = Field(default="待办", min_length=1, max_length=80)
    health_folder: str = Field(default="健康", min_length=1, max_length=80)


class RevertRequest(BaseModel):
    commit_hash: str = Field(min_length=7, max_length=80)


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "service": "obsidian-inbox-writer"}


@app.get("/git/status")
def git_status(authorization: str | None = Header(default=None)):
    auth_error = _auth_error(authorization)
    if auth_error:
        return auth_error
    vault_root = _vault_root()
    return {
        "ok": True,
        "head": git_current_head(vault_root),
        "status": git_short_status(vault_root),
        "git_sync_enabled": _env_bool("ENABLE_GIT_SYNC", default=False),
    }


@app.post("/append")
def append(payload: AppendRequest, authorization: str | None = Header(default=None)):
    token = os.environ.get("INBOX_TOKEN", "")
    if not token:
        return JSONResponse(status_code=500, content={"ok": False, "error": "missing INBOX_TOKEN"})

    if authorization != f"Bearer {token}":
        return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})

    received_at = _parse_received_at(payload.received_at)
    if received_at is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid received_at"})

    vault_root = _vault_root()
    enable_git_sync = _env_bool("ENABLE_GIT_SYNC", default=False)
    item = InboxMessage(
        platform=payload.platform,
        sender=payload.sender,
        sender_id=payload.sender_id,
        message=payload.message,
        raw_type=payload.raw_type,
        received_at=received_at,
    )

    with inbox_write_lock():
        if enable_git_sync:
            pull_result = git_pull_rebase(vault_root)
            if not pull_result.synced:
                return JSONResponse(
                    status_code=409,
                    content={
                        "ok": False,
                        "error": pull_result.warning,
                        "details": pull_result.details,
                    },
                )

        try:
            write_result = append_message(vault_root, item)
        except ValueError as exc:
            return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})

        synced = False
        warning = None
        commit_hash = None
        if enable_git_sync:
            commit_message = f"inbox: add {payload.platform} message {received_at:%Y-%m-%d %H:%M}"
            sync_result = git_commit_push(vault_root, write_result.relative_path, commit_message)
            synced = sync_result.synced
            warning = sync_result.warning
            commit_hash = sync_result.commit_hash

    response = {
        "ok": True,
        "path": write_result.relative_path,
        "category": write_result.category,
        "synced": synced,
        "commit_hash": commit_hash,
    }
    if warning:
        response["warning"] = f"written locally but {warning}"
    return response


@app.post("/life/diary")
def life_diary(payload: LifeDiaryRequest, authorization: str | None = Header(default=None)):
    life_datetime = _parse_life_datetime(payload.date, payload.time)
    if life_datetime is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid date or time"})

    date_text, time_text = life_datetime
    item = DiaryEvent(
        date=date_text,
        time=time_text,
        content=payload.content,
        category=payload.category,
        mood=payload.mood,
        platform=payload.platform,
        sender_id=payload.sender_id,
        record_uid=payload.record_uid,
        life_root=payload.life_root,
        diary_folder=payload.diary_folder,
    )
    return _write_vault_item(
        authorization=authorization,
        write_action=lambda vault_root: append_diary_event(vault_root, item),
        commit_message=f"life: add diary {date_text} {time_text}",
    )


@app.post("/life/note")
def life_note(payload: LifeNoteRequest, authorization: str | None = Header(default=None)):
    life_datetime = _parse_life_datetime(payload.date, payload.time)
    if life_datetime is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid date or time"})

    date_text, time_text = life_datetime
    item = LifeNote(
        date=date_text,
        time=time_text,
        title=payload.title,
        content=payload.content,
        category=payload.category,
        original_content=payload.original_content,
        platform=payload.platform,
        sender_id=payload.sender_id,
        record_uid=payload.record_uid,
        life_root=payload.life_root,
        notes_folder=payload.notes_folder,
    )
    return _write_vault_item(
        authorization=authorization,
        write_action=lambda vault_root: write_life_note(vault_root, item),
        commit_message=f"life: add note {date_text} {payload.title[:40]}",
    )


@app.post("/life/finance")
def life_finance(payload: LifeFinanceRequest, authorization: str | None = Header(default=None)):
    life_datetime = _parse_life_datetime(payload.date, payload.time)
    if life_datetime is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid date or time"})

    date_text, time_text = life_datetime
    item = FinanceRecord(
        date=date_text,
        time=time_text,
        amount=payload.amount,
        direction=payload.direction,
        category=payload.category,
        merchant=payload.merchant,
        wallet=payload.wallet,
        counterparty=payload.counterparty,
        status=payload.status,
        note=payload.note,
        platform=payload.platform,
        sender_id=payload.sender_id,
        record_uid=payload.record_uid,
        life_root=payload.life_root,
        finance_folder=payload.finance_folder,
    )
    return _write_vault_item(
        authorization=authorization,
        write_action=lambda vault_root: append_finance_record(vault_root, item),
        commit_message=f"life: add finance {date_text} {time_text}",
    )


@app.post("/life/finance/status")
def life_finance_status(payload: LifeFinanceStatusRequest, authorization: str | None = Header(default=None)):
    life_datetime = _parse_life_datetime(payload.date, payload.time)
    if life_datetime is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid date or time"})

    date_text, time_text = life_datetime
    item = FinanceStatusUpdate(
        date=date_text,
        time=time_text,
        title=payload.title,
        status=payload.status,
        note=payload.note,
        platform=payload.platform,
        sender_id=payload.sender_id,
        life_root=payload.life_root,
        finance_folder=payload.finance_folder,
    )
    return _write_vault_item(
        authorization=authorization,
        write_action=lambda vault_root: append_finance_status_update(vault_root, item),
        commit_message=f"life: update finance {date_text} {payload.title[:40]}",
    )


@app.post("/life/plan")
def life_plan(payload: LifePlanRequest, authorization: str | None = Header(default=None)):
    life_datetime = _parse_life_datetime(payload.date, payload.time)
    if life_datetime is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid date or time"})

    target_datetime = _parse_life_datetime(payload.target_date, payload.target_time) if payload.target_date else None
    if payload.target_date and target_datetime is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid target date or time"})

    date_text, time_text = life_datetime
    target_date_text = target_datetime[0] if target_datetime else None
    target_time_text = target_datetime[1] if payload.target_time and target_datetime else None
    item = PlanRecord(
        date=date_text,
        time=time_text,
        title=payload.title,
        content=payload.content,
        plan_scope=payload.plan_scope,
        priority=payload.priority,
        status=payload.status,
        target_date=target_date_text,
        target_time=target_time_text,
        platform=payload.platform,
        sender_id=payload.sender_id,
        record_uid=payload.record_uid,
        life_root=payload.life_root,
        plan_folder=payload.plan_folder,
    )
    return _write_vault_item(
        authorization=authorization,
        write_action=lambda vault_root: append_plan_record(vault_root, item),
        commit_message=f"life: add plan {date_text} {payload.title[:40]}",
    )


@app.post("/life/health")
def life_health(payload: LifeHealthRequest, authorization: str | None = Header(default=None)):
    life_datetime = _parse_life_datetime(payload.date, payload.time)
    if life_datetime is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid date or time"})

    date_text, time_text = life_datetime
    item = HealthRecord(
        date=date_text,
        time=time_text,
        metric_type=payload.metric_type,
        value=payload.value,
        unit=payload.unit,
        duration_minutes=payload.duration_minutes,
        distance_km=payload.distance_km,
        status=payload.status,
        note=payload.note,
        platform=payload.platform,
        sender_id=payload.sender_id,
        record_uid=payload.record_uid,
        life_root=payload.life_root,
        health_folder=payload.health_folder,
    )
    return _write_vault_item(
        authorization=authorization,
        write_action=lambda vault_root: append_health_record(vault_root, item),
        commit_message=f"life: add health {date_text} {payload.metric_type}",
    )


@app.post("/life/plan/status")
def life_plan_status(payload: LifePlanStatusRequest, authorization: str | None = Header(default=None)):
    life_datetime = _parse_life_datetime(payload.date, payload.time)
    if life_datetime is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid date or time"})

    date_text, time_text = life_datetime
    item = PlanStatusUpdate(
        date=date_text,
        time=time_text,
        title=payload.title,
        status=payload.status,
        note=payload.note,
        platform=payload.platform,
        sender_id=payload.sender_id,
        life_root=payload.life_root,
        plan_folder=payload.plan_folder,
    )
    return _write_vault_item(
        authorization=authorization,
        write_action=lambda vault_root: append_plan_status_update(vault_root, item),
        commit_message=f"life: update plan {date_text} {payload.title[:40]}",
    )


@app.post("/life/recovery-index")
def life_recovery_index(payload: LifeRecoveryRequest, authorization: str | None = Header(default=None)):
    auth_error = _auth_error(authorization)
    if auth_error:
        return auth_error
    try:
        records = collect_life_recovery_records(
            _vault_root(),
            life_root=payload.life_root,
            finance_folder=payload.finance_folder,
            plan_folder=payload.plan_folder,
            health_folder=payload.health_folder,
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    return {"ok": True, "records": records}


@app.post("/life/summary")
def life_summary(payload: LifeDocumentRequest, authorization: str | None = Header(default=None)):
    return _write_life_document(payload, authorization, document_type=payload.document_type)


@app.post("/life/briefing")
def life_briefing(payload: LifeDocumentRequest, authorization: str | None = Header(default=None)):
    return _write_life_document(payload, authorization, document_type="晨报")


@app.post("/git/revert")
def git_revert(payload: RevertRequest, authorization: str | None = Header(default=None)):
    token = os.environ.get("INBOX_TOKEN", "")
    if not token:
        return JSONResponse(status_code=500, content={"ok": False, "error": "missing INBOX_TOKEN"})

    if authorization != f"Bearer {token}":
        return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})

    if not _env_bool("ENABLE_GIT_SYNC", default=False):
        return JSONResponse(status_code=409, content={"ok": False, "error": "git sync disabled"})

    vault_root = _vault_root()
    with inbox_write_lock():
        pull_result = git_pull_rebase(vault_root)
        if not pull_result.synced:
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": pull_result.warning,
                    "details": pull_result.details,
                },
            )

        sync_result = git_revert_push(vault_root, payload.commit_hash)
        if not sync_result.synced:
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": sync_result.warning,
                    "details": sync_result.details,
                },
            )

    return {
        "ok": True,
        "synced": sync_result.synced,
        "commit_hash": sync_result.commit_hash,
    }


def _write_life_document(
    payload: LifeDocumentRequest,
    authorization: str | None,
    document_type: str,
):
    life_datetime = _parse_life_datetime(payload.date, payload.time)
    if life_datetime is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid date or time"})

    date_text, time_text = life_datetime
    item = LifeDocument(
        date=date_text,
        time=time_text,
        content=payload.content,
        title=payload.title,
        document_type=document_type,
        platform=payload.platform,
        sender_id=payload.sender_id,
        life_root=payload.life_root,
        summary_folder=payload.summary_folder,
    )
    kind = "briefing" if document_type == "晨报" else "summary"
    return _write_vault_item(
        authorization=authorization,
        write_action=lambda vault_root: write_summary_document(vault_root, item),
        commit_message=f"life: add {kind} {date_text}",
    )


def _write_vault_item(*, authorization: str | None, write_action, commit_message: str):
    auth_error = _auth_error(authorization)
    if auth_error:
        return auth_error

    vault_root = _vault_root()
    enable_git_sync = _env_bool("ENABLE_GIT_SYNC", default=False)

    with inbox_write_lock():
        if enable_git_sync:
            pull_result = git_pull_rebase(vault_root)
            if not pull_result.synced:
                return JSONResponse(
                    status_code=409,
                    content={
                        "ok": False,
                        "error": pull_result.warning,
                        "details": pull_result.details,
                    },
                )

        try:
            write_result = write_action(vault_root)
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})

        synced = False
        warning = None
        commit_hash = None
        if enable_git_sync:
            sync_result = git_commit_push(vault_root, write_result.relative_path, commit_message)
            synced = sync_result.synced
            warning = sync_result.warning
            commit_hash = sync_result.commit_hash

    response = {
        "ok": True,
        "path": write_result.relative_path,
        "kind": write_result.kind,
        "synced": synced,
        "commit_hash": commit_hash,
    }
    if warning:
        response["warning"] = f"written locally but {warning}"
    return response


def _auth_error(authorization: str | None):
    token = os.environ.get("INBOX_TOKEN", "")
    if not token:
        return JSONResponse(status_code=500, content={"ok": False, "error": "missing INBOX_TOKEN"})
    if authorization != f"Bearer {token}":
        return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})
    return None


def _parse_received_at(value: str | None) -> datetime | None:
    app_timezone = _app_timezone()
    if not value:
        return datetime.now(app_timezone)
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(app_timezone)


def _parse_life_datetime(date_value: str | None, time_value: str | None) -> tuple[str, str] | None:
    now = datetime.now(_app_timezone())
    if date_value:
        date_text = date_value.strip()
        try:
            datetime.strptime(date_text, "%Y-%m-%d")
        except ValueError:
            return None
    else:
        date_text = now.strftime("%Y-%m-%d")

    if time_value:
        time_text = time_value.strip()
        for time_format in ("%H:%M", "%H:%M:%S"):
            try:
                parsed_time = datetime.strptime(time_text, time_format)
                return date_text, parsed_time.strftime("%H:%M")
            except ValueError:
                continue
        return None

    return date_text, now.strftime("%H:%M")


def _app_timezone():
    timezone_name = os.environ.get("INBOX_TIMEZONE", DEFAULT_TIMEZONE_NAME).strip() or DEFAULT_TIMEZONE_NAME
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name != DEFAULT_TIMEZONE_NAME:
            try:
                return ZoneInfo(DEFAULT_TIMEZONE_NAME)
            except ZoneInfoNotFoundError:
                pass
        return DEFAULT_TIMEZONE


def _vault_root() -> Path:
    configured = os.environ.get("VAULT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
