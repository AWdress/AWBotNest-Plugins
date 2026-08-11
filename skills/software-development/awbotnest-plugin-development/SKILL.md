---
name: awbotnest-plugin-development
description: Create, modify, review, validate, or publish AWBotNest plugins and AWBotNest-Plugins marketplace entries. Use for plugin metadata, ctx APIs, config_schema, Vue plugin config, dependencies, webhook handlers, manifest sync, and hot-reload-safe implementation.
---

# AWBotNest Plugin Development

Use the plugin guide and plugin template as the source of truth for AWBotNest plugin work. Do not infer plugin rules from platform internals when the plugin docs already define them.

## Source of truth

Read in this order before changing plugin code:

1. `/root/AWBotNest/docs/PLUGIN_GUIDE.md`
2. `/root/AWBotNest/plugins/_TEMPLATE.py`
3. `/root/AWBotNest-Plugins/README.md`
4. The target plugin plus 1–3 similar working plugins
5. `manifest.json` when shipping to the AWBotNest-Plugins repository

If runtime behaviour seems to differ from memory, trust the plugin guide and template first.

## Local-first workflow

When the user is iterating on a plugin already installed on their running instance, default to editing the installed copy first:

- runtime copy: `/data/AWBotNest/plugins/...`
- repo copy: `/root/AWBotNest-Plugins/plugins/...`

Use the local runtime copy for debugging and validation. Only sync back to the GitHub/plugin-market repo when the user explicitly asks or when the task is clearly about publishing.

## Supported plugin shapes

AWBotNest supports two plugin shapes:

- Single-file plugin: `plugins/<id>.py`
- Package plugin: `plugins/<id>/__init__.py`

Rules:

- `__plugin__["id"]` must equal the filename or directory name.
- `_`-prefixed files/directories are not recognized as plugins.
- Plugin-to-plugin imports are forbidden.
- Package plugins may use relative imports inside their own directory.

Use package plugins when the feature needs split modules, resources, or a Vue frontend.

## Mandatory plugin contract

Every plugin needs:

1. top-level literal `__plugin__` dict
2. `setup(ctx)`
3. optional `teardown(ctx)`

`__plugin__` must stay a pure literal dict because the platform reads it by AST, not by executing the file.

Minimal shape:

```python
__plugin__ = {
    "name": "示例功能",
    "id": "my_feature",
    "version": "1.0.0",
    "scope": "user",  # user | bot | both | standalone
    "author": "AWdress",
    "description": "功能说明",
    "icon": "",
    "default_enabled": False,
    "config_schema": {
        "keyword": {"type": "string", "default": "hello", "label": "触发词"},
    },
    "requirements": ["httpx>=0.27"],
}

async def setup(ctx):
    @ctx.on_message(ctx.filters.text)
    async def handler(client, message):
        await message.reply("matched")

async def teardown(ctx):
    pass
```

Required metadata fields:

- `name`
- `id`
- `version`
- `scope`

Choose `standalone` when the plugin does not depend on a Telegram user account or bot, such as scheduled jobs, webhooks, external APIs, or browser automation. A standalone plugin can still use configuration, storage, platform AI, notifications, and scheduling, but an `auto` Telegram handler target mounts to no account. Use `user`, `bot`, or `both` if the plugin listens for Telegram messages.

Common optional fields:

- `author`
- `description`
- `icon`
- `default_enabled`
- `config_schema`
- `requirements`
- `webhook`

## Use ctx for all platform interaction

Plugin code should go through `ctx`, not direct platform internals.

Use:

- handlers: `ctx.on_message`, `ctx.on_edited_message`, `ctx.on_callback`, `ctx.on_webhook`
- filters: `ctx.filters.*`; combine with `&`, `|`, and `~`
- messaging: `ctx.bot`, `ctx.user`, `ctx.user_apps`
- admin notifications: `ctx.notify`, `ctx.notify_table`
- browser and synced cookies: `ctx.browser`, `ctx.cookies`
- platform AI: `ctx.ai`
- config: `ctx.config`
- storage: `ctx.kv`, `ctx.data_dir`
- logging: `ctx.log`
- scheduling: `ctx.schedule`
- cleanup: `ctx.add_cleanup`
- stop propagation: `ctx.StopPropagation`

