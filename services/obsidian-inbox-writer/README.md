# obsidian-inbox-writer

`obsidian-inbox-writer` 是 Obsidian Life Hub 的配套写入服务。它接收插件发来的结构化数据，追加写入 Obsidian vault，并可选执行 Git 同步。

## 职责边界

- 写入 `raw/inbox/` 和 `生活/` 下的 Markdown。
- 为记录生成稳定 ID，支持撤销和 Markdown 反向恢复。
- 可选执行 Git add/commit/push。
- 不处理聊天意图识别，不直接调用 AstrBot，也不整理 `wiki/`。

## 本地运行

需要 Python 3.10+。

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INBOX_TOKEN="change-me"
export VAULT_ROOT="/path/to/your/obsidian/vault"
export ENABLE_GIT_SYNC="false"
export INBOX_TIMEZONE="Asia/Shanghai"
uvicorn app.main:app --host 127.0.0.1 --port 8787
```

Windows PowerShell 示例：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:INBOX_TOKEN="change-me"
$env:VAULT_ROOT="D:\Obsidian\your-vault"
$env:ENABLE_GIT_SYNC="false"
$env:INBOX_TIMEZONE="Asia/Shanghai"
uvicorn app.main:app --host 127.0.0.1 --port 8787
```

健康检查：

```bash
curl http://127.0.0.1:8787/health
```

## Docker Compose

```bash
cp .env.example .env
# edit .env
docker compose up -d --build
```

默认只绑定到 `127.0.0.1`，避免把写入服务暴露到公网。如果 AstrBot 和 writer 都在 Docker 内，建议放到同一 Docker network，然后在插件配置中填写：

```text
http://obsidian-inbox-writer:8787
```

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `INBOX_TOKEN` | 是 | 无 | API Bearer Token。 |
| `VAULT_ROOT` | 是 | 当前目录 | 容器或进程内的 Obsidian vault 根路径。 |
| `ENABLE_GIT_SYNC` | 否 | `false` | 写入后是否执行 Git 同步。 |
| `INBOX_TIMEZONE` | 否 | `Asia/Shanghai` | 写入日期和时间使用的时区。 |
| `VAULT_HOST_PATH` | Docker 必填 | 无 | 宿主机上的 vault 绝对路径。 |
| `INBOX_WRITER_BIND` | 否 | `127.0.0.1` | writer 端口绑定地址。 |
| `INBOX_WRITER_PORT` | 否 | `8787` | writer 暴露端口。 |
| `GIT_SSH_KEY_PATH` | Git 同步时需要 | `/root/.ssh/id_ed25519` | 宿主机 SSH 私钥路径。 |
| `GIT_KNOWN_HOSTS_PATH` | Git 同步时建议 | `/root/.ssh/known_hosts` | known_hosts 路径。 |

## 常用接口

- `GET /health`：返回服务状态。
- `POST /append`：追加原始消息到 `raw/inbox/YYYY-MM-DD.md`。
- `POST /life/diary`：追加日记事件。
- `POST /life/note`：追加随想、语录等笔记。
- `POST /life/finance`：追加财务记录。
- `POST /life/plan`：追加计划。
- `POST /life/reminder`：追加备忘。
- `POST /life/health`：追加健康记录。
- `POST /life/summary`：写入日总结、周报、语录周精选等报告。
- `POST /life/briefing`：写入晨报。
- `GET /life/recovery-index`：从 Markdown 反向提取记录，用于插件重建 SQLite 索引。

## 安全建议

- 不要把 writer 直接开放到公网。
- `INBOX_TOKEN` 使用长随机字符串，并与插件配置中的 `writer_token` 一致。
- 私有仓库 Git 同步时，SSH 私钥只读挂载。
- 不要提交 `.env`、私钥、known_hosts、vault 数据、SQLite 数据库和日志文件。