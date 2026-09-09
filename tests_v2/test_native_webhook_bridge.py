from __future__ import annotations

import unittest
from types import SimpleNamespace

from plugins_v2.webhook_bridge import core


class Storage:
    def __init__(self): self.data = {}
    async def get(self, key, default=None): return self.data.get(key, default)
    async def set(self, key, value): self.data[key] = value
    async def delete(self, key): return self.data.pop(key, None) is not None


class Context:
    def __init__(self):
        self.config = {"enabled": True, "dedupe_seconds": 60, "rate_limit": 30}
        self.storage = Storage(); self.routes = {}; self.actions = {}; self.sent = []
        self.log = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None,
                                   exception=lambda *a, **k: None)
    def on_webhook(self, path):
        return lambda fn: self.routes.setdefault(path, fn) or fn
    def action(self, name):
        return lambda fn: self.actions.setdefault(name, fn) or fn
    async def notify(self, text, **kwargs): self.sent.append((text, kwargs))
    def update_config(self, values): self.config.update(values)


class NativeWebhookBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_receive_route_forwards_and_deduplicates(self):
        ctx = Context(); await core.setup(ctx)
        self.assertEqual(set(ctx.routes), {"receive"})
        req = SimpleNamespace(method="POST", path="receive", body='{"title":"构建完成","message":"发布成功"}'.encode(),
                              query={}, headers={"content-type": "application/json"},
                              json={"title": "构建完成", "message": "发布成功"}, text="")
        first = await ctx.routes["receive"](req)
        second = await ctx.routes["receive"](req)
        self.assertTrue(first["forwarded"])
        self.assertTrue(second["ignored"])
        self.assertEqual(len(ctx.sent), 1)
        self.assertEqual((await ctx.storage.get("stats"))["received"], 2)


if __name__ == "__main__": unittest.main()