Do not:

- `import pyrogram`
- import global config modules
- import kernel/platform internals for plugin logic
- use `@Client.on_message`
- use `print`

## Platform AI and cookies

The plugin guide officially defines both capabilities:

- Use `ctx.ai` for text, vision, and image generation. Do not store API keys or create a separate OpenAI client. Check `ctx.ai.is_available(...)`, and use model aliases returned by `ctx.ai.available_models(...)` when a plugin exposes model choice.
- Declare `cookie_domains` in the literal plugin metadata before reading synchronized cookies through `ctx.cookies`. Never store CookieCloud credentials or enumerate undeclared domains. Use `request_sync(domain)` when a required cookie is missing.
- Use `ctx.browser` for JavaScript rendering and interactive browser work; do not bundle or install a browser runtime from plugin code.

## Handler rules

Register handlers only inside `setup(ctx)`.

Examples:

```python
@ctx.on_message(ctx.filters.text)
async def h(client, message):
    ...

@ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-10)
async def h2(client, message):
    ...

@ctx.on_edited_message(ctx.filters.text)
async def on_edit(client, message):
    ...

@ctx.on_callback(ctx.filters.regex("^my_btn$"))
async def on_click(client, callback_query):
    ...
```

Notes:

- `group` is relative ordering inside plugin handling.
- `target` may be `auto`, `user`, `bot`, or `both`.
- For command-style user plugins, inspect similar working plugins before assuming `ctx.filters.command(...)` is the best trigger.

## Config schema rules

All plugin business config belongs in `__plugin__["config_schema"]`.
Do not write business settings into platform config.

Supported field types from the plugin guide:

- `string`
- `password`
- `number`
- `boolean`
- `select`
- `multiselect`
- `slider`
- `text`

Field shape:

```python
"field_name": {
    "type": "string|password|number|boolean|select|multiselect|slider|text",
    "default": "",
    "label": "显示名",
    "help": "字段说明",
    "options": ["a", "b"],
    "min": 0,
    "max": 100,
    "step": 1,
    "section": "分区标题",
    "show_if": {"other_field": True},
}
```

Practical rules:

- Every field should have a sensible `default`.
- Use `section` to group fields.
- Use `show_if` for conditional visibility.
- Keep field keys stable during UI-only refactors so saved config still works.
- Read saved values through `ctx.config`.

## Vue plugin convention

Use Vue only when the plugin genuinely needs a richer management interface.

Current observed convention:

- package plugin shape
- `__plugin__["render_mode"] = "vue"`
- backend default config centralized in `DEFAULTS = {...}`
- frontend config loaded/saved via `host.getConfig()` and `host.saveConfig(...)`
- runtime/test/history operations exposed via `ctx.on_api(...)`

Rules:

- Keep backend defaults centralized.
- Keep frontend config shape aligned with backend defaults.
- Use `ctx.on_api` for operational endpoints.
- Rebuild and ship `frontend/dist` after frontend changes.

## Notifications

Use `ctx.notify(...)` for admin notifications.
Do not reimplement notification routing with direct bot sends.

Example:

```python
await ctx.notify("任务失败", level="error", category="备份", account=client)
```

When result data already exists as a mapping or list of mappings, pass it directly and let
the platform infer table headers:

```python
await ctx.notify({"Account": "A", "Status": "OK"})
await ctx.notify([
    {"Account": "A", "Status": "OK", "Points": 100},
    {"Account": "B", "Status": "Failed", "Points": 0},
])
```

For rankings, multi-account results, and other row/column summaries, prefer
`ctx.notify_table(...)`:

