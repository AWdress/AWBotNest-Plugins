"""Static and lifecycle smoke checks for generated AWBotNest 2 packages."""
from __future__ import annotations

import argparse
import ast
import asyncio
import importlib
import json
import logging
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class KV:
    def __init__(self): self.values = {}
    def get(self, key, default=None): return self.values.get(key, default)
    def set(self, key, value): self.values[key] = value
    def delete(self, key): self.values.pop(key, None)
    def items(self): return list(self.values.items())


class ClosedTask:
    def done(self): return True
    def cancel(self): return None
    def add_done_callback(self, callback): return None


class FakeContext:
    def __init__(self, plugin_id, data_dir):
        self.plugin_id = plugin_id
        self.config = {}
        self.kv = KV()
        self.data_dir = data_dir
        self.users = []
        self.bot = None
        self.log = logging.getLogger(f"v2check.{plugin_id}")
        self.http = self.cookies = self.browser = self.ai = SimpleNamespace()
        self.registrations = []

    def _decorator(self, kind, **kwargs):
        def decorate(callback):
            self.registrations.append((kind, callback, kwargs))
            return callback
        return decorate

    def on_message(self, **kwargs): return self._decorator("message", **kwargs)
    def on_edited_message(self, **kwargs): return self._decorator("edited", **kwargs)
    def on_callback(self, **kwargs): return self._decorator("callback", **kwargs)
    def schedule_interval(self, name, callback, *, seconds):
        self.registrations.append(("interval", callback, {"name": name, "seconds": seconds})); return name
    def schedule_cron(self, name, callback, **fields):
        self.registrations.append(("cron", callback, {"name": name, **fields})); return name
    def create_task(self, awaitable, *, name=None, **kwargs):
        awaitable.close()
        return ClosedTask()
    def action(self, name, callback): self.registrations.append(("action", callback, {"name": name}))
    def on_webhook(self, path, callback): self.registrations.append(("webhook", callback, {"path": path}))
    def update_config(self, values): self.config.update(values); return dict(self.config)
    async def notify(self, *args, **kwargs): return None


async def lifecycle(plugin_id, temp_root):
    module = importlib.import_module(f"plugins_v2.{plugin_id}")
    ctx = FakeContext(plugin_id, temp_root / plugin_id)
    ctx.data_dir.mkdir(parents=True, exist_ok=True)
    await asyncio.wait_for(module.setup(ctx), timeout=5)
    teardown = getattr(module, "teardown", None)
    if teardown:
        await asyncio.wait_for(teardown(ctx), timeout=5)
    return len(ctx.registrations)


def static_check(manifest):
    errors = []
    for plugin_id, row in manifest.items():
        entry = ROOT / row["path"] / "__init__.py"
        if not entry.exists():
            errors.append(f"{plugin_id}: missing entry")
            continue
        tree = ast.parse(entry.read_text(encoding="utf-8"), filename=str(entry))
        node = next((n for n in tree.body if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__plugin__" for t in n.targets)), None)
        metadata = ast.literal_eval(node.value) if node else {}
        for key in ("id", "name", "version", "scope", "config_schema"):
            if key not in metadata:
                errors.append(f"{plugin_id}: missing {key}")
        if metadata.get("id") != plugin_id:
            errors.append(f"{plugin_id}: id mismatch")
        if metadata.get("version") != row.get("version") or metadata.get("scope") != row.get("scope"):
            errors.append(f"{plugin_id}: manifest mismatch")
        if entry.stat().st_size > 2 * 1024 * 1024:
            errors.append(f"{plugin_id}: entry too large")
        schema = metadata.get("config_schema") or {}
        legacy_root = entry.parent / "_legacy"
        legacy_files = list(legacy_root.rglob("*.py")) if legacy_root.is_dir() else [entry.parent / "_legacy.py"]
        used_keys = set()
        for legacy_file in legacy_files:
            if not legacy_file.exists():
                continue
            source = legacy_file.read_text(encoding="utf-8")
            used_keys.update(re.findall(r"ctx\.config\.get\(\s*['\"]([^'\"]+)", source))
            used_keys.update(re.findall(r"ctx\.config\[\s*['\"]([^'\"]+)", source))
            used_keys.update(re.findall(r"ctx\.update_config\(\s*\{\s*['\"]([^'\"]+)", source))
        missing = sorted(used_keys - set(schema))
        if missing:
            errors.append(f"{plugin_id}: undeclared config keys {missing}")
    return errors


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-lifecycle", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "manifest_v2.json").read_text(encoding="utf-8"))["plugins"]
    errors = static_check(manifest)
    registrations = {}
    if not args.skip_lifecycle:
        with tempfile.TemporaryDirectory(prefix="awbotnest-v2-check-") as temp:
            for plugin_id in manifest:
                try:
                    registrations[plugin_id] = await lifecycle(plugin_id, Path(temp))
                except Exception as exc:
                    errors.append(f"{plugin_id}: lifecycle {type(exc).__name__}: {exc}")
    print(json.dumps({"plugins": len(manifest), "registrations": registrations, "errors": errors}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    asyncio.run(main())
