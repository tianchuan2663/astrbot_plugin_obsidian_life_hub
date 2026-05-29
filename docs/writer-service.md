# writer 服务

`obsidian-inbox-writer` 是 Obsidian Life Hub 的配套 HTTP 服务，负责实际修改 Markdown 文件并可选执行 Git 同步。

## 为什么需要 writer

AstrBot 插件通常运行在机器人进程或容器内，直接挂载并修改 Obsidian vault 会把插件、文件系统权限、Git 凭据和同步逻辑绑得很紧。writer 把这些职责独立出来：

- 插件只负责识别意图、整理结构化数据和调用 API。
- writer 只负责文件追加、稳定 ID、Git commit/push、反向恢复。
- 用户可以把 writer 部署在能访问 vault 的本机、NAS 或云服务器上。

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `INBOX_TOKEN` | 是 | 无 | API Bearer Token。 |
| `VAULT_ROOT` | 是 | 当前目录 | Obsidian vault 根路径。 |
| `ENABLE_GIT_SYNC` | 否 | `false` | 写入后是否自动 Git 同步。 |
| `INBOX_TIMEZONE` | 否 | `Asia/Shanghai` | 写入时间和日期使用的时区。 |

## API 健康检查

```bash
curl http://127.0.0.1:8787/health
```

## 安全建议

- 不要把 writer 直接暴露到公网。
- `INBOX_TOKEN` 使用长随机字符串。
- Git SSH 私钥只读挂载给容器。
- 发布仓库不要提交 `.env`、私钥、known_hosts、vault 数据和 SQLite 数据库。