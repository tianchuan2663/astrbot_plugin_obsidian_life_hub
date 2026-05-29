# 故障排查

## `Obsidian状态` 显示 writer 异常

1. 确认 writer 容器正在运行。
2. 在 AstrBot 所在机器执行 `curl http://writer地址/health`。
3. 检查插件的 `writer_base_url` 是否能从 AstrBot 容器访问。
4. 检查 `writer_token` 是否与 `INBOX_TOKEN` 一致。

## 写入成功但 Obsidian 看不到

1. 检查 writer 的 `VAULT_ROOT` 或 `VAULT_HOST_PATH` 是否指向正确 vault。
2. 检查生成路径是否在 `生活/` 或 `raw/inbox/` 下。
3. 如果使用 Git 同步，确认本地 Obsidian 已 pull 最新提交。

## Git 同步失败

1. 临时设置 `ENABLE_GIT_SYNC=false` 验证写入本身是否正常。
2. 检查 SSH key 是否只读挂载到容器内。
3. 检查远程仓库是否允许该公钥写入。
4. 进入容器执行 `git status` 和 `git remote -v` 查看仓库状态。

## 提醒没有进入 AstrBot 原生未来任务

1. 确认 `enable_native_future_task_bridge=true`。
2. 使用明确句式，例如 `明天上午十点提醒我交材料`。
3. `备忘 明天 20:00 交材料` 是 Obsidian 备忘，不会创建 AstrBot 原生 future task。

## 普通聊天被误写入

默认 `auto_record_mode=explicit`，普通聊天不应被写入。若开启了包含普通聊天到总结的选项，请确认 `include_conversations_in_summaries` 是否符合预期。