# 安装指南

## 1. 克隆插件

进入 AstrBot 的插件目录：

```bash
cd /path/to/AstrBot/data/plugins
git clone https://github.com/tianchuan2663/astrbot_plugin_obsidian_life_hub.git
```

重启 AstrBot，或在 WebUI 的插件管理里重载插件。

## 2. 启动 writer 服务

writer 是 Obsidian 文件写入服务。它需要能访问你的 vault 根目录。

```bash
cd /path/to/AstrBot/data/plugins/astrbot_plugin_obsidian_life_hub
cp deploy/.env.example deploy/.env
```

编辑 `deploy/.env`：

- `INBOX_TOKEN` 改成长随机字符串。
- `VAULT_HOST_PATH` 改成 Obsidian vault 的宿主机绝对路径。
- 如果暂时不需要 Git 同步，保持 `ENABLE_GIT_SYNC=false`。

启动：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.writer.yml up -d --build
```

检查：

```bash
curl http://127.0.0.1:8787/health
```

## 3. 配置插件

在 AstrBot WebUI 打开 Obsidian Life Hub 配置页：

- `writer_base_url`：如果 AstrBot 和 writer 在同一 Docker 网络，可填 `http://obsidian-inbox-writer:8787`；否则填可访问的实际地址。
- `writer_token`：填写 `deploy/.env` 中的 `INBOX_TOKEN`。
- `amap_weather_key`：可选，高德天气 Key。
- `weather_city_name` 与 `amap_weather_city`：默认青岛，可按需修改。

## 4. 验证

在机器人会话发送：

```text
Obsidian状态
Obsidian帮助
随想 插件安装成功，写入链路开始测试
```

如果需要定时晨报和总结，再发送：

```text
推送到这里
```