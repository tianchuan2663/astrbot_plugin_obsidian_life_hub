from __future__ import annotations

from typing import Any
import json

import aiohttp

from .config import LifePluginConfig
from .utils import safe_error_text


class WriterClient:
    def __init__(self, config: LifePluginConfig):
        self.config = config

    async def append_inbox(
        self,
        *,
        platform: str,
        sender: str,
        sender_id: str,
        message: str,
        raw_type: str = "text",
    ) -> dict[str, Any]:
        return await self._post(
            "/append",
            {
                "platform": platform,
                "sender": sender,
                "sender_id": sender_id,
                "message": message,
                "raw_type": raw_type,
            },
        )

    async def write_diary(
        self,
        *,
        date: str,
        time: str,
        content: str,
        category: str = "日记",
        mood: str | None = None,
        record_uid: str | None = None,
        platform: str = "QQ",
        sender_id: str = "unknown",
    ) -> dict[str, Any]:
        return await self._post(
            "/life/diary",
            {
                "life_root": self.config.life_root_folder,
                "diary_folder": self.config.diary_folder,
                "date": date,
                "time": time,
                "content": content,
                "category": category,
                "mood": mood,
                "record_uid": record_uid,
                "platform": platform,
                "sender_id": sender_id,
            },
        )

    async def write_note(
        self,
        *,
        date: str,
        time: str,
        title: str,
        content: str,
        category: str,
        original_content: str | None = None,
        record_uid: str | None = None,
        platform: str = "QQ",
        sender_id: str = "unknown",
    ) -> dict[str, Any]:
        return await self._post(
            "/life/note",
            {
                "life_root": self.config.life_root_folder,
                "notes_folder": self.config.notes_folder,
                "date": date,
                "time": time,
                "title": title,
                "content": content,
                "category": category,
                "original_content": original_content,
                "record_uid": record_uid,
                "platform": platform,
                "sender_id": sender_id,
            },
        )

    async def write_finance(
        self,
        *,
        date: str,
        time: str,
        amount: float,
        direction: str,
        category: str,
        note: str,
        merchant: str | None = None,
        wallet: str | None = None,
        counterparty: str | None = None,
        status: str = "已记录",
        record_uid: str | None = None,
        platform: str = "QQ",
        sender_id: str = "unknown",
    ) -> dict[str, Any]:
        return await self._post(
            "/life/finance",
            {
                "life_root": self.config.life_root_folder,
                "finance_folder": self.config.finance_folder,
                "date": date,
                "time": time,
                "amount": amount,
                "direction": direction,
                "category": category,
                "merchant": merchant,
                "wallet": wallet,
                "counterparty": counterparty,
                "status": status,
                "record_uid": record_uid,
                "note": note,
                "platform": platform,
                "sender_id": sender_id,
            },
        )

    async def write_finance_status(
        self,
        *,
        date: str,
        time: str,
        title: str,
        status: str,
        note: str | None = None,
        platform: str = "QQ",
        sender_id: str = "unknown",
    ) -> dict[str, Any]:
        return await self._post(
            "/life/finance/status",
            {
                "life_root": self.config.life_root_folder,
                "finance_folder": self.config.finance_folder,
                "date": date,
                "time": time,
                "title": title,
                "status": status,
                "note": note,
                "platform": platform,
                "sender_id": sender_id,
            },
        )

    async def write_plan(
        self,
        *,
        date: str,
        time: str,
        title: str,
        content: str,
        plan_scope: str,
        priority: str,
        status: str = "未开始",
        target_date: str | None = None,
        target_time: str | None = None,
        record_uid: str | None = None,
        platform: str = "QQ",
        sender_id: str = "unknown",
    ) -> dict[str, Any]:
        return await self._post(
            "/life/plan",
            {
                "life_root": self.config.life_root_folder,
                "plan_folder": self.config.plan_folder,
                "date": date,
                "time": time,
                "title": title,
                "content": content,
                "plan_scope": plan_scope,
                "priority": priority,
                "status": status,
                "target_date": target_date,
                "target_time": target_time,
                "record_uid": record_uid,
                "platform": platform,
                "sender_id": sender_id,
            },
        )

    async def write_health(
        self,
        *,
        date: str,
        time: str,
        metric_type: str,
        note: str,
        value: float | None = None,
        unit: str | None = None,
        duration_minutes: float | None = None,
        distance_km: float | None = None,
        status: str = "已记录",
        record_uid: str | None = None,
        platform: str = "QQ",
        sender_id: str = "unknown",
    ) -> dict[str, Any]:
        return await self._post(
            "/life/health",
            {
                "life_root": self.config.life_root_folder,
                "health_folder": self.config.health_folder,
                "date": date,
                "time": time,
                "metric_type": metric_type,
                "value": value,
                "unit": unit,
                "duration_minutes": duration_minutes,
                "distance_km": distance_km,
                "status": status,
                "record_uid": record_uid,
                "note": note,
                "platform": platform,
                "sender_id": sender_id,
            },
        )

    async def write_plan_status(
        self,
        *,
        date: str,
        time: str,
        title: str,
        status: str,
        note: str | None = None,
        platform: str = "QQ",
        sender_id: str = "unknown",
    ) -> dict[str, Any]:
        return await self._post(
            "/life/plan/status",
            {
                "life_root": self.config.life_root_folder,
                "plan_folder": self.config.plan_folder,
                "date": date,
                "time": time,
                "title": title,
                "status": status,
                "note": note,
                "platform": platform,
                "sender_id": sender_id,
            },
        )

    async def write_summary(
        self,
        *,
        date: str,
        time: str,
        content: str,
        title: str | None = None,
        document_type: str = "日总结",
        platform: str = "QQ",
        sender_id: str = "unknown",
    ) -> dict[str, Any]:
        return await self._post(
            "/life/summary",
            {
                "life_root": self.config.life_root_folder,
                "summary_folder": self.config.summary_folder,
                "date": date,
                "time": time,
                "content": content,
                "title": title,
                "document_type": document_type,
                "platform": platform,
                "sender_id": sender_id,
            },
        )

    async def write_briefing(
        self,
        *,
        date: str,
        time: str,
        content: str,
        title: str | None = None,
        platform: str = "QQ",
        sender_id: str = "unknown",
    ) -> dict[str, Any]:
        return await self._post(
            "/life/briefing",
            {
                "life_root": self.config.life_root_folder,
                "summary_folder": self.config.summary_folder,
                "date": date,
                "time": time,
                "content": content,
                "title": title,
                "platform": platform,
                "sender_id": sender_id,
            },
        )

    async def revert_commit(self, commit_hash: str) -> dict[str, Any]:
        return await self._post(
            "/git/revert",
            {
                "commit_hash": commit_hash,
            },
        )

    async def health(self) -> dict[str, Any]:
        return await self._get("/health", require_token=False)

    async def git_status(self) -> dict[str, Any]:
        return await self._get("/git/status")

    async def recovery_index(self) -> dict[str, Any]:
        return await self._post(
            "/life/recovery-index",
            {
                "life_root": self.config.life_root_folder,
                "finance_folder": self.config.finance_folder,
                "plan_folder": self.config.plan_folder,
                "health_folder": self.config.health_folder,
            },
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.config.writer_base_url:
            raise ValueError("missing writer_base_url")
        if not self.config.writer_token:
            raise ValueError("missing writer_token")

        url = f"{self.config.writer_base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        headers = {"Authorization": f"Bearer {self.config.writer_token}"}
        clean_payload = {key: value for key, value in payload.items() if value is not None}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=clean_payload, headers=headers) as response:
                data = await _read_json(response)
                if response.status >= 400 or not data.get("ok"):
                    raise RuntimeError(
                        safe_error_text(f"writer failed: status={response.status}, response={data}")
                    )
                return data

    async def _get(self, path: str, *, require_token: bool = True) -> dict[str, Any]:
        if not self.config.writer_base_url:
            raise ValueError("missing writer_base_url")
        if require_token and not self.config.writer_token:
            raise ValueError("missing writer_token")

        url = f"{self.config.writer_base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        headers = {"Authorization": f"Bearer {self.config.writer_token}"} if require_token else {}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                data = await _read_json(response)
                if response.status >= 400 or not data.get("ok"):
                    raise RuntimeError(
                        safe_error_text(f"writer failed: status={response.status}, response={data}")
                    )
                return data


async def _read_json(response: aiohttp.ClientResponse) -> dict[str, Any]:
    text = await response.text()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text[:500]}
