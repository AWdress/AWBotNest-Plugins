---
name: awbotnest-plugin-development
description: Use when creating, modifying, reviewing, or publishing plugins for AWBotNest and its AWBotNest-Plugins marketplace repo.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [awbotnest, plugins, telegram, python, manifest, hot-reload]
    related_skills: [requesting-code-review, github-repo-management]
---

# AWBotNest Plugin Development

## Overview

AWBotNest plugins follow a strict hot-pluggable contract. A plugin is either a single Python file under `plugins/` or a package directory with `__init__.py`. Platform integration must go through `ctx`; direct use of platform internals or raw Pyrogram decorators breaks unload/reload behavior.

The marketplace repo `AWdress/AWBotNest-Plugins` adds one more publishing contract: root `manifest.json` must describe each plugin, and any code change that should ship to installed users must also bump the plugin version in both the plugin metadata and the manifest entry.

## When to Use

Use this skill when:
- Creating a new AWBotNest plugin
- Modifying an existing plugin in `AWBotNest-Plugins`
- Reviewing whether a plugin follows platform conventions
- Preparing a plugin change for marketplace publication

Do not use this skill for:
- Core AWBotNest platform changes outside the plugin contract
- Generic Telegram bot code that does not run as an AWBotNest plugin

## Source of Truth

Read sources in this order:
- `AWdress/AWBotNest/docs/SPEC.md`
- `AWdress/AWBotNest/docs/PLUGIN_GUIDE.md`
- `AWdress/AWBotNest/plugins/_TEMPLATE.py`
- `AWdress/AWBotNest-Plugins/README.md`
- `AWdress/AWBotNest-Plugins/manifest.json`
- Existing plugins under `AWdress/AWBotNest-Plugins/plugins/`

Use the platform repo as the hard contract and the plugin repo as the publishing/distribution convention.

## Plugin Shapes

Two supported shapes:

1. Single-file plugin: `plugins/<id>.py`
2. Package plugin: `plugins/<id>/__init__.py`

Rules:
- Plugin `id` must equal the filename or directory name, without `.py`
- If a single file and directory share the same name, single-file wins
- Files or directories starting with `_` are helper/private and are not discovered as plugins
- Use package form when the plugin needs helper modules, OCR utilities, records, or other internal structure

## Required Contract

Every plugin must expose these pieces:

```python
__plugin__ = {
    "name": "My Feature",
    "id": "my_feature",
    "version": "1.0.0",
    "scope": "user",
}

async def setup(ctx):
    @ctx.on_message(ctx.filters.text)
    async def handler(client, message):
        await message.reply("ok")

async def teardown(ctx):
    pass
```

Notes:
- `__plugin__` must be a pure literal dict because the platform parses it statically via AST
- `setup(ctx)` is mandatory
- `teardown(ctx)` is optional, but required in practice when the plugin owns long-lived resources
- Supported `scope` values: `user`, `bot`, `both`

Useful optional metadata keys:
- `author`
- `description`
- `icon`
- `default_enabled`
- `webhook`
- `config_schema`
- `requirements`

## ctx-Only Integration Rule

Treat `ctx` as the only platform API surface.

Use:
- `@ctx.on_message(...)`
- `@ctx.on_edited_message(...)`
- `@ctx.on_callback(...)`
- `@ctx.on_webhook`
- `ctx.filters.*`
- `ctx.bot`, `ctx.user`, `ctx.user_apps`
- `ctx.notify(...)`
- `ctx.config[...]`
- `ctx.kv`
- `ctx.data_dir`
- `ctx.log`
- `ctx.schedule(...)`
- `ctx.add_cleanup(...)`
- `ctx.StopPropagation`

Do not use:
- `import pyrogram` for handler registration
- `@Client.on_message` or other raw client decorators
- direct imports of platform config or core modules just to reach runtime state
- `print()` for operational logging

Why: hot enable/disable and per-plugin lifecycle management depend on the platform owning handler registration and cleanup.

## Handler Conventions

Register handlers inside `setup(ctx)` only.

Typical examples:

