# AWBotNest-Plugins

> AWBotNest 平台的插件仓库。这里的每个插件都遵循平台「**单文件 / 文件夹插件**」规范，可被平台「从 GitHub 导入」或配置为「插件仓库自动同步」的源。

- 平台仓库：[AWdress/AWBotHub](https://github.com/AWdress/AWBotHub)（AWBotNest）
- 本仓库来源：从旧项目 AWLottery 的功能逐个迁移、改写为平台规范插件。迁移进度见 [MIGRATION.md](MIGRATION.md)。

---

## 一分钟上手

1. 复制平台的 `plugins/_TEMPLATE.py`（或本仓库任一插件），改名成你的功能名，如 `my_feature.py`。文件名就是插件 ID。
2. 改顶部的 `__plugin__` 字典（`id` 必须等于文件名）。
3. 在 `setup(ctx)` 里写逻辑，处理器一律用 `ctx.on_message` / `ctx.on_callback` 注册。
4. 把插件放进平台 `plugins/`，或上传、或从本仓库导入。
5. 在平台插件列表打开开关 → 立即生效；关掉 → 立即卸载。**不用重启，不用改其它文件。**

---

## 插件规范

### 1. 三段式契约

每个插件必须有这三段（`teardown` 可选）：

```python
# ① 元数据：平台靠它在前端显示。必须是纯字面量字典（平台用 AST 静态解析）
__plugin__ = {
    "name": "我的功能",        # 必填：前端显示名
    "id": "my_feature",        # 必填：必须 = 文件名/目录名（去 .py）
    "version": "1.0.0",        # 必填：自动同步靠它判断有没有更新
    "scope": "user",           # 必填：user(用户账号) | bot(机器人) | both
    "author": "你",            # 可选
    "description": "干啥的",    # 可选
    "default_enabled": False,  # 可选：放入本地 plugins/ 时是否默认启用
    "config_schema": { ... },  # 可选：前端自动生成配置表单
}

# ② 启用时调用：在这里注册处理器（可 async 可同步）
async def setup(ctx):
    @ctx.on_message(ctx.filters.text)
    async def handler(client, message):
        await message.reply("收到")

# ③ 停用时调用（可选）：只清理你自己开的资源
async def teardown(ctx):
    pass
```

### 2. 两种形态

- **单文件**：`plugins/<id>.py` —— 简单插件，文件名 = ID。
- **文件夹**：`plugins/<id>/__init__.py` —— 复杂插件（多模块/资源），目录名 = ID，`__plugin__` 与 `setup` 写在 `__init__.py`，包内可 `from ._helper import ...`。
- 同名时单文件优先；以 `_` 开头的文件/目录不会被识别为插件（用作模板/私有辅助）。

### 3. `ctx` 能力速查

插件**只能**通过 `ctx` 访问平台，要什么都从它拿：

| 能力 | 用法 |
|------|------|
| 过滤器 | `ctx.filters.text` / `.photo` / `.command("x")` / `.outgoing` / `.incoming` / `.group`，可 `& \| ~` 组合 |
| 注册消息 | `@ctx.on_message(filter, group=0, target="auto")` |
| 注册回调 | `@ctx.on_callback(filter, group=0, target="auto")` |
| Bot 发送 | `await ctx.bot.send(chat_id, text)` / `ctx.bot.send_photo(...)` |
| 用户发送 | `await ctx.user.send(chat_id, text)` |
| 全部用户账号 | `ctx.user_apps`（多账号场景） |
| 配置 | `ctx.config["字段名"]`（每次读取都是前端最新值） |
| 键值存储 | `ctx.kv.get/set/delete/keys`（每插件独立 sqlite，互不干扰） |
| 日志 | `ctx.log.info/debug/warning/error` |
| 定时任务 | `ctx.schedule(fn, "interval", seconds=60)` / `(fn, "cron", hour=3, id="名称")` |
| 清理回调 | `ctx.add_cleanup(fn)` |

`target`：`"user"` / `"bot"` / `"both"` / `"auto"`（按插件 scope 自动选择）。

### 4. config_schema（插件配置）

插件的**所有业务参数都写在这里**，前端「配置」按钮据此自动生成设置界面，值用 `ctx.config[...]` 读：

```python
"config_schema": {
    "enable_x": {"type": "boolean", "default": True, "label": "启用X", "section": "功能开关"},
    "keyword":  {"type": "string",  "default": "",   "label": "触发词", "section": "参数",
                 "help": "字段下方说明", "show_if": {"enable_x": True}},
    "secret":   {"type": "password", "default": "",  "label": "密钥",  "section": "参数"},
    "volume":   {"type": "slider",  "default": 5, "min": 0, "max": 10, "step": 1, "section": "参数"},
    "mode":     {"type": "select",  "default": "a", "options": ["a","b"], "section": "参数"},
}
```

字段属性：
- `type`：`string` / `password` / `number` / `boolean` / `select` / `multiselect` / `slider` / `text`(多行)
- `default`：默认值（必填；multiselect 用列表，slider/number 用数字）
- `label` 显示名 · `help` 说明 · `options`（select/multiselect 用）· `min`/`max`/`step`（number/slider 用）
- `section`：分区标题（同 section 归一组卡片）
- `show_if`：条件联动，如 `{"enable_x": True}` 仅当该字段为真才显示本字段

> 平台没有「动态 N 条规则」控件。需要多规则/多任务时，用多行 `text` 字段装一个 **JSON 数组**，插件运行时解析（参考本仓库 `keyword_auto_reply` / `custom_auto_reply`）。

### 5. 必须遵守的规矩

1. **一个文件一个插件**，文件名 = `id`，全局唯一。
2. **不要 `import pyrogram` / `config` / 内核模块**，一切走 `ctx`。
3. **不要用 `@Client.on_message`**，用 `@ctx.on_message`（否则关不掉，破坏热插拔）。
4. **不要 `print`**，用 `ctx.log`。
5. **插件之间不要互相 import**。共用逻辑写成 `_` 开头的辅助文件，或下沉到平台。
6. **业务配置只进 `config_schema`**，禁止读写平台配置；持久化用 `ctx.kv`（关系型存储表名须带 `<plugin_id>_` 前缀）。
7. 自管理资源（后台 task、连接等）必须在 `teardown` 或 `ctx.add_cleanup` 里释放；`ctx.on_message` / `ctx.schedule` 注册的由平台自动清理。

---

## manifest.json（插件市场清单）

仓库根的 [manifest.json](manifest.json) 是插件市场清单，key = 插件 id。平台据此渲染市场，并靠 `version` 判断更新：

```json
{
  "my_feature": {
    "name": "我的功能",
    "version": "1.0.0",
    "author": "你",
    "description": "...",
    "path": "plugins/my_feature.py"
  }
}
```

- `path`：单文件以 `.py` 结尾，文件夹以 `/` 结尾。
- **改了插件代码 → 必须同步抬高 `version`**，否则自动同步端拉不到更新。
- 自动同步**只下载、不自动启用**（安全铁律），用户需在平台手动开启。

---

## 当前插件

| 插件 | id | 触发 | scope | 说明 |
|------|----|------|-------|------|
| 查ID | `id` | `/id` `.id`（可回复消息） | user | 查群组ID / 用户ID / 用户名 |
| 小姐姐视频 | `xjj` | `/xjj` `.xjj` | user | 拉取随机短视频 |
| 关键词自动回复 | `keyword_auto_reply` | 监听群消息 | user | 多规则、匹配方式、冷却、限群、自动删除、模板变量 |
| 定时自动回复 | `custom_auto_reply` | cron 定时 | user | 多任务、活动日期范围、多账号、结果通知 |

---

## 在平台中使用

平台「从 GitHub 导入」填以下任一即可：

- `AWdress/AWBotNest-Plugins`
- `https://github.com/AWdress/AWBotNest-Plugins`

或在平台「系统设置 → 插件仓库」把本仓库配为自动同步源，平台按间隔自动拉取新增/更新的插件（同样只下载不启用）。

---

完整平台规范见平台仓库的 `SPEC.md` 与 `PLUGIN_GUIDE.md`。
