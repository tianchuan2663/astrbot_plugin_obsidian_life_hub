# Obsidian Life Hub

![AstrBot](https://img.shields.io/badge/AstrBot-4.16%2B-2f6fed)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab)
![License](https://img.shields.io/badge/License-MIT-green)

Obsidian Life Hub 是一个面向 Obsidian 的 AstrBot 生活记录插件。它把聊天里的日记、随想、语录、记账、计划、备忘、健康记录和阶段性报告沉淀到 Obsidian vault，并可由配套 writer 服务完成 Markdown 写入与 Git 同步。

它的设计目标很简单：聊天时用中文触发词快速记录，Obsidian 里保持结构化、可恢复、可持续整理。

## 适合谁

- 想用 QQ、Telegram、飞书、企业微信等聊天入口记录生活的人。
- 希望把日常记录、财务、计划、健康数据统一落到 Obsidian 的人。
- 不想把 AstrBot 容器直接绑定到 vault 写文件，希望通过独立写入服务隔离权限的人。
- 想要晨报、今日总结、周报、语录周精选等生活助手体验的人。

## 核心特点

| 能力 | 说明 |
|---|---|
| 一个总指令 | AstrBot 管理行为里只注册 `查看触发词`，其它能力都通过聊天触发词使用。 |
| 中文触发词 | 支持 `记账`、`支出`、`计划`、`备忘`、`随想`、`语录`、`体重`、`晨报`、`今日总结` 等中文入口。 |
| 结构化写入 | 财务、计划、备忘、健康以 Markdown 表格追加；日记和笔记按中文目录沉淀。 |
| 修正与恢复 | 支持 `撤销上一条`、`改上一条`、`作废账目`、`修改账目`、`修改计划`、`恢复索引`。 |
| 定时报告 | 支持晨报、晚间询问、深夜今日总结、周报和语录周精选。 |
| 原生提醒边界 | `提醒我...` 桥接 AstrBot 原生 future task；`备忘...` 写入 Obsidian 备忘。 |
| 可通用部署 | 路径、目录、天气、预算、推送时间、功能开关都在配置页里调整。 |

## 工作方式

```text
聊天平台
  -> AstrBot + Obsidian Life Hub
  -> obsidian-inbox-writer HTTP 服务
  -> Obsidian vault Markdown 文件
  -> 可选 Git commit/push
```

插件本身不直接写 vault 文件，而是调用仓库内配套的 `services/obsidian-inbox-writer`。这样做的好处是：

- AstrBot 可以部署在云服务器、容器或本机，writer 单独负责文件写入。
- writer 可以挂载 Obsidian vault，并统一处理路径安全、Markdown 追加和 Git 同步。
- 插件重装后可通过 `恢复索引` 从已写入的 Markdown 反向恢复 SQLite 索引。

## 安装

### 1. 克隆插件

进入 AstrBot 插件目录，例如：

```bash
cd /path/to/AstrBot/data/plugins
git clone https://github.com/tianchuan2663/astrbot_plugin_obsidian_life_hub.git
```

重启 AstrBot，或在 WebUI 的插件管理里重载插件。

### 2. 启动 writer 服务

复制环境变量模板：

```bash
cd /path/to/AstrBot/data/plugins/astrbot_plugin_obsidian_life_hub
cp deploy/.env.example deploy/.env
```

编辑 `deploy/.env`，至少填写：

| 变量 | 说明 |
|---|---|
| `INBOX_TOKEN` | writer 访问令牌，建议使用长随机字符串。 |
| `VAULT_HOST_PATH` | 宿主机上的 Obsidian vault 绝对路径。 |
| `INBOX_TIMEZONE` | 时区，默认 `Asia/Shanghai`。 |
| `ENABLE_GIT_SYNC` | 是否写入后自动 Git 同步，初次测试可先用 `false`。 |

启动 writer：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.writer.yml up -d --build
```

检查 writer：

```bash
curl http://127.0.0.1:8787/health
```

### 3. 配置插件

在 AstrBot WebUI 打开 `Obsidian Life Hub` 配置页，先填最小可用配置：

| 配置项 | 推荐值或说明 |
|---|---|
| `enabled` | `true` |
| `writer_base_url` | 同 Docker 网络可填 `http://obsidian-inbox-writer:8787`；跨机器部署填写 AstrBot 可访问的 writer 地址。 |
| `writer_token` | 必须与 writer 的 `INBOX_TOKEN` 一致。 |
| `life_root_folder` | 默认 `生活`，所有生活层内容会写到该目录下。 |
| `push_target_session` | 可留空，稍后在聊天里发送 `推送到这里` 自动设置。 |
| `amap_weather_key` | 可选，高德天气 API Key；留空则晨报跳过天气。 |
| `amap_weather_city` | 高德 adcode，例如青岛 `370200`、深圳 `440300`。 |
| `weather_city_name` | 晨报展示用中文城市名，例如 `青岛`。 |

### 4. 验证链路

在机器人聊天里发送：

```text
查看触发词
Obsidian状态
随想 插件安装成功，写入链路开始测试
```

如果要启用定时推送，再发送：

```text
推送到这里
```

## 配置页说明

| 分组 | 配置项 | 作用 |
|---|---|---|
| 基础 | `assistant_display_name` | 回复中展示的助手名称。 |
| 基础 | `currency_symbol`、`monthly_budget` | 财务展示货币符号和月预算。 |
| writer | `writer_base_url`、`writer_token`、`timeout_seconds` | 连接 writer 服务。 |
| 目录 | `life_root_folder`、`diary_folder`、`notes_folder`、`finance_folder`、`plan_folder`、`health_folder`、`summary_folder` | 控制 Obsidian 中的中文目录结构。 |
| 功能开关 | `enable_auto_record` | 是否启用明确触发词记录。 |
| 功能开关 | `enable_inbox` | 是否启用 `记 / 收集 / 存一下` 原始收集。 |
| 功能开关 | `enable_diary`、`enable_notes`、`enable_finance`、`enable_plans`、`enable_health` | 分别控制日记、笔记、财务、计划、健康模块。 |
| 功能开关 | `enable_native_future_task_bridge` | 是否把 `提醒我...` 桥接到 AstrBot 原生 future task。 |
| 总结 | `enable_daily_summary`、`include_conversations_in_summaries` | 控制今日总结，以及是否把普通聊天片段纳入总结参考。 |
| 晨报 | `enable_morning_briefing`、`write_briefing_to_obsidian` | 控制晨报生成与是否写入 Obsidian。 |
| 定时 | `enable_scheduler`、`morning_briefing_time`、`evening_checkin_time`、`daily_summary_time`、`weekly_summary_day`、`weekly_summary_time` | 控制定时推送时间。 |
| 天气 | `amap_weather_key`、`amap_weather_city`、`weather_city_name` | 控制晨报天气来源和城市显示。 |

## 总指令

AstrBot 管理行为里只会看到一个插件指令：

```text
查看触发词
```

这个指令会在聊天中展示完整触发词表和示例。插件内部会兼容少量旧帮助词，但公开使用时建议统一使用 `查看触发词`。

## 常用触发词

### 财务

| 目的 | 示例 |
|---|---|
| 支出 | `支出 午饭9元 支付宝` |
| 收入 | `收入 兼职500元 中国银行` |
| 普通记账 | `记账 咖啡18元 微信` |
| 借出 | `借出 给张三100元 微信` |
| 借入 | `借入 向李四200元` |
| 还款 | `还款 张三100元 支付宝` |
| 收款 | `收款 李四200元 微信` |
| 转账 | `转账 微信转到中国银行300元` |
| 查询 | `今日财务` / `本周财务` / `本月财务` / `借贷情况` / `钱包统计` / `预算情况` |
| 报告 | `财务周报` / `财务月报` |
| 修正 | `作废账目 午饭` / `修改账目 午饭 为 支出 午饭10元 支付宝` |

### 计划与备忘

| 目的 | 示例 |
|---|---|
| 日计划 | `计划 明天 高优先级 整理插件配置` |
| 周计划 | `计划 本周 跑通安装流程` |
| 月计划 | `计划 本月 整理 Obsidian 目录` |
| 长期计划 | `计划 长期 去青岛周边旅行` |
| 备忘/DDL | `备忘 明天 20:00 交材料` / `DDL 5月30日 23:59 提交论文终稿` |
| 查询计划 | `我的计划` / `今日计划` / `本周计划` / `本月计划` / `长期计划` / `空闲计划` |
| 查询备忘 | `今日备忘` / `近期备忘` / `我的备忘` |
| 闭环 | `开始计划 插件` / `完成计划 插件` / `推迟计划 插件 到 明天` / `计划复盘` |
| 修正 | `取消计划 清单` / `修改计划 清单 为 明天 整理宿舍` |

### 日记、笔记和语录

| 目的 | 示例 |
|---|---|
| 日记素材 | `日记 今天晚上把插件整理成独立仓库` |
| 记事 | `记事 下午和同学讨论了答辩材料` |
| 随想 | `随想 通用插件要把个人路径和密钥都配置化` |
| 语录 | `语录 抖音｜某账号｜保持稳定比偶尔热血更重要｜#自律｜提醒我持续` |
| 补记 | `补记 昨天 21:30 日记 和朋友散步` |
| 原始收集 | `收集 这个链接以后研究一下：https://example.com` / `记 #灵感 一个新想法` |

语录也支持字段式写法：

```text
语录 原句：生活系统需要稳定可恢复 来源：测试 作者或账号：Codex 标签：链路 一句话感想：用于验证写入
```

### 健康

| 目的 | 示例 |
|---|---|
| 体重 | `体重 75.5kg` |
| 跑步 | `跑步 5公里 30分钟` |
| 睡眠 | `睡眠 7.5小时` |
| 健身 | `健身 胸背训练 45分钟` |
| 查询 | `今日健康` / `本周健康` / `本月健康` / `健康概览` |

### 报告与系统

| 目的 | 触发词 |
|---|---|
| 晨报 | `晨报` |
| 今日总结 | `今日总结` / `日总结` / `总结` |
| 日记草稿 | `日记草稿` |
| 周报 | `周报` |
| 语录精选 | `语录周精选` |
| 设置定时推送目标 | `推送到这里` |
| 状态检查 | `Obsidian状态` / `系统状态` |
| 反向恢复索引 | `恢复索引` / `重建索引` |
| 撤销 | `撤销上一条` |
| 修改上一条 | `改上一条 记账 午饭18元` |
| 帮助 | `查看触发词` |

## 原生提醒与备忘的区别

| 说法 | 结果 |
|---|---|
| `提醒我 明天 20:00 跑步` | 创建 AstrBot 原生 future task，不写入 Obsidian。 |
| `备忘 明天 20:00 交材料` | 写入 Obsidian 备忘，用于晨报、今日总结和备忘查询。 |

这样可以避免插件抢占 AstrBot 原生能力，也方便其它用户安装后继续使用 AstrBot 自带的未来任务面板。

## Obsidian 目录结构

默认写入结构如下，可在配置页改名：

```text
生活/
  日记/
    2026/2026-05/2026-05-29.md
  笔记/
    随想笔记/
    语录笔记/
    游戏笔记/
    读书笔记/
  财务/
    2026-05.md
  计划/
    计划清单.md
  健康/
    2026-05.md
  总结/
    晨报/
    日总结/
    周报/
    语录周精选/
raw/
  inbox/
```

## 定时内容

| 时间配置 | 默认值 | 内容 |
|---|---|---|
| `morning_briefing_time` | `08:00` | 生成晨报：日期、中文城市天气、今日计划和备忘。 |
| `evening_checkin_time` | `22:00` | 晚间询问是否需要总结。 |
| `daily_summary_time` | `23:55` | 自动生成今日总结：待办提醒、财务简讯、日记草稿。 |
| `weekly_summary_day` + `weekly_summary_time` | 周日 `21:30` | 生成周报和语录周精选。 |

手动发送 `晨报`、`今日总结`、`周报` 与定时生成使用同一套内容逻辑。

## 常见问题

### 管理行为里为什么只有一个命令？

这是有意设计。插件只注册 `查看触发词` 作为总入口，其它能力全部走聊天触发词，避免管理面板被几十个低频命令占满。

### writer 是必须的吗？

是的。当前版本需要 `obsidian-inbox-writer` 写入 Obsidian 文件。writer 已包含在本仓库的 `services/obsidian-inbox-writer/` 中，下载插件仓库时会一起下载；部署时仍需要按文档启动 writer 服务，并把 vault 路径挂载给它。

### 为什么发送“提醒我...”不会写入 Obsidian？

因为这类句式属于 AstrBot 原生未来任务。插件只做桥接，不写入 Obsidian，避免破坏 AstrBot 原本的提醒体验。需要写入 Obsidian 的截止事项请使用 `备忘` 或 `DDL`。

### 天气不显示怎么办？

检查 `amap_weather_key`、`amap_weather_city` 和 `weather_city_name`。高德城市 adcode 示例：青岛 `370200`，深圳 `440300`。Key 留空时晨报会自动跳过天气。

### 写入成功但 Obsidian 没同步到 Git？

检查 writer 的 `ENABLE_GIT_SYNC`、仓库远程地址、SSH Key、Git 用户名和网络。即使 Git 同步失败，Markdown 写入也可能已经完成，可先看 writer 日志和 vault 文件。

### 重装插件后历史数据还在吗？

Markdown 文件仍在 Obsidian。SQLite 索引用于查询、撤销和统计；重装后可发送 `恢复索引`，从现有财务、计划、健康 Markdown 中恢复可查询索引。

## 文档

- [安装指南](docs/installation.md)
- [配置说明](docs/configuration.md)
- [使用手册](docs/usage.md)
- [writer 服务](docs/writer-service.md)
- [架构说明](docs/architecture.md)
- [故障排查](docs/troubleshooting.md)

## 安全建议

- 不要把 `writer_token`、`INBOX_TOKEN`、高德 API Key、SSH 私钥提交到 Git。
- writer 对 vault 有写权限，建议只暴露给 AstrBot 所在内网或 Docker 网络。
- 公网部署时请加反向代理、HTTPS、访问控制或防火墙限制。
- 初次使用建议先关闭 `ENABLE_GIT_SYNC` 验证写入，再开启自动同步。

## 许可

MIT License。见 [LICENSE](LICENSE)。