```python
await ctx.notify_table(
    ["Account", "Status", "Points"],
    [["A", "OK", 100], ["B", "Failed", 0]],
    caption="Daily check-in",
    level="success",
    category="Check-in",
    align=["left", "center", "right"],
)
```

The platform renders native tables for Telegram bots and Premium user accounts,
and automatically converts them into readable grouped text for regular user accounts,
WeCom, and Bark. Do not add plugin-side Premium checks for notification tables.
Legacy multi-account summaries, repeated `[item] result` lines, and repeated
`field: value` details may be auto-detected by the platform; keep plain text when it is
narrative rather than tabular.

Use `ctx.notify(content, format="rich")` only when a structured notification cannot
be expressed with `notify_table`. Rich notification HTML is sanitized by the platform.

## Storage rules

- Use `ctx.kv` for plugin-scoped key/value state.
- Use `ctx.data_dir` for actual files.
- Keep plugin data isolated.
- Release plugin-owned resources in `teardown` or via `ctx.add_cleanup`.
- Platform-registered handlers/tasks are auto-cleaned; only clean what the plugin manages itself.

## Scheduling rules

Use `ctx.schedule(...)`.

Examples:

```python
ctx.schedule(tick, "interval", seconds=60)
ctx.schedule(tick, "cron", hour=3, minute=0)
ctx.schedule(daily_report, "cron", hour=9, id="每日早报")
```

Be careful when generating cron expressions from config. Validate minute/hour ranges.

## Dependencies

Declare third-party dependencies in `__plugin__["requirements"]`.
Do not call pip inside plugin code.

Rules from the plugin guide:

- use PEP 508 strings
- prefer broad compatible ranges like `>=`
- verify Python 3.13 support
- prefer platform-provided libraries when available
- optional imports should degrade gracefully

## Webhook plugins

If a plugin receives external callbacks:

- set `"webhook": True` in `__plugin__`
- register one `@ctx.on_webhook` handler
- return `dict`, `str`, or `None`
- let the platform own webhook auth

Example:

```python
__plugin__ = { ..., "webhook": True }

async def setup(ctx):
    @ctx.on_webhook
    async def on_hook(req):
        data = req.json or {}
        await ctx.notify(f"收到事件：{data}", category="Webhook")
        return {"ok": True}
```

## Marketplace / AWBotNest-Plugins publishing

When shipping to the plugin-market repository:

- bump `__plugin__["version"]`
- mirror version in `manifest.json`
- keep manifest key equal to plugin id
- use `.py` path for single-file plugins
- use trailing `/` path for package plugins
- keep duplicated metadata aligned where the repo expects it
- include built `frontend/dist/` for Vue plugins

If the repo uses duplicated card metadata in both `__plugin__` and `manifest.json`, keep them in sync.

## Validation checklist

Before finishing plugin work:

- [ ] plugin id matches filename or directory name
- [ ] `__plugin__` is a literal dict
- [ ] required metadata fields exist
- [ ] handler registration happens inside `setup(ctx)`
- [ ] no direct `pyrogram` / config / kernel imports for plugin behaviour
- [ ] no `@Client.on_message`
- [ ] no `print`
- [ ] config comes from `config_schema` / `ctx.config`
- [ ] runtime state uses `ctx.kv` / `ctx.data_dir`
- [ ] dependencies are declared, not self-installed
- [ ] Vue plugins have aligned defaults and shipped `frontend/dist`
- [ ] AI-related behaviour is described as current repo practice unless the plugin guide/template explicitly defines it
- [ ] manifest/version metadata updated when publishing
- [ ] edited plugin actually matches 1–3 similar working plugins where behaviour is repo-specific

## Repo-specific reality check

The plugin guide is authoritative for plugin contract and allowed APIs.
When marketplace conventions differ from the minimal guide, inspect the current AWBotNest-Plugins repo and nearby working plugins before finalizing metadata, icon usage, command trigger style, and publishing details.
