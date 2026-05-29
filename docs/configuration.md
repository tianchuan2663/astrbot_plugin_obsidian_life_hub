# 配置说明

配置页默认只展示常用项，避免首次安装时被大量高级开关淹没。插件仍会读取旧配置和隐藏高级字段，因此升级不会导致已有配置失效。

## 必填连接

| 配置 | 默认值 | 说明 |
|---|---|---|
| `enabled` | `true` | 插件总开关。 |
| `writer_base_url` | `http://obsidian-inbox-writer:8787` | writer HTTP 服务地址，不要带末尾 `/`。 |
| `writer_token` | 空 | writer Bearer Token，必须与 `INBOX_TOKEN` 一致。 |
| `life_root_folder` | `生活` | Obsidian 生活层根目录。 |

## 常用行为

| 配置 | 默认值 | 说明 |
|---|---|---|
| `enable_native_future_task_bridge` | `true` | 是否把“提醒我...”桥接到 AstrBot 原生 future task。 |
| `include_conversations_in_summaries` | `false` | 是否把普通聊天作为今日总结背景材料。 |
| `reply_on_success` | `true` | 写入成功后是否在聊天里回复路径。 |

## 财务

| 配置 | 默认值 | 说明 |
|---|---|---|
| `currency_symbol` | `¥` | 财务展示使用的货币符号。 |
| `monthly_budget` | `0` | 月度预算，填 0 表示关闭预算提醒。 |

## 定时推送

| 配置 | 默认值 | 说明 |
|---|---|---|
| `enable_scheduler` | `true` | 是否启用定时任务。 |
| `push_target_session` | 空 | 推送目标会话，可用“推送到这里”自动设置。 |
| `morning_briefing_time` | `08:00` | 晨报推送时间。 |
| `evening_checkin_time` | `22:00` | 晚间询问时间。 |
| `daily_summary_time` | `23:55` | 今日总结生成时间。 |
| `weekly_summary_day` | `7` | 周报推送星期，1 到 7 表示周一到周日。 |
| `weekly_summary_time` | `21:30` | 周报推送时间。 |

## 天气

| 配置 | 默认值 | 说明 |
|---|---|---|
| `amap_weather_key` | 空 | 高德开放平台天气 API Key。 |
| `amap_weather_city` | `370200` | 城市 adcode，例如青岛 `370200`、深圳 `440300`。 |
| `weather_city_name` | `青岛` | 用于晨报展示的中文城市名。 |

## 隐藏高级字段

这些字段不再默认显示在配置页，但仍可保留在配置 JSON 中使用：

```text
assistant_display_name
diary_folder / notes_folder / finance_folder / plan_folder / health_folder / summary_folder
enable_auto_record / enable_inbox / inbox_require_admin / inbox_allowed_sender_ids
enable_diary / enable_notes / enable_finance / enable_plans / enable_health
enable_daily_summary / enable_morning_briefing / write_briefing_to_obsidian
auto_polish / timeout_seconds
```