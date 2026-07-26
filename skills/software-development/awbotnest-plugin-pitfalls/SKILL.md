---
name: awbotnest-plugin-pitfalls
description: Real-world pitfalls from AWBotNest plugin development. Use when debugging plugin load failures, command non-response, config drift, or hot-reload issues. Load BEFORE starting any AWBotNest plugin work.
---

# AWBotNest Plugin Development Pitfalls

These pitfalls are plugin-focused and should be read together with `PLUGIN_GUIDE.md` and `_TEMPLATE.py`.

## Always read similar working plugins first

Before writing or fixing any plugin:

1. Read the plugin guide and template first.
2. Then inspect 1–3 similar working plugins.
3. Copy proven trigger/filter/config patterns instead of guessing from generic Pyrogram habits.

Skipping this is the fastest way to build something that loads but behaves wrong.

## Pitfall: `__plugin__["id"]` does not match filename or directory name

**Symptom**: Plugin is marked invalid or cannot be enabled correctly.

**Cause**: The plugin contract requires the ID to equal the file or package directory name.

**Fix**:

- single-file plugin: `plugins/foo.py` → `"id": "foo"`
- package plugin: `plugins/foo/__init__.py` → `"id": "foo"`

## Pitfall: `__plugin__` is not a pure literal dict

**Symptom**: Metadata fails to load or the platform cannot statically read the plugin.

**Cause**: The platform reads `__plugin__` through AST, not by executing plugin code.

**Fix**:

- keep `__plugin__` as a top-level literal dict
- do not build it dynamically
- do not populate required metadata via helper functions

## Pitfall: Using `@Client.on_message` or direct Pyrogram imports

**Symptom**: Plugin cannot hot-unload cleanly or violates plugin contract.

**Cause**: AWBotNest plugins must register through `ctx`, not raw class-level decorators.

**Fix**:

- use `@ctx.on_message(...)`
- use `@ctx.on_edited_message(...)`
- use `@ctx.on_callback(...)`
- do not `import pyrogram` for plugin handler registration

## Pitfall: Writing business config outside `config_schema`

**Symptom**: Plugin works only with hidden/manual config edits, or config UI is missing required settings.

**Cause**: Plugin business settings belong in `__plugin__["config_schema"]` and should be read via `ctx.config`.

**Fix**:

- define plugin settings in `config_schema`
- read saved values through `ctx.config`
- do not depend on platform config for plugin business logic

## Pitfall: Missing `default` values in config fields

**Symptom**: Config save/load becomes inconsistent, fields behave unpredictably on fresh install, or runtime code hits missing values.

**Cause**: The plugin guide expects every config field to have a sensible default.

**Fix**:

- provide explicit `default` for every config field
- keep runtime fallbacks aligned with those defaults

## Pitfall: Wrong filter strategy for command-style user plugins

**Symptom**: Plugin loads successfully but commands never trigger.

**Cause**: Generic assumptions about command filters often do not match the actual working pattern used by nearby plugins.

**Fix**:

- inspect similar working plugins first
- for user-command plugins, `ctx.filters.outgoing & ctx.filters.text` plus manual text matching is often safer than guessing
- match the repo’s proven trigger pattern before inventing a new one

## Pitfall: Using `print` instead of `ctx.log`

**Symptom**: Logs are inconsistent or harder to trace in plugin runtime.

**Cause**: The plugin guide expects plugin logging to go through `ctx.log`.

**Fix**:

- use `ctx.log.info(...)`
- use `ctx.log.warning(...)`
- use `ctx.log.error(...)`
- never rely on `print`

## Pitfall: Vue frontend config drifts from backend defaults

**Symptom**: Vue config page shows one field set or default set, but runtime uses another.

**Cause**: Frontend form structure and backend `DEFAULTS` evolved separately.

**Fix**:

- keep a backend `DEFAULTS` block as authoritative config shape
- make Vue config fields match that shape
- rebuild and ship `frontend/dist` after frontend config changes
- recheck `ctx.config.get(...)` against renamed/removed keys

## Pitfall: Shipping Vue source changes without rebuilt `frontend/dist`

**Symptom**: Plugin source looks updated, but installed/published UI still behaves like the old version.

**Cause**: Vue plugin build artifacts were not rebuilt or not committed.

**Fix**:

- rebuild frontend output after Vue changes
- commit `frontend/dist` when that repo/plugin expects built assets to ship
- verify published artifact matches the current source

## Pitfall: Metadata only updated in one place during marketplace publishing

**Symptom**: Card icon/version/description/changelog is stale in some surfaces.

**Cause**: The plugin repo may duplicate metadata between plugin code and `manifest.json`.

**Fix**:

- when publishing to AWBotNest-Plugins, sync duplicated metadata where required
- especially verify version, icon, description, and changelog consistency

## Pitfall: Plugin-owned resources not cleaned up

**Symptom**: Plugin disable/reload leaves behind tasks, connections, or stale state.

**Cause**: Platform auto-cleans ctx-registered handlers/tasks, but not arbitrary resources the plugin created itself.

**Fix**:

- use `ctx.add_cleanup(...)` for self-managed resources
- release them in `teardown(ctx)` when needed
- only manually clean what the plugin itself created

## Pitfall: Declaring unsupported dependencies

**Symptom**: Plugin enable fails at dependency install time.

**Cause**: Requirement range does not support the platform Python version, or the plugin declared a dependency the platform already provides better.

**Fix**:

- verify Python 3.13 compatibility
- prefer platform-provided libraries when available
- declare requirements in `__plugin__["requirements"]`
- do not self-install packages in plugin code

## Summary checklist

Before concluding a plugin is “done”:

- [ ] `id` matches filename/directory name
- [ ] `__plugin__` is a literal dict
- [ ] required metadata fields exist
- [ ] handlers register through `ctx`
- [ ] no direct Pyrogram decorator usage
- [ ] no `print`
- [ ] config is declared in `config_schema`
- [ ] defaults are present and runtime-aligned
- [ ] Vue defaults and built assets are in sync
- [ ] plugin-owned resources are cleaned up
- [ ] marketplace metadata is synchronized when publishing
