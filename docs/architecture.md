# 架构说明

## 数据流

```text
聊天平台 -> AstrBot -> Obsidian Life Hub 插件 -> obsidian-inbox-writer -> Obsidian vault -> Git remote
```

## 插件侧职责

- 监听 AstrBot 消息事件。
- 只处理明确触发词，尽量不抢占普通聊天。
- 解析财务、计划、备忘、健康、日记、语录等结构化意图。
- 调用 writer API 写入 Markdown。
- 使用 AstrBot 数据目录保存 SQLite 索引，用于查询、撤销、复盘和定时任务。
- 在需要时调用 AstrBot 原生 future task 创建提醒。

## writer 侧职责

- 提供 `/life/...` 写入 API。
- 将记录追加到 Obsidian Markdown 文件。
- 为记录写入稳定 ID，便于撤销和反向恢复。
- 可选执行 Git add/commit/push。
- 提供 Markdown 反向恢复接口，让插件重建 SQLite 索引。

## Obsidian 目录建议

```text
生活/
  日记/
  笔记/
    随想笔记/
    语录笔记/
  财务/
  计划/
  健康/
  总结/
raw/
  inbox/
```

## 发布边界

本仓库包含插件源码和 writer 源码。用户安装插件后仍需要单独启动 writer，因为 writer 是运行时服务，不会被 AstrBot 插件市场自动作为容器启动。