```python
@ctx.on_message(ctx.filters.command("id"), target="user")
async def on_id(client, message):
    ...

@ctx.on_callback(ctx.filters.regex("^pick:"), target="bot")
async def on_pick(client, callback_query):
    ...
```

Guidance:
- Use `target="auto"` unless the plugin clearly needs `user`, `bot`, or `both`
- `group` is only for ordering inside the current plugin; the platform isolates plugins into separate group ranges
- Raise `ctx.StopPropagation` only when the plugin intentionally wants to prevent later handlers in the same processing chain

## Configuration via config_schema

Business configuration belongs in `__plugin__["config_schema"]`. The platform uses it to build the configuration UI, and runtime reads should come from `ctx.config[...]`.

Supported field types:
- `string`
- `password`
- `number`
- `boolean`
- `select`
- `multiselect`
- `slider`
- `text`

Typical schema:

```python
"config_schema": {
    "enabled": {
        "type": "boolean",
        "default": True,
        "label": "启用",
        "section": "基础"
    },
    "keyword": {
        "type": "string",
        "default": "",
        "label": "关键词",
        "section": "基础",
        "show_if": {"enabled": True}
    }
}
```

Rules:
- Every field needs a sensible `default`
- Group related fields using `section`
- Use `show_if` to keep option-heavy plugins readable instead of overloading one flat form
- Prefer simple field combinations over inventing custom config formats
- For variable-length rules, use multiline `text` and parse line-by-line inside the plugin
- Do not read or mutate platform config files directly
- Business settings belong in plugin config, not platform settings

## State, Files, and Logging

Use the platform-owned storage surfaces:
- Persistent key-value state: `ctx.kv`
- Writable plugin-private files: `ctx.data_dir`
- Logging: `ctx.log.info/debug/warning/error`

Rules:
- Do not use ad hoc cross-plugin shared state
- If relational tables are needed, prefix table names with `<plugin_id>_`
- Keep plugin-owned artifacts inside `ctx.data_dir`

## Dependencies

Third-party libraries must be declared, never installed manually by the plugin.

Prefer platform-built-in dependencies first. Before adding a new requirement, inspect the platform's existing dependency set and reuse it when practical. The platform docs explicitly call out common built-ins such as `ddddocr`, `httpx`, `aiohttp`, and `Pillow`.

Before declaring a new dependency, verify it supports the platform Python version. The platform documentation targets Python 3.13 and specifically warns that some packages publish versions that still exclude 3.13 via `Requires-Python`. A requirement that resolves on older Python may still be uninstallable here.

Example:

```python
"requirements": [
    "httpx>=0.27",
    "rapidocr>=2",
]
```

Rules:
- Use PEP 508 requirement strings
- Prefer compatible lower bounds like `>=` over hard pins like `==`
- Never call `pip` from plugin code
- Verify the requirement can actually resolve on Python 3.13 before shipping it
- Remember AWBotNest is a single-process hot-plug system: one incompatible dependency version can block enablement
- If a dependency is optional, code the import path to degrade gracefully rather than crashing the whole plugin
- Network clients usually inherit proxy behavior from environment variables exported by the platform
- Conflicts with already-installed package versions should be treated as enable-time blockers, not something the plugin tries to overwrite

## Webhook Plugins

If a plugin receives external callbacks:

1. Set `"webhook": True` in `__plugin__`
2. Register exactly one `@ctx.on_webhook` handler in `setup(ctx)`
3. Accept a `WebhookRequest` and return either `dict`, `str`, or `None`

Example:

```python
__plugin__ = {"name": "Hook", "id": "hook", "version": "1.0.0", "scope": "bot", "webhook": True}

async def setup(ctx):
    @ctx.on_webhook
    async def on_webhook(req):
        data = req.json or {}
        await ctx.notify(f"收到事件: {data}", category="Webhook")
        return {"ok": True}
```

## Marketplace Publishing Contract

When working in `AWBotNest-Plugins`, check both the plugin file and root `manifest.json`.

Manifest shape:

```json
{
  "my_feature": {
    "name": "My Feature",
    "version": "1.0.0",
    "author": "You",
    "description": "...",
    "icon": "https://...",
    "path": "plugins/my_feature.py"
  }
}
```

