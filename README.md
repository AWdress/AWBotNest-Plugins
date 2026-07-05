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
| 键值存储 | `ctx.kv.get/set/delete/keys`（每插件独立 sqlite，互不干扰） |
| 文件目录 | `ctx.data_dir`（`Path`，每插件独享可写目录，存图片/素材等实际文件） |
| 日志 | `ctx.log.info/debug/warning/error` |
| 定时任务 | `ctx.schedule(fn, "interval", seconds=60)` / `(fn, "cron", hour=3, id="名称")` |
| Webhook | `@ctx.on_webhook`（需 `__plugin__` 声明 `"webhook": True`；入站 `…/api/v1/plugin/<id>/webhook?apikey=<密钥>`，处理器收 `WebhookRequest`，返回 dict/str/None） |
| 清理回调 | `ctx.add_cleanup(fn)` |

`target`：`"user"` / `"bot"` / `"both"` / `"auto"`（按插件 scope 自动选择）。

**group 隔离（不会互相"吃消息"）**：Pyrogram 在同一 group 内只跑第一个匹配的 handler。平台给**每个插件分配独立的 group 区间**，所以不同插件即使都监听同类消息也各自都能收到。你写的 `group=` 是「**本插件内部**的相对优先级」（数值越小越先），平台自动平移到你的区间——不用关心别的插件用了什么 group。想"我处理了就别让后面的插件再处理"，在 handler 里 `raise ctx.StopPropagation`。

**多账号下的账号范围**：`scope=user`/`both` 的插件默认挂到**所有**已连接用户账号；用户可在插件卡片「账号」按钮里选择只应用到部分账号（空=全部），改动后自动重挂。

**多 Bot 下的 Bot 选择（对插件透明）**：平台可配置多个 Bot，并在「系统设置 → 通知」为每个插件指定用哪个 Bot（默认=默认 Bot）。这对插件是**透明**的——`ctx.bot`、`ctx.notify`、`scope=bot`/`both` 的 handler 都会自动走平台为本插件分配的 Bot。插件作者**不选择**也不感知 Bot，照常写 `ctx.bot.send(...)` / `ctx.notify(...)` 即可。

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

> 需要多条规则/多项内容时，优先用普通字段组合（开关 + `select` + `show_if` 联动）把界面拆清楚；确实需要不定条数时，可用多行 `text` 字段让用户一行一条填写，插件内解析（参考 `keyword_auto_reply` 的「关键词=回复」写法）。

### 5. 第三方依赖（requirements）

插件用到平台基础环境之外的第三方库时，在 `__plugin__["requirements"]` 里**声明**，平台会在**启用插件时**自动 `pip install`。

```python
"requirements": ["rapidocr>=2", "httpx>=0.27"],
```

- **插件自己绝不调 pip**，只声明，安装时机和方式交平台（`dyp_redpacket` 的 OCR 依赖即用此方式）。
- 写 **PEP 508 字符串**，用宽松范围（`>=`）而非钉死（`==`），减少和平台/其它插件撞车。
- 平台是**单进程热插拔**，同一个包只能有一个版本生效。装之前先做冲突检测：已满足→跳过；缺失→装；**已装了不兼容版本→拒绝启用并报原因**，绝不强行覆盖。
- 注意目标平台的 **Python 版本**：选依赖时确认它支持平台所用版本（平台当前跑 Python 3.13），否则会因无兼容版本装不上而启用失败。
- 缺失依赖是否致命由插件自己决定：若设计成「缺了就降级」，import 处要容错（参考 `dyp_redpacket/_ocr.py`：OCR 库缺失时降级为纯文本判定，不影响基础功能）。
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

- 声明后，在插件「配置」弹窗的 Webhook 区点「随机」生成**每插件独立密钥**，即得入站地址：
  `http(s)://<平台地址>/api/v1/plugin/<插件id>/webhook?apikey=<密钥>`
- 仅当插件**已启用 + 已注册处理器 + 已生成密钥**时 webhook 才响应；停用/重载自动失效，密钥随插件删除一并清除。
- 只想把外部内容推给主人而不写插件时，用**平台级 webhook**：系统设置→通知里生成密钥，POST 到 `…/api/v1/webhook?apikey=<密钥>`。

### 6. 必须遵守的规矩

1. **一个文件一个插件**，文件名 = `id`，全局唯一。
2. **不要 `import pyrogram` / `config` / 内核模块**，一切走 `ctx`。
3. **不要用 `@Client.on_message`**，用 `@ctx.on_message`（否则关不掉，破坏热插拔）。
4. **不要 `print`**，用 `ctx.log`。
5. **插件之间不要互相 import**。共用逻辑写成 `_` 开头的辅助文件，或下沉到平台。
6. **业务配置只进 `config_schema`**，禁止读写平台配置；持久化用 `ctx.kv`（关系型存储表名须带 `<plugin_id>_` 前缀）。
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
| 癫影积分红包 | `dyp_redpacket` | 监听癫影助手红包 | user | 逐个点未抢数字按钮（已抢跳过），抢到一格即停；可选雷包检测（文本判定为主、OCR 识别配图兜底防伪装，识别不出保守跳过），发包bot/群内置 |
| 影巢口令红包（测试） | `yingchao_redpacket` | 监听指定发包人 | user | OCR 识别图片口令或复制他人口令参与，含陷阱防护 |

---

## 在平台中使用

本仓库是平台**内置的官方仓库**，无需手动添加：

1. 打开平台「插件管理 → 插件商店」，本仓库的插件会自动列在其中。
2. 找到想要的插件点「安装」（落盘到本地，**不会自动启用**）。
3. 到「我的插件」打开开关启用。需要的话点「配置」调参数。

平台会定时刷新商店列表，并对**已安装**插件按 `manifest.json` 的版本号推送更新：下载覆盖后，**正在运行的插件会自动热重载生效**，无需手动重载（未运行的只更新文件、不自动启用）。新插件不会自动安装，始终由你在商店里手动选择。

---

完整平台规范见平台仓库的 `SPEC.md` 与 `PLUGIN_GUIDE.md`。
