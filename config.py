from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LifePluginConfig:
    enabled: bool
    assistant_display_name: str
    currency_symbol: str
    monthly_budget: float
    writer_base_url: str
    writer_token: str
    life_root_folder: str
    diary_folder: str
    notes_folder: str
    finance_folder: str
    plan_folder: str
    health_folder: str
    summary_folder: str
    enable_native_future_task_bridge: bool
    enable_auto_record: bool
    auto_record_mode: str
    enable_inbox: bool
    inbox_require_admin: bool
    inbox_allowed_sender_ids: list[str]
    enable_diary: bool
    enable_notes: bool
    enable_finance: bool
    enable_plans: bool
    enable_health: bool
    enable_daily_summary: bool
    include_conversations_in_summaries: bool
    enable_morning_briefing: bool
    auto_polish: bool
    write_briefing_to_obsidian: bool
    enable_scheduler: bool
    morning_briefing_time: str
    evening_checkin_time: str
    daily_summary_time: str
    weekly_summary_day: int
    weekly_summary_time: str
    push_target_session: str
    amap_weather_key: str
    amap_weather_city: str
    weather_city_name: str
    timeout_seconds: float
    reply_on_success: bool

    @classmethod
    def from_astrbot_config(cls, config: Any) -> "LifePluginConfig":
        cfg = _ConfigReader(config)
        return cls(
            enabled=cfg.bool("enabled", True),
            assistant_display_name=cfg.str("assistant_display_name", "Obsidian Life Hub"),
            currency_symbol=cfg.str("currency_symbol", "¥"),
            monthly_budget=cfg.float("monthly_budget", 0.0),
            writer_base_url=cfg.str("writer_base_url", "http://obsidian-inbox-writer:8787").rstrip("/"),
            writer_token=cfg.str("writer_token", ""),
            life_root_folder=cfg.str("life_root_folder", "生活"),
            diary_folder=cfg.str("diary_folder", "日记"),
            notes_folder=cfg.str("notes_folder", "笔记"),
            finance_folder=cfg.str("finance_folder", "财务"),
            plan_folder=cfg.str("plan_folder", "待办"),
            health_folder=cfg.str("health_folder", "健康"),
            summary_folder=cfg.str("summary_folder", "总结"),
            enable_native_future_task_bridge=cfg.bool("enable_native_future_task_bridge", True),
            enable_auto_record=cfg.bool("enable_auto_record", True),
            auto_record_mode=cfg.str("auto_record_mode", "explicit").lower(),
            enable_inbox=cfg.bool("enable_inbox", True),
            inbox_require_admin=cfg.bool("inbox_require_admin", True),
            inbox_allowed_sender_ids=cfg.str_list("inbox_allowed_sender_ids", []),
            enable_diary=cfg.bool("enable_diary", True),
            enable_notes=cfg.bool("enable_notes", True),
            enable_finance=cfg.bool("enable_finance", True),
            enable_plans=cfg.bool("enable_plans", True),
            enable_health=cfg.bool("enable_health", True),
            enable_daily_summary=cfg.bool("enable_daily_summary", True),
            include_conversations_in_summaries=cfg.bool("include_conversations_in_summaries", False),
            enable_morning_briefing=cfg.bool("enable_morning_briefing", True),
            auto_polish=cfg.bool("auto_polish", False),
            write_briefing_to_obsidian=cfg.bool("write_briefing_to_obsidian", True),
            enable_scheduler=cfg.bool("enable_scheduler", True),
            morning_briefing_time=cfg.str("morning_briefing_time", "08:00"),
            evening_checkin_time=cfg.str("evening_checkin_time", "22:00"),
            daily_summary_time=cfg.str("daily_summary_time", cfg.str("diary_draft_time", "23:55")),
            weekly_summary_day=cfg.int("weekly_summary_day", 7),
            weekly_summary_time=cfg.str("weekly_summary_time", "21:30"),
            push_target_session=cfg.str(
                "push_target_session",
                # Legacy compatibility: old versions exposed separate push targets.
                cfg.str("briefing_push_target", cfg.str("summary_push_target", "")),
            ),
            amap_weather_key=cfg.str("amap_weather_key", ""),
            amap_weather_city=cfg.str("amap_weather_city", "370200"),
            weather_city_name=cfg.str("weather_city_name", "青岛"),
            timeout_seconds=cfg.float("timeout_seconds", 12.0),
            reply_on_success=cfg.bool("reply_on_success", True),
        )


class _ConfigReader:
    def __init__(self, config: Any):
        self.config = config or {}

    def get(self, key: str, default: Any) -> Any:
        try:
            return self.config.get(key, default)
        except Exception:
            return default

    def str(self, key: str, default: str) -> str:
        value = self.get(key, default)
        return str(value if value is not None else default).strip()

    def bool(self, key: str, default: bool) -> bool:
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def int(self, key: str, default: int) -> int:
        value = self.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def float(self, key: str, default: float) -> float:
        value = self.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def str_list(self, key: str, default: list[str]) -> list[str]:
        value = self.get(key, default)
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
        return normalized