Publishing rules:
- `manifest.json` key must equal plugin `id`
- `path` must point to the plugin file or directory
- For package plugins, the manifest path should end with `/`
- Keep `icon` consistent with `__plugin__["icon"]` if both are present
- Any shipped code change must bump plugin `version`
- The same version bump must be mirrored in `manifest.json`
- Without a version bump, the store will not detect an update and installed platforms will not receive it

## Recommended Workflow

1. Identify whether the change belongs in a single-file plugin or package plugin.
Completion criterion: the target plugin path and `id` are fixed before editing.

2. Inspect 1-3 similar plugins in the repo.
Completion criterion: local naming, handler style, and config patterns are clear.

3. Implement or modify `__plugin__`, `setup(ctx)`, and any helpers.
Completion criterion: all handlers are registered through `ctx`, with no raw client decorators.

4. Add or refine `config_schema`, `requirements`, `ctx.kv`, and cleanup logic as needed.
Completion criterion: runtime state, configuration, and external dependencies all flow through platform-approved surfaces.

5. Update `manifest.json`.
Completion criterion: manifest key, path, metadata, and version match the plugin.

6. Bump versions whenever behavior changes should ship.
Completion criterion: plugin metadata version and manifest version are both updated together.

7. Verify syntax and obvious contract mistakes before commit/push.
Completion criterion: modified files parse cleanly and no rule in this skill is violated.

## Review Checklist

Use this checklist when reviewing a plugin PR or local change:

- [ ] Plugin `id` matches its filename or directory name
- [ ] `__plugin__` is present and literal
- [ ] `setup(ctx)` exists and registers handlers only through `ctx`
- [ ] No `@Client.on_message` or direct platform-core imports for runtime wiring
- [ ] No `print()` calls for operational logs
- [ ] Business settings live in `config_schema`
- [ ] Persistent state uses `ctx.kv` and files use `ctx.data_dir`
- [ ] Long-lived resources are released in `teardown(ctx)` or via `ctx.add_cleanup(...)`
- [ ] Requirements are declared in metadata, not installed in code
- [ ] `manifest.json` entry exists and matches the plugin
- [ ] Version was bumped if marketplace users should receive the change

## Common Pitfalls

1. Forgetting to update `manifest.json` after editing plugin code.
This silently breaks marketplace distribution even when the code itself is correct.

2. Changing plugin code without bumping version.
The store polls by version; no version change means no update rollout.

3. Registering handlers outside `setup(ctx)`.
This undermines lifecycle control and tends to break disable/unload behavior.

4. Importing Pyrogram decorators directly.
Even if it seems to work locally, it bypasses platform ownership of handlers.

5. Writing business settings as hard-coded constants or external ad hoc files.
Those settings belong in `config_schema` so the UI and runtime stay aligned.

6. Forgetting cleanup for background tasks or network resources.
Hot reload makes leaks visible quickly; clean up anything the platform does not auto-manage.

7. Cross-importing another plugin.
Shared code should live in helper modules within the same plugin package or be promoted into platform/shared support, not imported from a sibling plugin.

## Reference Files

For a copyable starter, load:
- `references/minimal-plugin-template.py`

Use the platform's richer example `AWdress/AWBotNest/plugins/_TEMPLATE.py` when the plugin needs webhook, scheduling, or more complex config examples.

## Verification Checklist

- [ ] Plugin shape is valid: single file or package directory
- [ ] `id`, filename/directory name, and manifest key all match
- [ ] `__plugin__` includes `name`, `id`, `version`, `scope`
- [ ] All handlers and webhook hooks are registered through `ctx`
- [ ] Config is exposed through `config_schema` and read from `ctx.config`
- [ ] State/files/logging use `ctx.kv`, `ctx.data_dir`, `ctx.log`
- [ ] Requirements are declared, not self-installed
- [ ] Cleanup exists for plugin-owned resources
- [ ] `manifest.json` path/version/metadata match the plugin
- [ ] Version bump is present when preparing marketplace publication
