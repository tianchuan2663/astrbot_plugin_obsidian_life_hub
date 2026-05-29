# Obsidian Life Hub

Obsidian Life Hub 是一个 AstrBot 插件，用来把聊天中的生活记录、计划、备忘、财务、健康数据和阶段性报告沉淀到 Obsidian vault。

插件不直接在 AstrBot 容器里写 vault 文件，而是调用配套的 `obsidian-inbox-writer` HTTP 服务。这样可以把聊天意图识别、Markdown 文件写入、Git 同步和反向恢复拆开，方便本地、NAS 或云服务器部署。

## 主要能力

- 明确触发词写入：记账、支出、收入、借入、借出、计划、备忘、随想、语录、体重、跑步、睡眠等。
- 报告生成：晨报、今日总结、日记草稿、周报、语录周精选。
- Obsidian 结构化落盘：按 `生活/` 下的中文目录追加 Markdown 表格或段落。
- 原生提醒桥接：明确的“提醒我...”句式可创建 AstrBot 原生 future task，不写入 Obsidian。
- 数据恢复：从 writer 已生成的 Markdown 反向恢复 SQLite 索引，降低重装或迁移风险。
- 状态检查：检查 writer、Git、SQLite 索引和待确认队列。

## 仓库结构

```text
astrbot_plugin_obsidian_life_hub/
  main.py
  metadata.yaml
  _conf_schema.json
  requirements.txt
  services/obsidian-inbox-writer/
  deploy/
  docs/
```

## 安装概览

1. 在 AstrBot 的 `data/plugins` 目录克隆本仓库。
2. 启动 `services/obsidian-inbox-writer`，并把 Obsidian vault 挂载给 writer。
3. 在 AstrBot WebUI 插件配置页填写 `writer_base_url` 与 `writer_token`。
4. 在聊天里发送 `Obsidian状态`、`Obsidian帮助` 验证插件状态。

详细步骤见 [docs/installation.md](docs/installation.md)。

## 最小配置

插件侧至少需要：

- `writer_base_url`：writer 服务地址，例如 `http://obsidian-inbox-writer:8787`。
- `writer_token`：必须与 writer 的 `INBOX_TOKEN` 一致。
- `push_target_session`：需要定时推送晨报/总结时，可以向机器人发送“推送到这里”自动记录当前会话。

writer 侧至少需要：

- `INBOX_TOKEN`：访问令牌。
- `VAULT_ROOT`：容器或本机内的 Obsidian vault 根路径。
- `INBOX_TIMEZONE`：默认 `Asia/Shanghai`。
- `ENABLE_GIT_SYNC`：是否在写入后执行 Git 同步。

## 常用触发词

| 类型 | 示例 |
|---|---|
| 记账 | `记账 午饭 18 元 支付宝` / `支出 咖啡 20 微信` / `收入 兼职 500` |
| 借贷 | `借出 给张三 100 微信` / `借入 向李四 200` |
| 计划 | `计划 明天 高优先级 整理插件发布文档` / `长期计划 青岛周边旅行` |
| 备忘 | `备忘 明天 20:00 交材料` |
| 笔记 | `随想 通用插件要把个人路径和密钥都配置化` |
| 语录 | `语录 抖音｜某账号｜保持稳定比偶尔热血更重要｜#自律｜提醒我持续` |
| 健康 | `体重 75.5kg` / `跑步 5km 30分钟` / `睡眠 7.5小时` |
| 报告 | `晨报` / `今日总结` / `周报` / `语录周精选` |
| 系统 | `Obsidian状态` / `Obsidian帮助` / `恢复索引` / `撤销上一条` |

## 与 AstrBot 原生功能的边界

Obsidian Life Hub 是普通 AstrBot 插件，不修改 AstrBot 框架源码。默认只处理明确触发词；普通聊天会继续交给 AstrBot 原有对话流程。明确的“提醒我...”句式会桥接到 AstrBot 原生 future task，插件不会把这类提醒重复写入 Obsidian。

## 文档

- [安装指南](docs/installation.md)
- [配置说明](docs/configuration.md)
- [使用手册](docs/usage.md)
- [writer 服务](docs/writer-service.md)
- [架构说明](docs/architecture.md)
- [故障排查](docs/troubleshooting.md)

## 许可

MIT License。见 [LICENSE](LICENSE)。