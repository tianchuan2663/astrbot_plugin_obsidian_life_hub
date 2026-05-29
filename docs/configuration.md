# 配置说明

## writer 连接

| 配置 | 说明 |
|---|---|
| `writer_base_url` | writer HTTP 服务地址，不要带末尾 `/`。 |
| `writer_token` | writer Bearer Token，必须与 `INBOX_TOKEN` 一致。 |
| `timeout_seconds` | 调用 writer 的超时时间。 |

## 写入与触发

| 配置 | 说明 |
|---|---|
| `enabled` | 插件总开关。 |
| `enable_auto_record` | 是否启用明确触发词记录。 |
| `enable_inbox` | 是否启用“记 / 收集 / 存一下”原始收集。 |
| `enable_native_future_task_bridge` | 是否把“提醒我...”桥接到 AstrBot 原生 future task。 |
| `include_conversations_in_summaries` | 是否把普通聊天作为今日总结背景材料，默认关闭。 |

## 目录

| 配置 | 默认值 | 说明 |
|---|---|---|
| `life_root_folder` | `生活` | Obsidian 生活层根目录。 |
| `diary_folder` | `日记` | 日记目录。 |
| `notes_folder` | `笔记` | 随想、语录等笔记目录。 |
| `finance_folder` | `财务` | 财务记录目录。 |
| `plan_folder` | `计划` | 计划与备忘目录。 |
| `health_folder` | `健康` | 健康记录目录。 |
| `summary_folder` | `总结` | 报告目录。 |

## 定时推送

| 配置 | 默认值 | 说明 |
|---|---|---|
| `enable_scheduler` | `true` | 是否启用定时任务。 |
| `morning_briefing_time` | `08:00` | 晨报推送时间。 |
| `daily_summary_time` | `23:55` | 今日总结生成时间。 |
| `evening_checkin_time` | `22:00` | 晚间提醒时间。 |
| `weekly_summary_day` | `7` | 周报推送星期，1 到 7 表示周一到周日。 |
| `weekly_summary_time` | `21:30` | 周报推送时间。 |
| `push_target_session` | 空 | 推送目标会话，可用“推送到这里”自动设置。 |

## 天气

| 配置 | 说明 |
|---|---|
| `amap_weather_key` | 高德开放平台天气 API Key。 |
| `amap_weather_city` | 城市 adcode，例如青岛 `370200`。 |
| `weather_city_name` | 用于报告展示的中文城市名。 |