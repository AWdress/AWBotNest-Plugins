# AWBotNest-Plugins

> AWBotNest 官方插件仓库 —— 平台**内置**此仓库，它会自动出现在每个平台的「插件商店」里。这里的每个插件都遵循平台「**单文件 / 文件夹插件**」规范。

- 平台仓库：[AWdress/AWBotNest](https://github.com/AWdress/AWBotNest)

---

## 一分钟上手

1. 复制平台的 `plugins/_TEMPLATE.py`（或本仓库任一插件），改名成你的功能名，如 `my_feature.py`。文件名就是插件 ID。
2. 改顶部的 `__plugin__` 字典（`id` 必须等于文件名）。
3. 在 `setup(ctx)` 里写逻辑，处理器一律用 `ctx.on_message` / `ctx.on_callback` 注册。
4. 把插件放进平台 `plugins/`，或上传、或从本仓库导入。
5. 在平台插件列表打开开关 → 立即生效；关掉 → 立即卸载。**不用重启，不用改其它文件。**

---

## 开发者 Skill

仓库内附带一个可复用的 AWBotNest 插件开发 skill，方便在 Hermes 里复用这套规范：

- `skills/software-development/awbotnest-plugin-development/SKILL.md`
- 最小模板：`skills/software-development/awbotnest-plugin-development/references/minimal-plugin-template.py`

如果对方也在用 Hermes，可将该目录同步到自己的 `~/.hermes/skills/software-development/awbotnest-plugin-development/`，或直接作为仓库内 skill 参考使用。

---

## 插件规范

### 1. 三段式契约

每个插件必须有这三段（`teardown` 可选）：

```python
# ① 元数据：平台靠它在前端显示。必须是纯字面量字典（平台用 AST 静态解析）
__plugin__ = {
    "name": "我的功能",        # 必填：前端显示名
    "id": "my_feature",        # 必填：必须 = 文件名/目录名（去 .py）
    "version": "1.0.0",        # 必填：插件商店靠它判断有没有更新
    "scope": "user",           # 必填：user(用户账号) | bot(机器人) | both
    "author": "你",            # 可选
    "description": "干啥的",    # 可选
    "changelog": "v1.0.0 初始版本\n- 实现基础功能",  # 必填：详情页展示的版本更新说明
    "icon": "",                # 可选：图标 URL，前端卡片用；留空回退平台 logo
    "default_enabled": False,  # 可选：放入本地 plugins/ 时是否默认启用
    "webhook": False,          # 可选：声明 True 才能用 @ctx.on_webhook 接收外部回调
    "config_schema": { ... },  # 可选：前端自动生成配置表单
    "requirements": [          # 可选：第三方依赖（PEP 508），平台启用时自动代装
        "httpx>=0.27",
    ],
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

`changelog` 是发布必填项。新插件写初始版本内容；以后每次更新都要在保留有价值历史的同时，把当前版本的新增、修复和破坏性变化写在最前面，并与 `version`、`manifest.json` 同步更新。

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
| 注册编辑消息 | `@ctx.on_edited_message(filter, group=0, target="auto")`（仅消息被编辑时触发，用法同 on_message；适合「先发再编辑送达结果」的 bot） |
| 注册回调 | `@ctx.on_callback(filter, group=0, target="auto")` |
| 中断传播 | `raise ctx.StopPropagation`（在 handler 内主动阻止后续插件再处理这条消息，谨慎用） |
| Bot 发送 | `await ctx.bot.send(chat_id, text)` / `ctx.bot.send_photo(...)`（`ctx.bot` = 平台为本插件分配的 Bot，未分配=默认 Bot） |
| 指定 Bot | `ctx.get_bot(bot_id)`（高级：取某个 Bot 的发送代理，不传/不存在回退默认 Bot） |
| 用户发送 | `await ctx.user.send(chat_id, text)` |
| 全部用户账号 | `ctx.user_apps`（多账号场景；未连接时发送代理抛 `RuntimeError`，可先判 `ctx.bot/user.connected`） |
| 通知平台主人 | `await ctx.notify(text, level=, category=, account=)`（平台自动加插件名/级别图标/账号名并投递；别自己拼格式或用 `ctx.bot.send`） |
| 主人 ID | `ctx.owner_id`（平台主人 Telegram 数字 ID，无主账号为 0） |
| 配置 | `ctx.config["字段名"]`（每次读取都是前端最新值） |
| 写回配置 | `ctx.update_config({"key": val})`（局部合并写回本插件配置，**不触发重载**；用于持久化运行状态或把状态回填到 `info` 字段供前端展示） |
| 下载媒体 | `await ctx.download(message, subdir=None)`（下载消息媒体到本插件目录，返回落盘 `Path`；无媒体抛 `ValueError`） |
| 浏览器自动化 | `await ctx.browser.page_source(url, ...)`（渲染后 HTML）/ `await ctx.browser.run(url, action, ...)`（传同步 `action(page)` 执行并返回结果；引擎优先 CloakBrowser，回退 Playwright Chromium；首次调用下载内核到 `data/browser_cache`） |
| 动作按钮 | `@ctx.action("名")`（注册动作按钮处理器，`config_schema` 里 `type:action` 的按钮点击触发；返回 dict(含 `ok`/`message`) / str / None） |
| Vue后端接口 | `@ctx.on_api("/path", methods=[...])`（Vue 模式后端接口，前端 `host.callApi` 调；管理员登录态鉴权，收 `WebhookRequest`，返回 dict/str/None） |
| 键值存储 | `ctx.kv.get/set/delete/keys`（每插件独立 sqlite，互不干扰） |
| 文件目录 | `ctx.data_dir`（`Path`，每插件独享可写目录，存图片/素材等实际文件） |
| 日志 | `ctx.log.info/debug/warning/error` |
| 定时任务 | `ctx.schedule(fn, "interval", seconds=60)` / `(fn, "cron", hour=3, id="名称")` |
| Webhook | `@ctx.on_webhook`（需 `__plugin__` 声明 `"webhook": True`；入站 `…/api/v1/plugin/<id>/webhook?apikey=<密钥>`，apikey 用平台统一的 Webhook 密钥，处理器收 `WebhookRequest`，返回 dict/str/None） |
| 清理回调 | `ctx.add_cleanup(fn)` |

`target`：`"user"` / `"bot"` / `"both"` / `"auto"`（按插件 scope 自动选择）。

**group 隔离（不会互相"吃消息"）**：Pyrogram 在同一 group 内只跑第一个匹配的 handler。平台给**每个插件分配独立的 group 区间**，所以不同插件即使都监听同类消息也各自都能收到。你写的 `group=` 是「**本插件内部**的相对优先级」（数值越小越先），平台自动平移到你的区间——不用关心别的插件用了什么 group。想"我处理了就别让后面的插件再处理"，在 handler 里 `raise ctx.StopPropagation`。

**多账号下的账号范围**：`scope=user`/`both` 的插件默认挂到**所有**已连接用户账号；用户可在插件卡片「账号」按钮里选择只应用到部分账号（空=全部），改动后自动重挂。

**多 Bot 下的 Bot 选择（对插件透明）**：平台可配置多个 Bot，并在「系统设置 → 通知」为每个插件指定用哪个 Bot（默认=默认 Bot）。这对插件是**透明**的——`ctx.bot`、`ctx.notify`、`scope=bot`/`both` 的 handler 都会自动走平台为本插件分配的 Bot。插件作者**不选择**也不感知 Bot，照常写 `ctx.bot.send(...)` / `ctx.notify(...)` 即可。

### 4. config_schema（插件配置）

普通插件的业务参数优先写在这里，前端「配置」按钮据此自动生成设置界面，值用 `ctx.config[...]` 读。平台原生表单已经支持分区、条件显示、动态列表、会话选择器、动作按钮和响应式布局；**能用 `config_schema` 清楚表达的配置，不要为了样式改成 Vue**。

> **布局默认由平台自动排布，也支持按需精调**：配置弹窗使用 12 列栅格（桌面约 1000px，窄屏自动全屏）。未写 `cols` 时，短字段默认占 6 列、大字段默认占 12 列；需要更整齐的组合时可用 `cols` 指定 1–12 列，用 `order` 调整同一分区内的顺序。窄屏（≤768px）统一回落单列。

```python
"config_schema": {
    "enable_x": {"type": "boolean", "default": True, "label": "启用X", "section": "功能开关",
                 "cols": 4, "order": 1},
    "keyword":  {"type": "string",  "default": "",   "label": "触发词", "section": "参数",
                 "help": "字段下方说明", "show_if": {"enable_x": True}},
    "secret":   {"type": "password", "default": "",  "label": "密钥",  "section": "参数", "required": True},
    "volume":   {"type": "slider",  "default": 5, "min": 0, "max": 10, "step": 1, "section": "参数"},
    "mode":     {"type": "select",  "default": "a", "options": ["a","b"], "section": "参数"},
    # 可增删行的规则列表，取值为 list-of-dict
    "rules":    {"type": "list", "default": [], "label": "规则", "item_label": "规则", "section": "规则",
                 "fields": {
                     "name":  {"type": "string",  "label": "名称"},
                     "types": {"type": "multiselect", "label": "类型", "options": ["a","b"], "default": []},
                     "on":    {"type": "boolean", "label": "启用", "default": True},
                 }},
    # 会话选择器：从账号的群/频道/私聊里挑，直接存会话 id
    "target":   {"type": "chat", "default": 0, "label": "转发到", "multi": False,
                 "chat_types": ["group", "channel"], "section": "会话"},
    "tip":      {"type": "info", "label": "说明", "text": "先填密钥再启用", "section": "会话"},
    "test":     {"type": "action", "label": "测试连接", "action": "test", "section": "会话"},
}
```

#### 字段类型速查

| 类型 | 适用场景 | 示例 |
|------|---------|-----|
| `boolean` | 开关功能 | 启用自动回复、记录日志 |
| `string` | 短文本输入 | 关键词、API地址、用户名 |
| `password` | 敏感信息 | API密钥、Token、密码 |
| `number` | 精确数值 | 端口号、重试次数、ID |
| **`slider`** | **有范围的数值调节** | **延迟秒数、音量、透明度、百分比** |
| `select` | 单选下拉 | 模式选择（编辑/回复）、日志级别 |
| `multiselect` | 多选标签 | 通知类型、过滤标签、启用的功能 |
| `text` | 多行长文本 | 消息模板、脚本、JSON配置 |
| `list` | 可增删的列表 | 规则列表、白名单、定时任务 |
| `chat` | 会话选择器 | 转发到的群组、通知频道 |
| `info` | 只读说明 | 使用提示、当前状态显示 |
| `action` | 操作按钮 | 测试连接、立即执行、清空缓存 |

> **提示**：数值范围调节优先用 `slider` 而非 `number`——用户体验更直观，尤其是百分比、延迟、等级这类有明确上下限的参数。

#### 字段属性

字段属性：
- `type`：`string` / `password` / `number` / `boolean` / `select` / `multiselect` / `slider` / `text`(多行) / `list` / `chat` / `action` / `info`
- `default`：默认值（必填；`multiselect`/`list` 用列表，`slider`/`number` 用数字）
- `label` 显示名 · `help` 说明 · `options`（select/multiselect 用）· `min`/`max`/`step`（number/slider 用）
- `required`：`True` 时保存前校验非空，空则前端拦下不保存（`info`/`action` 不校验）
- `section`：分区标题（同 section 归一组卡片）
- `cols`：字段占用的栅格列数（1–12）；12=整行、6=半行、4=三等分。窄屏时自动失效并占满整行
- `order`：同一 `section` 内的排序权重，数字越小越靠前；未指定的排在后面
- `show_if`：条件联动，如 `{"enable_x": True}` 仅当该字段为真才显示本字段
- `list`：可增删行，`fields` 定义每行子字段（`{子键: 子 spec}`，子字段用基础类型），`item_label` 定每行标题前缀（如「规则 1」）。取值 `[{子键: 值}, ...]`，`ctx.config["rules"]` 直接遍历。行内暂不支持 `show_if`，别再嵌套 `list`
- `chat`：会话选择器，从账号的群/频道/私聊里挑，存会话 id；`multi=True` 存 id 数组；`chat_types` 过滤类型（`private`/`bot`/`group`/`channel`）；`session` 指定枚举账号。`ctx.config["target"]` 直接当 chat_id 用，没连账号可手填兜底
- `action`：动作按钮，`action` 名须与插件里 `ctx.action("名字")` 注册的一致；`danger=True` 点击前弹确认
- `info`：只读展示，`text` 为固定文字；不填 `text` 则显示该键当前值（可用 `ctx.update_config` 写回显示动态状态）

> 多条规则/不定条数内容，优先用 `list` 字段（可增删行、每行一组表单，用户一看就懂）；来源/目标这类会话选 `chat` 选择器，免手填 id。

#### 推荐排版规范

配置弹窗采用 **12 列栅格系统**（桌面约 1000px 宽，窄屏自动全屏）。

**自动布局（默认）**：
- 未指定 `cols` 时，大字段（`text`/`list`/`multiselect`/`chat`）自动占 12 列（整行）
- 短字段（`string`/`password`/`number`/`boolean`/`select`/`slider`）自动占 6 列（半行，两两并排）

**推荐排版**：
```python
"config_schema": {
    # ✅ 推荐：所有开关并排在最上面（用 cols 控制），配合 order 确保优先显示
    "enable_plugin": {"type": "boolean", "label": "启用插件", "cols": 3, "order": 1, "section": "功能开关"},
    "auto_delete":   {"type": "boolean", "label": "自动删除", "cols": 3, "order": 2, "section": "功能开关"},
    "send_notify":   {"type": "boolean", "label": "发送通知", "cols": 3, "order": 3, "section": "功能开关"},
    "debug_mode":    {"type": "boolean", "label": "调试模式", "cols": 3, "order": 4, "section": "功能开关"},
    
    # 其他参数字段跟在后面（order 从 10 开始，给开关预留空间）
    "api_key":       {"type": "password", "label": "API密钥", "order": 10, "section": "基本配置"},
    "interval":      {"type": "slider", "label": "间隔(分钟)", "min": 1, "max": 60, "default": 10, "order": 11, "section": "基本配置"},
}
```

**常用布局组合**：
- `6 + 6`：两个字段并排（半行）
- `4 + 4 + 4`：三个字段并排（三等分）
- `8 + 4`：主要字段 + 辅助字段
- `3 + 3 + 3 + 3`：四个开关并排

**移动端适配**：窄屏（≤768px）自动回退单列布局，`cols` 设置失效，所有字段占满宽。

排版建议：先用 `section` 分成少量语义明确的卡片，再用 `order` 固定阅读顺序；同一行优先使用 `6+6`、`4+4+4` 或 `8+4`，避免为了填满一行把长文本、列表和会话选择器压窄。

### 4.5 Vue 模式（自带界面，进阶）

`config_schema` 自动表单覆盖绝大多数插件。只有界面本身属于功能的一部分时，才使用 **Vue 模式**（仅**文件夹插件**）：`__plugin__` 声明 `"render_mode": "vue"`（不再需要 `config_schema`），目录带一个 `frontend/` 模块联邦工程（暴露 `./Config`），发布前 `npm run build` 并**一起提交 `frontend/dist/`**（平台加载构建产物）。

选择标准：

| 场景 | 应选模式 |
|------|----------|
| 开关、文本、数字、下拉、多选、滑块、会话选择、条件字段 | `config_schema` |
| 可增删的规则或账号列表 | 优先 `config_schema` 的 `list` |
| 测试连接、清理缓存、立即执行等单个动作 | 优先 `config_schema` 的 `action` |
| 图表、排行榜、运行历史、活动监控、批量管理、需要多次 API 交互的操作台 | Vue |
| 只是希望配置页“更好看” | 仍用 `config_schema` |

> 不要求、也不建议把已有插件批量迁成 Vue。简单插件保留原生表单，代码更少、升级成本更低，也能自动获得平台后续的表单能力和移动端适配。已有 Vue 插件只有在确实提供管理面板、记录列表或复杂交互时才保留 Vue。

- 平台注入 `props { pluginId, host }`；`host.getConfig()/saveConfig(v)` 读写配置（仍存平台、插件里 `ctx.config` 可读）、`host.callApi(path,{method,body})` 调后端、`host.toast`。
- 后端接口用 `@ctx.on_api("/path", methods=[...])` 注册，前端 `host.callApi` 调（管理员登录态鉴权）。
- **画布约 1000px、窄屏（≤768px）自动全屏——请用响应式布局（百分比 / 栅格 / 容器查询），不要写死过窄或过宽的固定尺寸，否则窄屏溢出**。参考本仓库 `auto_subscribe`（容器查询 + master-detail）。
- 完整说明见平台 `PLUGIN_GUIDE.md` 的「Vue 模式」与模板 `plugins/_TEMPLATE_VUE/`。

### 5. 第三方依赖（requirements）

插件用到平台基础环境之外的第三方库时，在 `__plugin__["requirements"]` 里**声明**，平台会在**启用插件时**自动 `pip install`。

```python
"requirements": ["rapidocr>=2", "httpx>=0.27"],
```

- **插件自己绝不调 pip**，只声明，安装时机和方式交平台（`yingchao_redpacket` 的 OCR 依赖即用此方式）。
- 写 **PEP 508 字符串**，用宽松范围（`>=`）而非钉死（`==`），减少和平台/其它插件撞车。
- 平台是**单进程热插拔**，同一个包只能有一个版本生效。装之前先做冲突检测：已满足→跳过；缺失→装；**已装了不兼容版本→拒绝启用并报原因**，绝不强行覆盖。
- 注意目标平台的 **Python 版本**：选依赖时确认它支持平台所用版本（平台当前跑 Python 3.13），否则会因无兼容版本装不上而启用失败。
- 缺失依赖是否致命由插件自己决定：若设计成「缺了就降级」，import 处要容错（参考 `yingchao_redpacket/_ocr.py`：OCR 库缺失时降级，不影响基础功能）。
- **出站请求自动走平台代理**：系统设置里启用代理后，平台会导出 `HTTP(S)_PROXY`/`ALL_PROXY` 环境变量，`httpx`/`requests`/`aiohttp`（默认 `trust_env=True`）自动走代理，插件无需手动配置（`localhost`/`127.0.0.1` 已排除）；若手动关了 `trust_env`，请自行读取这些环境变量。

### 5.5 Webhook（接收外部回调）

需要接收外部服务回调（如媒体服务器事件推送）的插件，在 `__plugin__` 声明 `"webhook": True`，用 `@ctx.on_webhook` 注册**一个**处理器：

```python
__plugin__ = { ..., "webhook": True }

async def setup(ctx):
    @ctx.on_webhook
    async def on_hook(req):          # req 是 WebhookRequest
        data = req.json or {}        # 解析出的 JSON（非 JSON 为 None）；另有 req.method/query/headers/text/body
        await ctx.notify(f"收到事件：{data}", category="Webhook")
        return {"ok": True}          # dict→JSON / str→文本 / None→{"ok": true}
```

- 声明后，在插件「配置」弹窗的 Webhook 区即可看到本插件入站地址（每个插件路径不同）：
  `http(s)://<平台地址>/api/v1/plugin/<插件id>/webhook?apikey=<密钥>`
- `apikey` 用**平台统一的 Webhook 密钥**：在「系统设置 → 通知 → 平台 Webhook」点「随机」生成**一次**，平台 webhook 与所有插件 webhook **共用同一个密钥**，不为每个插件单独生成。
- 处理器收到的 `req` 是 `WebhookRequest`：`req.method` / `req.query`（已剔除 apikey）/ `req.headers`（键小写）/ `req.json`（非 JSON 为 None）/ `req.text` / `req.body`（原始 bytes）。返回 dict→JSON、str→文本、None→`{"ok": true}`。
- 仅当插件**已启用 + 已注册处理器 + 平台已生成密钥**时 webhook 才响应；一个插件一个处理器，停用/重载自动失效。
- 只想把外部内容推给管理员而不写插件时，用**平台级 webhook**：系统设置→通知里生成密钥，POST 到 `…/api/v1/webhook?apikey=<密钥>`（JSON 里带 `text`/`title`/`category` 或整段文本即作为通知）。

### 6. 必须遵守的规矩

1. **一个文件一个插件**，文件名 = `id`，全局唯一。
2. **不要 `import pyrogram` / `config` / 内核模块**，一切走 `ctx`。
3. **不要用 `@Client.on_message`**，用 `@ctx.on_message`（否则关不掉，破坏热插拔）。
4. **不要 `print`**，用 `ctx.log`。
5. **插件之间不要互相 import**。共用逻辑写成 `_` 开头的辅助文件，或下沉到平台。
6. **业务配置由平台托管**：普通模式声明 `config_schema`，Vue 模式通过 `host.getConfig()/saveConfig()` 读写；后端统一从 `ctx.config` 读取。禁止直接读写平台配置文件；运行数据用 `ctx.kv`（关系型存储表名须带 `<plugin_id>_` 前缀）。
7. 自管理资源（后台 task、连接等）必须在 `teardown` 或 `ctx.add_cleanup` 里释放；`ctx.on_message` / `ctx.on_edited_message` / `ctx.on_callback` / `ctx.schedule` 注册的由平台自动清理。

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
    "icon": "https://.../i.png",
    "path": "plugins/my_feature.py"
  }
}
```

- `path`：单文件以 `.py` 结尾，文件夹以 `/` 结尾。
- `icon`（可选）：市场卡片图标 URL，留空回退平台 logo；与插件 `__plugin__["icon"]`（已安装卡片用）保持一致即可。
- **改了插件代码 → 必须同步抬高 `version`**，否则插件商店识别不到更新、已安装的平台收不到推送。抬高版本推上来后，平台轮询会自动下载覆盖；**正在运行的插件实例会自动热重载使新代码生效**（未运行的只更新文件、不自动启用）。
- 商店里的插件**只在用户点「安装」时落盘，且绝不自动启用**（安全铁律），需用户在平台手动开启。

---

## 当前插件

### 工具 / 常用

| 插件 | id | 触发 | scope | 说明 |
|------|----|------|-------|------|
| 查ID | `id` | `/id` `.id`（可回复消息） | user | 查群组ID / 用户ID / 用户名 |
| 小姐姐视频 | `xjj` | `/xjj` `.xjj` | user | 拉取随机短视频 |
| 删除自己消息 | `self_delete` | `/dme 数字` `.dme 数字` | user | 删除当前会话里自己最近发的若干条消息 |
| P站图片 | `zpr` | `/zpr` `/zp`（及 `.` 前缀） | user | 二次元图片，`/zp` 附带原图文件 |
| 举牌 | `jupai` | `/jupai 文字`（可回复消息） | user | 把文字转成举牌人图片 |
| 转发复读 | `zf` | `/zf [次数]`（回复消息） | user | 把被回复消息在当前会话转发/复读若干次 |
| 取消息结构 | `getmsg` | `/getmsg`（回复消息） | user | 导出该消息原始结构为 txt 发到收藏夹，调试用 |
| 插件开发探针 | `probe` | `.probe`（可回复消息）/ `.cbprobe on\|off` | both | 采集消息/会话/按钮/回调的完整信息，附带访问路径速查，开发插件用 |
| AI 助手 | `ai` | 私聊/群@ / `/ai`（回复消息） | user | AI 人形对话（带记忆），`/ai` 解释或解答（支持图片） |

### 自动化 / 定时

| 插件 | id | 触发 | scope | 说明 |
|------|----|------|-------|------|
| 关键词自动回复 | `keyword_auto_reply` | 监听群消息 | user | 一行一条「关键词=回复」，支持冷却、限群、自动删除、模板变量 |
| 定时自动回复 | `custom_auto_reply` | 定时 | user | 每个会话单独设时间和内容（定点 / 间隔 / cron） |
| 自动报时昵称 | `auto_changename` | 定时 | user | 定时把昵称改成当前时间，支持自定义模板 |
| 自动换头像 | `auto_avatar` | 定时 / `.avataradd` 等 | user | 定时随机换头像，回复图片 `.avataradd` 入池，`.avatarlist/.avatarclear` 管理 |

### PT 站 / 媒体

| 插件 | id | 触发 | scope | 说明 |
|------|----|------|-------|------|
| 115列表转发 | `trans115search` | 监听来源会话 | user | 把机器人发的「列表」消息自动转发到目标会话 |
| 影巢115媒体监控 | `movie_monitor_115` | 监听频道 | user | 监控 115 分享，TMDB 识别 + 查 Emby，缺失转发 CMS 入库 |
| U2送糖 | `u2_dmhy` | `/u2` `/u2s`（带 cookie） | user | 给 u2.dmhy.org 用户赠送 UCoin，单人/批量，自带冷却 |
| 多站点转账 | `transfer` | 监听多站点转账bot | user | 记录转入/转出并生成排行榜，站点群组/bot 内置 |
| 朱雀 | `zhuque_lottery` | 命令 / 定时 | user | 朱雀PT站自动化：查询、大劫、红包雨、转盘、转账、投注、魔法卡、倍投 |
| AWEmbyPush | `awembypush` | Emby/Jellyfin Webhook | bot | 监听入库 Webhook，TMDB 增强 + 剧集合并 + 去重后，推送 Telegram/企业微信/Bark 通知（自 MoviePilot 移植） |
| 自动订阅助手 | `auto_subscribe` | 定时 / Vue 配置界面 | user | 聚合豆瓣/Mikan新番/奈飞/猫眼榜单，按全局或每源过滤后自动订阅到 NextFind；自带 Vue 管理界面（自 MoviePilot 移植） |

### 群游戏（自建）

| 插件 | id | 触发 | scope | 说明 |
|------|----|------|-------|------|
| 趣味答题 | `quiz_game` | 群发「开启答题」 | user | 出题抢答，答对自动发魔力奖励，支持连胜加成（AI/天行出题） |
| 数字炸弹 | `bomb_game` | 群内开启后参与 | both | 回复+金额组奖池，轮流猜数字，爆炸者出局，中奖按比例分池 |
| 发红包 | `red_packet_send` | 群里发包 | user | 用你的账号发拼手气红包，群友回复参与，自动分配发放魔力 |

### 抽奖 / 抢红包（自动参与）

| 插件 | id | 触发 | scope | 说明 |
|------|----|------|-------|------|
| HDHive抽奖 | `hdhive_lottery` | 监听抽奖消息 | user | 随机等待后发口令参与，开奖检测中奖并通知 |
| 小菜抽奖 | `auto_lottery` | 监听抽奖消息 | user | 时间段/奖品关键词匹配 → 陷阱检测 → 随机等待参与 → 中奖感谢/发奖 |
| 通用抽奖 | `common_lottery` | 监听抽奖消息 | user | 自动参与 @Lottery8Bot 等：解析口令、按需自动加群、随机等待发口令 |
| 拼手气红包(HDSKY) | `hdsky_redpacket` | 监听天空群红包 | user | 自动点「抢红包」按钮，可选 `/red` 占位发言应对「限最近发言人」 |
| 癫影积分红包 | `dyp_redpacket` | 监听癫影助手红包 | user | 混合红包（暗含 N 个雷包）：逐个点未抢数字按钮，落地一格即停——抢到分/踩雷都算用掉唯一机会停手，「手慢了/已被抢」才试下一格。发包bot/群内置 |
| 影巢口令红包（测试） | `yingchao_redpacket` | 监听指定发包人 | user | OCR 识别图片口令或复制他人口令参与，含陷阱防护 |
| 自动抢红包 | `red_packet_grab` | 监听验证码口令红包 / Vue 配置界面 | user | OCR 识别或复制已确认的正确口令兜底；可限制发包人/群组，含抢包记录 |

---

## 在平台中使用

本仓库是平台**内置的官方仓库**，无需手动添加：

1. 打开平台「插件管理 → 插件商店」，本仓库的插件会自动列在其中。
2. 找到想要的插件点「安装」（落盘到本地，**不会自动启用**）。
3. 到「我的插件」打开开关启用。需要的话点「配置」调参数。

平台会定时刷新商店列表，并对**已安装**插件按 `manifest.json` 的版本号推送更新：下载覆盖后，**正在运行的插件会自动热重载生效**，无需手动重载（未运行的只更新文件、不自动启用）。新插件不会自动安装，始终由你在商店里手动选择。

---

完整平台规范见平台仓库的 `SPEC.md` 与 `PLUGIN_GUIDE.md`。
