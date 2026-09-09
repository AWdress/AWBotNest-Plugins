from __future__ import annotations

import unittest
from types import SimpleNamespace

from plugins_v2.custom_plugin import core


class Context:
    def __init__(self, source=core.DEFAULT_SOURCE, enabled=True):
        self.config = {"code_enabled": enabled, "source": source, "custom_config": "{}"}
        self.log = SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None)
        self.apis = {}
        self.messages = []
        self.cleanups = []

    def on_api(self, path, callback=None, **kwargs):
        def register(fn):
            self.apis[path] = fn
            return fn
        return register(callback) if callback else register

    def on_message(self, **kwargs):
        return lambda fn: self.messages.append((kwargs, fn)) or fn

    def add_cleanup(self, fn):
        self.cleanups.append(fn)

    def update_config(self, values):
        self.config.update(values)


class NativeCustomPluginTests(unittest.IsolatedAsyncioTestCase):
    async def test_registers_native_api_paths_and_template(self):
        ctx = Context()
        await core.setup(ctx)
        self.assertEqual(set(ctx.apis), {"status", "validate"})
        self.assertEqual(len(ctx.messages), 1)
        status = await ctx.apis["status"](SimpleNamespace(method="GET"))
        self.assertEqual(status["state"], "running")
        self.assertIn("async def hello(event)", status["template"])

    async def test_failed_source_does_not_commit_handler(self):
        source = "async def setup(ctx):\n @ctx.on_message(pattern='x')\n async def x(event): pass\n raise RuntimeError('boom')"
        ctx = Context(source)
        await core.setup(ctx)
        self.assertEqual(ctx.messages, [])
        status = await ctx.apis["status"](SimpleNamespace(method="GET"))
        self.assertEqual(status["state"], "error")


if __name__ == "__main__":
    unittest.main()
