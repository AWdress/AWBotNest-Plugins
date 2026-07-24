---
name: awbotnest-plugin-development
description: Create, modify, review, validate, or publish AWBotNest plugins and AWBotNest-Plugins marketplace entries. Use for plugin metadata, ctx lifecycle APIs, config_schema layout, Vue management panels, webhooks, dependencies, version bumps, manifest updates, and hot-reload-safe implementation.
---

# AWBotNest Plugin Development

Build plugins against the platform contract and publish them through `AWBotNest-Plugins` without bypassing lifecycle, configuration, or marketplace rules.

## Read the source of truth

For platform-sensitive work, read the latest available sources in this order:

1. `AWdress/AWBotNest/docs/SPEC.md`
2. `AWdress/AWBotNest/docs/PLUGIN_GUIDE.md`
3. `AWdress/AWBotNest/plugins/_TEMPLATE.py` or `_TEMPLATE_VUE/`
4. The current repo `README.md`
5. `manifest.json` and 1–3 similar local plugins

Treat the platform repo as the runtime contract and this repo as the marketplace convention. Prefer current local documentation over remembered rules.

## Choose the plugin shape

- Use `plugins/<id>.py` for a simple plugin.
- Use `plugins/<id>/__init__.py` for helpers, resources, records, OCR, or a Vue frontend.
- Make `__plugin__["id"]` equal the filename or directory name.
- Keep private helpers prefixed with `_`; never import sibling plugins.

## Implement the contract

Declare `__plugin__` as a pure literal dictionary because discovery uses AST parsing:

```python
__plugin__ = {
    "name": "示例功能",
    "id": "my_feature",
    "version": "1.0.0",
    "scope": "user",  # user | bot | both
    "author": "",
    "description": "功能说明",
    "changelog": "v1.0.0 初始版本\n- 实现基础功能",
    "default_enabled": False,
}

async def setup(ctx):
    @ctx.on_message(ctx.filters.text)
    async def handler(client, message):
        await message.reply("ok")

async def teardown(ctx):
    pass
```

Require `changelog` on every published plugin. Put the current version first, retain useful prior entries, and describe user-visible additions, fixes, and breaking behavior.

Register handlers only inside `setup(ctx)`. Use `ctx` as the platform boundary:

- Handlers: `ctx.on_message`, `ctx.on_edited_message`, `ctx.on_callback`, `ctx.on_webhook`, `ctx.on_api`, `ctx.action`
- Filters: `ctx.filters.*`; combine with `&`, `|`, and `~`
- Sending: `ctx.bot`, `ctx.user`, `ctx.user_apps`, `ctx.notify`, `ctx.owner_id`
- Runtime: `ctx.config`, `ctx.update_config`, `ctx.kv`, `ctx.data_dir`, `ctx.log`
- Utilities: `ctx.download`, `ctx.browser`
- Lifecycle: `ctx.schedule`, `ctx.add_cleanup`, `ctx.StopPropagation`

Do not import Pyrogram for decorator registration, use `@Client.on_message`, read platform config files, or use `print()` for operational logging. Treat `group=` as ordering only within the plugin; the platform isolates plugin group ranges.

## Choose configuration mode deliberately

Default to native `config_schema`. Do not migrate a plugin to Vue merely to make it prettier.

Use `config_schema` for:

- Switches, text, passwords, numbers, selects, multiselects, sliders
- Conditional fields with `show_if`
- Variable-length records with `list`
- Conversation selection with `chat`
- One-shot operations with `action`
- Read-only guidance or status with `info`

Use Vue only when the interface is part of the feature: charts, history tables, leaderboards, activity monitoring, bulk management, or a multi-step API-driven console.

### Native schema layout

Supported types are `string`, `password`, `number`, `boolean`, `select`, `multiselect`, `slider`, `text`, `list`, `chat`, `action`, and `info`.

```python
"config_schema": {
    "enabled": {
        "type": "boolean", "default": True,
        "label": "启用", "section": "总开关", "cols": 4, "order": 1,
    },
    "rules": {
        "type": "list", "default": [], "label": "规则",
        "section": "规则管理", "item_label": "规则",
        "fields": {
            "keyword": {"type": "string", "label": "关键词"},
            "active": {"type": "boolean", "label": "启用", "default": True},
        },
    },
    "groups": {
        "type": "chat", "default": [], "label": "群组",
        "multi": True, "chat_types": ["group"], "section": "范围",
    },
    "test": {
        "type": "action", "label": "测试连接", "action": "test",
        "section": "连接",
    },
}
```

Schema rules:

- Give every stored field a sensible `default`.
- Group fields into meaningful `section` cards; avoid one flat “参数” section.
- Let the platform use its defaults unless a deliberate composition improves scanning: short fields default to 6 columns and large fields to 12.
- Use `cols` (1–12) for intentional `6+6`, `4+4+4`, or `8+4` rows, and `order` for stable ordering within a section. Narrow screens collapse all fields to one column.
- Use `show_if` for dependent settings.
- Prefer `list` over ad hoc multiline formats for structured repeating rules.
- Prefer `chat` over manual numeric IDs when the user selects a conversation.
- Register an `action` using `ctx.action("name")`; use `danger=True` when confirmation is required.
- Keep field keys unchanged during layout-only refactors so saved configuration remains compatible.

Backend code reads native and Vue-saved settings through `ctx.config`.

### Vue management panels

Vue mode requires a package plugin and:

```python
__plugin__ = {
    # ...
    "render_mode": "vue",
}
```

Place a Vite module-federation project in `frontend/` and expose `./Config`. The platform injects `props { pluginId, host }`:

- `host.getConfig()` and `host.saveConfig(values)` manage settings.
- `host.callApi(path, {method, body})` calls plugin APIs.
- `host.toast.success/error` reports UI results.

Register backend endpoints with `@ctx.on_api("/path", methods=[...])`. Use `req.json` according to the current platform guide; do not invent a separate configuration endpoint when `host.saveConfig` already exists.

To display group names instead of numeric IDs in Vue interfaces, call `/api/chats/{chat_id}` from the plugin backend using `httpx` with an admin Bearer token. The response is `{id, title, type}`. Fall back to displaying the ID if the query fails.

Before publishing, run `npm run build` and commit `frontend/dist/`. Ensure `.gitignore` does not exclude `dist`. Use responsive layouts for the roughly 1000px desktop canvas and narrow full-screen mode.

## Store state and files correctly

- Put persistent state in the plugin-scoped `ctx.kv`.
- Put writable artifacts in `ctx.data_dir`.
- Prefix any relational table with `<plugin_id>_`.
- Release plugin-owned tasks, clients, and resources in `teardown` or `ctx.add_cleanup`.
- Let the platform clean up handlers and schedules it registered.

## Declare dependencies

Declare third-party packages in `__plugin__["requirements"]` as PEP 508 strings. Prefer compatible lower bounds (`>=`) and verify Python 3.13 support. Never invoke `pip` in plugin code.

If a dependency is optional, guard the import and degrade gracefully. Network libraries normally inherit platform proxy environment variables; do not disable `trust_env` unless direct access is intentional.

## Implement webhooks

Set `"webhook": True` and register exactly one `@ctx.on_webhook` handler. Accept the platform `WebhookRequest`; use `req.method`, `query`, `headers`, `json`, `text`, or `body`, and return `dict`, `str`, or `None`. Do not implement independent API-key handling—the platform owns webhook authentication.

## Publish to the marketplace

For any shipped plugin code change:

1. Bump `__plugin__["version"]`.
2. Require and update `__plugin__["changelog"]` with the user-visible changes, fixes, and any breaking behavior; use `\n` for multiple lines and retain useful earlier entries below the current release.
3. Mirror the version in root `manifest.json`.
4. Keep manifest key equal to plugin ID.
5. Use a `.py` path for single-file plugins and a trailing `/` for packages.
6. Keep name, description, author, and icon consistent when duplicated.
7. Include Vue `frontend/dist/` when applicable.

Without a version bump, installed platforms will not receive the update.

## Workflow

1. Read current platform and repo guidance.
2. Inspect the target and 1–3 comparable plugins.
3. Choose single-file/package and native-schema/Vue modes.
4. Preserve saved configuration keys unless migration is explicitly required.
5. Implement through `ctx`; add cleanup and graceful degradation.
6. Update plugin and manifest versions.
7. Validate Python syntax, literal metadata, schema sections, version parity, and frontend build output.
8. Review the staged diff so unrelated user changes are not included.

## Verification checklist

- [ ] ID, path, directory/filename, and manifest key agree.
- [ ] `__plugin__` is a literal dict with name, ID, version, and scope.
- [ ] `changelog` exists on every published plugin, starts with the current release, and retains useful history.
- [ ] All runtime registration flows through `ctx` inside `setup`.
- [ ] Native configuration uses meaningful sections, supported field types, and deliberate `cols`/`order` only where they improve layout.
- [ ] Vue is justified by management/visual interaction and includes built `dist`.
- [ ] Backend settings come from `ctx.config`; runtime data uses `ctx.kv`/`ctx.data_dir`.
- [ ] Dependencies are declared and compatible; no self-installation occurs.
- [ ] Plugin-owned resources are cleaned up.
- [ ] Plugin and manifest versions match.
- [ ] Modified Python compiles and `git diff --check` passes (generated bundles may be exempt only when unavoidable).

For a copyable native starter, read `references/minimal-plugin-template.py`.
