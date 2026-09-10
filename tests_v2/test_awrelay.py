import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from plugins_v2.awrelay import core


class _Storage:
    async def items(self):
        return []

    async def set(self, key, value):
        return None


class _HeldTask:
    def __init__(self, coroutine):
        self.coroutine = coroutine

    def add_done_callback(self, callback):
        return None


class _Context:
    def __init__(self, config=None):
        self.config = config or {}
        self.storage = _Storage()
        self.bot = None
        self.log = MagicMock()
        self.message_handlers = []
        self.held_tasks = []

    def add_cleanup(self, callback):
        self.cleanup = callback

    def on_api(self, *args, **kwargs):
        return lambda callback: callback

    def on_message(self, *args, **kwargs):
        def register(callback):
            self.message_handlers.append(callback)
            return callback
        return register

    def on_callback(self, *args, **kwargs):
        return lambda callback: callback

    def schedule(self, *args, **kwargs):
        return None

    def create_task(self, coroutine, **kwargs):
        held = _HeldTask(coroutine)
        self.held_tasks.append(held)
        return held


class AWRelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        for messages in core._media_groups.values():
            messages.clear()
        core._media_groups.clear()
        for context in getattr(self, "contexts", []):
            for task in context.held_tasks:
                task.coroutine.close()

    async def _setup(self, config=None):
        context = _Context(config)
        self.contexts = getattr(self, "contexts", []) + [context]
        await core.setup(context)
        return context

    async def test_broadcast_channel_is_not_treated_as_private_user(self):
        context = await self._setup({"enabled": True, "group_id": "-100123"})
        event = SimpleNamespace(
            is_private=False,
            is_group=False,
            get_sender=AsyncMock(side_effect=AssertionError("不应读取频道发送者")),
        )

        await context.message_handlers[0](event)

        event.get_sender.assert_not_awaited()

    async def test_telethon_grouped_id_starts_album_aggregation(self):
        context = await self._setup({
            "enabled": True,
            "group_id": "-100123",
            "captcha_enabled": False,
        })
        user = SimpleNamespace(id=42)
        message = SimpleNamespace(
            id=7,
            chat_id=42,
            grouped_id=9988,
            raw_text="",
        )
        event = SimpleNamespace(
            is_private=True,
            client=object(),
            message=message,
            get_sender=AsyncMock(return_value=user),
        )

        await context.message_handlers[0](event)

        self.assertEqual(core._media_groups["42:9988"], [message])
        self.assertEqual(len(context.held_tasks), 1)

    def test_target_id_and_topic_reply_are_telethon_compatible(self):
        self.assertEqual(core._target_id({"group_id": " -1003709604884 "}), -1003709604884)
        self.assertEqual(core._target_id({"group_id": "not-an-id"}), 0)
        message = SimpleNamespace(reply_to=SimpleNamespace(reply_to_top_id=123, reply_to_msg_id=99))
        self.assertEqual(core._thread_id(message), 123)


if __name__ == "__main__":
    unittest.main()
