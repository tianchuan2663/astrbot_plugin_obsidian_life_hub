from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import sqlite3
from typing import Any


class LifeDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS life_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_uid TEXT,
                session_id TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_time TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                mood TEXT,
                markdown_path TEXT,
                sync_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_life_events_session_date
                ON life_events(session_id, event_date);

            CREATE TABLE IF NOT EXISTS life_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_uid TEXT,
                session_id TEXT NOT NULL,
                note_date TEXT NOT NULL,
                note_time TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                polished_content TEXT,
                markdown_path TEXT,
                sync_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_life_notes_session_date
                ON life_notes(session_id, note_date);

            CREATE TABLE IF NOT EXISTS finance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_uid TEXT,
                session_id TEXT NOT NULL,
                record_date TEXT NOT NULL,
                record_time TEXT NOT NULL,
                amount REAL NOT NULL,
                direction TEXT NOT NULL,
                category TEXT NOT NULL,
                merchant TEXT,
                note TEXT,
                wallet TEXT,
                counterparty TEXT,
                status TEXT NOT NULL DEFAULT '已记录',
                markdown_path TEXT,
                sync_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_finance_records_session_date
                ON finance_records(session_id, record_date);

            CREATE TABLE IF NOT EXISTS health_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_uid TEXT,
                session_id TEXT NOT NULL,
                record_date TEXT NOT NULL,
                record_time TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL,
                unit TEXT,
                duration_minutes REAL,
                distance_km REAL,
                note TEXT,
                status TEXT NOT NULL DEFAULT '已记录',
                markdown_path TEXT,
                sync_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_health_records_session_date
                ON health_records(session_id, record_date);

            CREATE TABLE IF NOT EXISTS life_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_uid TEXT,
                session_id TEXT NOT NULL,
                plan_date TEXT NOT NULL,
                plan_time TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                plan_scope TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT '未开始',
                target_date TEXT,
                target_time TEXT,
                markdown_path TEXT,
                sync_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_life_plans_session_status
                ON life_plans(session_id, status, plan_scope, target_date);

            CREATE TABLE IF NOT EXISTS life_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_uid TEXT,
                session_id TEXT NOT NULL,
                reminder_date TEXT NOT NULL,
                reminder_time TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                due_date TEXT,
                due_time TEXT,
                status TEXT NOT NULL DEFAULT '未完成',
                markdown_path TEXT,
                sync_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_life_reminders_session_due
                ON life_reminders(session_id, status, due_date, due_time);

            CREATE TABLE IF NOT EXISTS conversation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_conversation_logs_session_created
                ON conversation_logs(session_id, created_at);

            CREATE TABLE IF NOT EXISTS summary_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                summary_date TEXT NOT NULL,
                summary_type TEXT NOT NULL,
                status TEXT NOT NULL,
                markdown_path TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS write_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                trigger TEXT,
                commit_hash TEXT,
                markdown_path TEXT,
                original_text TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_write_history_session_status
                ON write_history(session_id, status, id);

            CREATE TABLE IF NOT EXISTS pending_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pending_actions_session_status
                ON pending_actions(session_id, status, id);

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            """
        )
        self._ensure_columns(
            "life_events",
            {
                "record_uid": "TEXT",
            },
        )
        self._ensure_columns(
            "life_notes",
            {
                "record_uid": "TEXT",
            },
        )
        self._ensure_columns(
            "finance_records",
            {
                "record_uid": "TEXT",
                "wallet": "TEXT",
                "counterparty": "TEXT",
                "status": "TEXT NOT NULL DEFAULT '已记录'",
            },
        )
        self._ensure_columns(
            "health_records",
            {
                "record_uid": "TEXT",
            },
        )
        self._ensure_columns(
            "life_plans",
            {
                "record_uid": "TEXT",
            },
        )
        self.conn.commit()

    def _ensure_columns(self, table: str, columns: dict[str, str]) -> None:
        existing = {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}
        for column, declaration in columns.items():
            if column not in existing:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    async def add_life_event(
        self,
        session_id: str,
        event_date: str,
        event_time: str,
        category: str,
        content: str,
        record_uid: str | None = None,
        mood: str | None = None,
        markdown_path: str | None = None,
        sync_status: str = "synced",
    ) -> int:
        async with self._lock:
            cursor = self.conn.execute(
                "INSERT INTO life_events "
                "(record_uid, session_id, event_date, event_time, category, content, mood, markdown_path, sync_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (record_uid, session_id, event_date, event_time, category, content, mood, markdown_path, sync_status),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    async def add_life_note(
        self,
        session_id: str,
        note_date: str,
        note_time: str,
        category: str,
        title: str,
        content: str,
        record_uid: str | None = None,
        polished_content: str | None = None,
        markdown_path: str | None = None,
        sync_status: str = "synced",
    ) -> int:
        async with self._lock:
            cursor = self.conn.execute(
                "INSERT INTO life_notes "
                "(record_uid, session_id, note_date, note_time, category, title, content, polished_content, markdown_path, sync_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_uid,
                    session_id,
                    note_date,
                    note_time,
                    category,
                    title,
                    content,
                    polished_content,
                    markdown_path,
                    sync_status,
                ),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    async def add_finance_record(
        self,
        session_id: str,
        record_date: str,
        record_time: str,
        amount: float,
        direction: str,
        category: str,
        merchant: str | None = None,
        note: str | None = None,
        wallet: str | None = None,
        counterparty: str | None = None,
        status: str = "已记录",
        record_uid: str | None = None,
        markdown_path: str | None = None,
        sync_status: str = "synced",
    ) -> int:
        async with self._lock:
            cursor = self.conn.execute(
                "INSERT INTO finance_records "
                "(record_uid, session_id, record_date, record_time, amount, direction, category, merchant, note, "
                "wallet, counterparty, status, markdown_path, sync_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_uid,
                    session_id,
                    record_date,
                    record_time,
                    amount,
                    direction,
                    category,
                    merchant,
                    note,
                    wallet,
                    counterparty,
                    status,
                    markdown_path,
                    sync_status,
                ),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    async def add_health_record(
        self,
        session_id: str,
        record_date: str,
        record_time: str,
        metric_type: str,
        value: float | None = None,
        unit: str | None = None,
        duration_minutes: float | None = None,
        distance_km: float | None = None,
        note: str | None = None,
        status: str = "已记录",
        record_uid: str | None = None,
        markdown_path: str | None = None,
        sync_status: str = "synced",
    ) -> int:
        async with self._lock:
            cursor = self.conn.execute(
                "INSERT INTO health_records "
                "(record_uid, session_id, record_date, record_time, metric_type, value, unit, duration_minutes, "
                "distance_km, note, status, markdown_path, sync_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_uid,
                    session_id,
                    record_date,
                    record_time,
                    metric_type,
                    value,
                    unit,
                    duration_minutes,
                    distance_km,
                    note,
                    status,
                    markdown_path,
                    sync_status,
                ),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    async def add_plan(
        self,
        session_id: str,
        plan_date: str,
        plan_time: str,
        title: str,
        content: str,
        plan_scope: str,
        priority: str,
        status: str = "未开始",
        target_date: str | None = None,
        target_time: str | None = None,
        record_uid: str | None = None,
        markdown_path: str | None = None,
        sync_status: str = "synced",
    ) -> int:
        async with self._lock:
            cursor = self.conn.execute(
                "INSERT INTO life_plans "
                "(record_uid, session_id, plan_date, plan_time, title, content, plan_scope, priority, status, "
                "target_date, target_time, markdown_path, sync_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_uid,
                    session_id,
                    plan_date,
                    plan_time,
                    title,
                    content,
                    plan_scope,
                    priority,
                    status,
                    target_date,
                    target_time,
                    markdown_path,
                    sync_status,
                ),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    async def add_reminder(
        self,
        session_id: str,
        reminder_date: str,
        reminder_time: str,
        title: str,
        content: str,
        due_date: str | None = None,
        due_time: str | None = None,
        status: str = "未完成",
        record_uid: str | None = None,
        markdown_path: str | None = None,
        sync_status: str = "synced",
    ) -> int:
        async with self._lock:
            cursor = self.conn.execute(
                "INSERT INTO life_reminders "
                "(record_uid, session_id, reminder_date, reminder_time, title, content, due_date, due_time, "
                "status, markdown_path, sync_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_uid,
                    session_id,
                    reminder_date,
                    reminder_time,
                    title,
                    content,
                    due_date,
                    due_time,
                    status,
                    markdown_path,
                    sync_status,
                ),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    async def complete_plan_by_keyword(self, session_id: str, keyword: str) -> dict[str, Any] | None:
        text = f"%{keyword.strip()}%"
        if text == "%%":
            return None
        async with self._lock:
            rows = self._fetch_dicts(
                "SELECT * FROM life_plans "
                "WHERE session_id = ? AND status NOT IN ('已完成', '取消', '已取消') "
                "AND (title LIKE ? OR content LIKE ?) "
                "ORDER BY COALESCE(target_date, '9999-12-31'), id DESC LIMIT 1",
                (session_id, text, text),
            )
            if not rows:
                return None
            plan = rows[0]
            previous_status = str(plan.get("status") or "未开始")
            self.conn.execute(
                "UPDATE life_plans SET status = '已完成', updated_at = datetime('now', 'localtime') WHERE id = ?",
                (plan["id"],),
            )
            self.conn.commit()
            plan["previous_status"] = previous_status
            plan["status"] = "已完成"
            return plan

    async def cancel_plan_by_keyword(self, session_id: str, keyword: str) -> dict[str, Any] | None:
        text = f"%{keyword.strip()}%"
        if text == "%%":
            return None
        async with self._lock:
            rows = self._fetch_dicts(
                "SELECT * FROM life_plans "
                "WHERE session_id = ? AND status NOT IN ('已完成', '取消', '已取消') "
                "AND (title LIKE ? OR content LIKE ?) "
                "ORDER BY COALESCE(target_date, '9999-12-31'), id DESC LIMIT 1",
                (session_id, text, text),
            )
            if not rows:
                return None
            plan = rows[0]
            previous_status = str(plan.get("status") or "未开始")
            self.conn.execute(
                "UPDATE life_plans SET status = '已取消', updated_at = datetime('now', 'localtime') WHERE id = ?",
                (plan["id"],),
            )
            self.conn.commit()
            plan["previous_status"] = previous_status
            plan["status"] = "已取消"
            return plan

    async def start_plan_by_keyword(self, session_id: str, keyword: str) -> dict[str, Any] | None:
        return await self._update_plan_status_by_keyword(session_id, keyword, "进行中")

    async def postpone_plan_by_keyword(
        self,
        session_id: str,
        keyword: str,
        *,
        target_date: str | None = None,
        target_time: str | None = None,
        note: str = "",
    ) -> dict[str, Any] | None:
        text = f"%{keyword.strip()}%"
        if text == "%%":
            return None
        async with self._lock:
            rows = self._fetch_dicts(
                "SELECT * FROM life_plans "
                "WHERE session_id = ? AND status NOT IN ('已完成', '取消', '已取消') "
                "AND (title LIKE ? OR content LIKE ?) "
                "ORDER BY COALESCE(target_date, '9999-12-31'), id DESC LIMIT 1",
                (session_id, text, text),
            )
            if not rows:
                return None
            plan = rows[0]
            previous_status = str(plan.get("status") or "未开始")
            self.conn.execute(
                "UPDATE life_plans SET status = '已推迟', target_date = ?, target_time = ?, "
                "updated_at = datetime('now', 'localtime') WHERE id = ?",
                (target_date, target_time, plan["id"]),
            )
            self.conn.commit()
            plan["previous_status"] = previous_status
            plan["status"] = "已推迟"
            plan["new_target_date"] = target_date
            plan["new_target_time"] = target_time
            plan["postpone_note"] = note
            return plan

    async def _update_plan_status_by_keyword(self, session_id: str, keyword: str, status: str) -> dict[str, Any] | None:
        text = f"%{keyword.strip()}%"
        if text == "%%":
            return None
        async with self._lock:
            rows = self._fetch_dicts(
                "SELECT * FROM life_plans "
                "WHERE session_id = ? AND status NOT IN ('已完成', '取消', '已取消') "
                "AND (title LIKE ? OR content LIKE ?) "
                "ORDER BY COALESCE(target_date, '9999-12-31'), id DESC LIMIT 1",
                (session_id, text, text),
            )
            if not rows:
                return None
            plan = rows[0]
            previous_status = str(plan.get("status") or "未开始")
            self.conn.execute(
                "UPDATE life_plans SET status = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                (status, plan["id"]),
            )
            self.conn.commit()
            plan["previous_status"] = previous_status
            plan["status"] = status
            return plan

    async def update_plan_by_keyword(
        self,
        session_id: str,
        keyword: str,
        *,
        title: str,
        content: str,
        plan_scope: str,
        priority: str,
        target_date: str | None = None,
        target_time: str | None = None,
    ) -> dict[str, Any] | None:
        text = f"%{keyword.strip()}%"
        if text == "%%":
            return None
        async with self._lock:
            rows = self._fetch_dicts(
                "SELECT * FROM life_plans "
                "WHERE session_id = ? AND status NOT IN ('已完成', '取消', '已取消') "
                "AND (title LIKE ? OR content LIKE ?) "
                "ORDER BY COALESCE(target_date, '9999-12-31'), id DESC LIMIT 1",
                (session_id, text, text),
            )
            if not rows:
                return None
            plan = rows[0]
            self.conn.execute(
                "UPDATE life_plans SET title = ?, content = ?, plan_scope = ?, priority = ?, "
                "target_date = ?, target_time = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                (title, content, plan_scope, priority, target_date, target_time, plan["id"]),
            )
            self.conn.commit()
            plan["new_title"] = title
            plan["new_content"] = content
            plan["new_plan_scope"] = plan_scope
            plan["new_priority"] = priority
            plan["new_target_date"] = target_date
            plan["new_target_time"] = target_time
            return plan

    async def set_plan_status(self, plan_id: int, status: str) -> None:
        async with self._lock:
            self.conn.execute(
                "UPDATE life_plans SET status = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                (status, plan_id),
            )
            self.conn.commit()

    async def add_conversation_log(self, session_id: str, role: str, content: str) -> int:
        async with self._lock:
            cursor = self.conn.execute(
                "INSERT INTO conversation_logs (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    async def add_summary_job(
        self,
        session_id: str,
        summary_date: str,
        summary_type: str,
        status: str,
        markdown_path: str | None = None,
    ) -> int:
        async with self._lock:
            cursor = self.conn.execute(
                "INSERT INTO summary_jobs (session_id, summary_date, summary_type, status, markdown_path) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, summary_date, summary_type, status, markdown_path),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    async def add_write_history(
        self,
        session_id: str,
        action_type: str,
        trigger: str,
        commit_hash: str | None,
        markdown_path: str | None,
        original_text: str = "",
        status: str = "active",
    ) -> int:
        async with self._lock:
            cursor = self.conn.execute(
                "INSERT INTO write_history "
                "(session_id, action_type, trigger, commit_hash, markdown_path, original_text, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, action_type, trigger, commit_hash, markdown_path, original_text, status),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    async def get_last_active_write(self, session_id: str) -> dict[str, Any] | None:
        async with self._lock:
            rows = self._fetch_dicts(
                "SELECT * FROM write_history "
                "WHERE session_id = ? AND status = 'active' AND commit_hash IS NOT NULL "
                "ORDER BY id DESC LIMIT 1",
                (session_id,),
            )
        return rows[0] if rows else None

    async def mark_write_undone(self, history_id: int) -> None:
        async with self._lock:
            self.conn.execute(
                "UPDATE write_history SET status = 'undone' WHERE id = ?",
                (history_id,),
            )
            self.conn.commit()

    async def cancel_finance_by_keyword(self, session_id: str, keyword: str) -> dict[str, Any] | None:
        text = f"%{keyword.strip()}%"
        if text == "%%":
            return None
        async with self._lock:
            rows = self._fetch_dicts(
                "SELECT * FROM finance_records "
                "WHERE session_id = ? AND status != '作废' "
                "AND (note LIKE ? OR category LIKE ? OR direction LIKE ? OR wallet LIKE ? OR counterparty LIKE ?) "
                "ORDER BY record_date DESC, record_time DESC, id DESC LIMIT 1",
                (session_id, text, text, text, text, text),
            )
            if not rows:
                return None
            record = rows[0]
            previous_status = str(record.get("status") or "已记录")
            self.conn.execute(
                "UPDATE finance_records SET status = '作废' WHERE id = ?",
                (record["id"],),
            )
            self.conn.commit()
            record["previous_status"] = previous_status
            record["status"] = "作废"
            return record

    async def add_pending_action(
        self,
        session_id: str,
        action_type: str,
        summary: str,
        payload_json: str,
        *,
        ttl_minutes: int = 10,
    ) -> int:
        expires_at = (datetime.now() + timedelta(minutes=ttl_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        async with self._lock:
            self.conn.execute(
                "UPDATE pending_actions SET status = 'expired' "
                "WHERE session_id = ? AND status = 'pending'",
                (session_id,),
            )
            cursor = self.conn.execute(
                "INSERT INTO pending_actions (session_id, action_type, summary, payload_json, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, action_type, summary, payload_json, expires_at),
            )
            self.conn.commit()
            return int(cursor.lastrowid)

    async def get_pending_action(self, session_id: str) -> dict[str, Any] | None:
        async with self._lock:
            rows = self._fetch_dicts(
                "SELECT * FROM pending_actions "
                "WHERE session_id = ? AND status = 'pending' AND expires_at >= datetime('now', 'localtime') "
                "ORDER BY id DESC LIMIT 1",
                (session_id,),
            )
        return rows[0] if rows else None

    async def resolve_pending_action(self, pending_id: int, status: str) -> None:
        async with self._lock:
            self.conn.execute(
                "UPDATE pending_actions SET status = ? WHERE id = ?",
                (status, pending_id),
            )
            self.conn.commit()

    async def set_setting(self, key: str, value: str) -> None:
        async with self._lock:
            self.conn.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now', 'localtime')) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value),
            )
            self.conn.commit()

    async def get_setting(self, key: str, default: str = "") -> str:
        async with self._lock:
            rows = self._fetch_dicts("SELECT value FROM settings WHERE key = ?", (key,))
        if not rows:
            return default
        return str(rows[0].get("value") or default)

    async def query_day(self, session_id: str, date_text: str) -> dict[str, list[dict[str, Any]]]:
        async with self._lock:
            events = self._fetch_dicts(
                "SELECT * FROM life_events WHERE session_id = ? AND event_date = ? ORDER BY event_time, id",
                (session_id, date_text),
            )
            notes = self._fetch_dicts(
                "SELECT * FROM life_notes WHERE session_id = ? AND note_date = ? ORDER BY note_time, id",
                (session_id, date_text),
            )
            finance = self._fetch_dicts(
                "SELECT * FROM finance_records WHERE session_id = ? AND record_date = ? "
                "AND status != '作废' ORDER BY record_time, id",
                (session_id, date_text),
            )
            health = self._fetch_dicts(
                "SELECT * FROM health_records WHERE session_id = ? AND record_date = ? "
                "AND status != '作废' ORDER BY record_time, id",
                (session_id, date_text),
            )
            plans = self._fetch_dicts(
                "SELECT * FROM life_plans WHERE session_id = ? "
                "AND status NOT IN ('取消', '已取消') "
                "AND (target_date = ? OR DATE(updated_at) = ? OR (target_date IS NULL AND plan_scope = '近期')) "
                "ORDER BY COALESCE(target_date, '9999-12-31'), priority, id",
                (session_id, date_text, date_text),
            )
            reminders = self._fetch_dicts(
                "SELECT * FROM life_reminders WHERE session_id = ? "
                "AND status NOT IN ('已完成', '取消', '已取消') "
                "AND (due_date = ? OR reminder_date = ?) "
                "ORDER BY COALESCE(due_date, '9999-12-31'), COALESCE(due_time, '23:59'), id",
                (session_id, date_text, date_text),
            )
            conversations = self._fetch_dicts(
                "SELECT * FROM conversation_logs WHERE session_id = ? AND DATE(created_at) = ? ORDER BY id",
                (session_id, date_text),
            )
        return {
            "events": events,
            "notes": notes,
            "finance": finance,
            "health": health,
            "plans": plans,
            "reminders": reminders,
            "conversations": conversations,
        }

    async def query_range(self, session_id: str, start_date: str, end_date: str) -> dict[str, list[dict[str, Any]]]:
        async with self._lock:
            events = self._fetch_dicts(
                "SELECT * FROM life_events WHERE session_id = ? AND event_date BETWEEN ? AND ? "
                "ORDER BY event_date, event_time, id",
                (session_id, start_date, end_date),
            )
            notes = self._fetch_dicts(
                "SELECT * FROM life_notes WHERE session_id = ? AND note_date BETWEEN ? AND ? "
                "ORDER BY note_date, note_time, id",
                (session_id, start_date, end_date),
            )
            finance = self._fetch_dicts(
                "SELECT * FROM finance_records WHERE session_id = ? AND record_date BETWEEN ? AND ? "
                "AND status != '作废' ORDER BY record_date, record_time, id",
                (session_id, start_date, end_date),
            )
            health = self._fetch_dicts(
                "SELECT * FROM health_records WHERE session_id = ? AND record_date BETWEEN ? AND ? "
                "AND status != '作废' ORDER BY record_date, record_time, id",
                (session_id, start_date, end_date),
            )
            plans = self._fetch_dicts(
                "SELECT * FROM life_plans WHERE session_id = ? "
                "AND status NOT IN ('取消', '已取消') AND (target_date BETWEEN ? AND ? OR target_date IS NULL) "
                "ORDER BY COALESCE(target_date, '9999-12-31'), id",
                (session_id, start_date, end_date),
            )
            reminders = self._fetch_dicts(
                "SELECT * FROM life_reminders WHERE session_id = ? "
                "AND status NOT IN ('已完成', '取消', '已取消') "
                "AND (due_date BETWEEN ? AND ? OR due_date IS NULL) "
                "ORDER BY COALESCE(due_date, '9999-12-31'), COALESCE(due_time, '23:59'), id",
                (session_id, start_date, end_date),
            )
        return {
            "events": events,
            "notes": notes,
            "finance": finance,
            "health": health,
            "plans": plans,
            "reminders": reminders,
            "conversations": [],
        }

    async def query_plans(
        self,
        session_id: str,
        *,
        scopes: tuple[str, ...] = (),
        target_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_completed: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM life_plans WHERE session_id = ?"
        params: list[Any] = [session_id]
        if not include_completed:
            sql += " AND status NOT IN ('已完成', '取消', '已取消')"
        if scopes:
            placeholders = ", ".join("?" for _ in scopes)
            sql += f" AND plan_scope IN ({placeholders})"
            params.extend(scopes)
        if target_date:
            sql += " AND target_date = ?"
            params.append(target_date)
        if start_date:
            sql += " AND (target_date IS NULL OR target_date >= ?)"
            params.append(start_date)
        if end_date:
            sql += " AND (target_date IS NULL OR target_date <= ?)"
            params.append(end_date)
        sql += " ORDER BY COALESCE(target_date, '9999-12-31'), CASE priority WHEN '高' THEN 0 WHEN '中' THEN 1 ELSE 2 END, id DESC LIMIT ?"
        params.append(limit)
        async with self._lock:
            return self._fetch_dicts(sql, tuple(params))

    async def query_reminders(
        self,
        session_id: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        include_completed: bool = False,
        include_undated: bool = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM life_reminders WHERE session_id = ?"
        params: list[Any] = [session_id]
        if not include_completed:
            sql += " AND status NOT IN ('已完成', '取消', '已取消')"
        if not include_undated:
            sql += " AND due_date IS NOT NULL"
        if start_date:
            sql += " AND due_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND due_date <= ?"
            params.append(end_date)
        sql += " ORDER BY COALESCE(due_date, '9999-12-31'), COALESCE(due_time, '23:59'), id DESC LIMIT ?"
        params.append(limit)
        async with self._lock:
            return self._fetch_dicts(sql, tuple(params))

    async def query_finance_records(
        self,
        session_id: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        directions: tuple[str, ...] = (),
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM finance_records WHERE session_id = ? AND status != '作废'"
        params: list[Any] = [session_id]
        if start_date:
            sql += " AND record_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND record_date <= ?"
            params.append(end_date)
        if directions:
            placeholders = ", ".join("?" for _ in directions)
            sql += f" AND direction IN ({placeholders})"
            params.extend(directions)
        sql += " ORDER BY record_date DESC, record_time DESC, id DESC LIMIT ?"
        params.append(limit)
        async with self._lock:
            return self._fetch_dicts(sql, tuple(params))

    async def query_health_records(
        self,
        session_id: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        metric_types: tuple[str, ...] = (),
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM health_records WHERE session_id = ? AND status != '作废'"
        params: list[Any] = [session_id]
        if start_date:
            sql += " AND record_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND record_date <= ?"
            params.append(end_date)
        if metric_types:
            placeholders = ", ".join("?" for _ in metric_types)
            sql += f" AND metric_type IN ({placeholders})"
            params.extend(metric_types)
        sql += " ORDER BY record_date DESC, record_time DESC, id DESC LIMIT ?"
        params.append(limit)
        async with self._lock:
            return self._fetch_dicts(sql, tuple(params))

    async def get_notes_by_category(
        self,
        session_id: str,
        category: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM life_notes WHERE session_id = ? AND category = ?"
        params: list[Any] = [session_id, category]
        if start_date:
            sql += " AND note_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND note_date <= ?"
            params.append(end_date)
        sql += " ORDER BY note_date DESC, note_time DESC, id DESC LIMIT ?"
        params.append(limit)
        async with self._lock:
            return self._fetch_dicts(sql, tuple(params))

    async def get_recent_notes(self, session_id: str, days: int = 90, limit: int = 20) -> list[dict[str, Any]]:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        async with self._lock:
            return self._fetch_dicts(
                "SELECT * FROM life_notes WHERE session_id = ? AND note_date >= ? ORDER BY id DESC LIMIT ?",
                (session_id, since, limit),
            )

    async def count_pending_actions(self, session_id: str) -> int:
        async with self._lock:
            rows = self._fetch_dicts(
                "SELECT COUNT(*) AS count FROM pending_actions "
                "WHERE session_id = ? AND status = 'pending' AND expires_at >= datetime('now', 'localtime')",
                (session_id,),
            )
        return int(rows[0]["count"] if rows else 0)

    async def record_counts(self, session_id: str) -> dict[str, int]:
        tables = {
            "日记": "life_events",
            "笔记": "life_notes",
            "财务": "finance_records",
            "计划": "life_plans",
            "备忘": "life_reminders",
            "健康": "health_records",
            "写入历史": "write_history",
        }
        counts: dict[str, int] = {}
        async with self._lock:
            for label, table in tables.items():
                rows = self._fetch_dicts(f"SELECT COUNT(*) AS count FROM {table} WHERE session_id = ?", (session_id,))
                counts[label] = int(rows[0]["count"] if rows else 0)
        return counts

    async def import_recovery_records(self, session_id: str, records: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, int]]:
        stats = {
            "finance": {"imported": 0, "skipped": 0},
            "plans": {"imported": 0, "skipped": 0},
            "health": {"imported": 0, "skipped": 0},
        }
        async with self._lock:
            for item in records.get("finance", []):
                record_uid = str(item.get("record_uid") or "").strip()
                if not record_uid or self._record_uid_exists("finance_records", record_uid):
                    stats["finance"]["skipped"] += 1
                    continue
                self.conn.execute(
                    "INSERT INTO finance_records "
                    "(record_uid, session_id, record_date, record_time, amount, direction, category, merchant, note, "
                    "wallet, counterparty, status, markdown_path, sync_status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record_uid,
                        session_id,
                        item.get("record_date") or "",
                        item.get("record_time") or "",
                        float(item.get("amount") or 0),
                        item.get("direction") or "支出",
                        item.get("category") or "其他",
                        None,
                        item.get("note") or "",
                        item.get("wallet") or "",
                        item.get("counterparty") or "",
                        item.get("status") or "已记录",
                        item.get("markdown_path") or "",
                        "recovered",
                    ),
                )
                stats["finance"]["imported"] += 1

            for item in records.get("plans", []):
                record_uid = str(item.get("record_uid") or "").strip()
                if not record_uid or self._record_uid_exists("life_plans", record_uid):
                    stats["plans"]["skipped"] += 1
                    continue
                self.conn.execute(
                    "INSERT INTO life_plans "
                    "(record_uid, session_id, plan_date, plan_time, title, content, plan_scope, priority, status, "
                    "target_date, target_time, markdown_path, sync_status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record_uid,
                        session_id,
                        item.get("plan_date") or "",
                        item.get("plan_time") or "",
                        item.get("title") or "未命名计划",
                        item.get("content") or item.get("title") or "",
                        item.get("plan_scope") or "近期",
                        item.get("priority") or "中",
                        item.get("status") or "未开始",
                        item.get("target_date") or None,
                        item.get("target_time") or None,
                        item.get("markdown_path") or "",
                        "recovered",
                    ),
                )
                stats["plans"]["imported"] += 1

            for item in records.get("health", []):
                record_uid = str(item.get("record_uid") or "").strip()
                if not record_uid or self._record_uid_exists("health_records", record_uid):
                    stats["health"]["skipped"] += 1
                    continue
                self.conn.execute(
                    "INSERT INTO health_records "
                    "(record_uid, session_id, record_date, record_time, metric_type, value, unit, duration_minutes, "
                    "distance_km, note, status, markdown_path, sync_status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record_uid,
                        session_id,
                        item.get("record_date") or "",
                        item.get("record_time") or "",
                        item.get("metric_type") or "健康",
                        item.get("value"),
                        item.get("unit") or "",
                        item.get("duration_minutes"),
                        item.get("distance_km"),
                        item.get("note") or "",
                        item.get("status") or "已记录",
                        item.get("markdown_path") or "",
                        "recovered",
                    ),
                )
                stats["health"]["imported"] += 1

            self.conn.commit()
        return stats

    def _record_uid_exists(self, table: str, record_uid: str) -> bool:
        rows = self._fetch_dicts(f"SELECT id FROM {table} WHERE record_uid = ? LIMIT 1", (record_uid,))
        return bool(rows)

    def _fetch_dicts(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        cursor = self.conn.execute(sql, params)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self) -> None:
        self.conn.close()
