import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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


class _Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


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
        core._storage_state.clear()
        core._target_entities.clear()
        core._bot_api_targets.clear()
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

    async def test_uncached_target_entity_is_resolved_from_dialogs_once(self):
        target_id = -1004462559854
        entity = SimpleNamespace(id=4462559854, access_hash=987654321)
        input_peer = SimpleNamespace(channel_id=4462559854, access_hash=987654321)

        class _Client:
            def __init__(self):
                self.dialog_scans = 0
                self.input_requests = []

            async def get_entity(self, peer):
                raise ValueError(
                    "Could not find the input entity for "
                    "PeerChannel(channel_id=4462559854) (PeerChannel)"
                )

            async def iter_dialogs(self, limit=None):
                self.dialog_scans += 1
                self.asserted_limit = limit
                yield SimpleNamespace(entity=SimpleNamespace(id=1))
                yield SimpleNamespace(entity=entity)

            async def get_input_entity(self, peer):
                self.input_requests.append(peer)
                return input_peer

        client = _Client()
        with patch.object(
            core.utils,
            "get_peer_id",
            side_effect=lambda candidate: (
                target_id if candidate is entity else int(getattr(candidate, "id", 0))
            ),
        ):
            resolved = await core._resolve_target_entity(client, target_id)
            cached = await core._resolve_target_entity(client, target_id)
            peer = await core._target_peer(client, target_id)

        self.assertIs(resolved, entity)
        self.assertIs(cached, entity)
        self.assertIs(peer, input_peer)
        self.assertEqual(client.dialog_scans, 1)
        self.assertIsNone(client.asserted_limit)
        self.assertEqual(client.input_requests, [entity, entity])

    async def test_bot_api_fallback_handles_uncached_private_forum(self):
        target_id = -1004462559854

        class _Client:
            def is_connected(self):
                return True

            async def get_entity(self, peer):
                raise ValueError("Could not find the input entity for PeerChannel")

            async def iter_dialogs(self, limit=None):
                if False:
                    yield None

        client = _Client()
        context = _Context({"enabled": True, "group_id": str(target_id)})
        context.bot = client
        context.bot_id = ""
        context.accounts = SimpleNamespace(bots={"default": client})
        context.settings = SimpleNamespace(
            default_bot_id="default",
            bot_specs=lambda: [SimpleNamespace(id="default", token="123:secret")],
        )
        context.http = SimpleNamespace(post=AsyncMock(side_effect=[
            _Response({"ok": True, "result": {
                "id": target_id, "title": "中转论坛", "type": "supergroup", "is_forum": True,
            }}),
            _Response({"ok": True, "result": {"message_id": 88}}),
        ]))

        entity = await core._validate_target(context, context.config)
        sent = await core._copy_messages_to_topic(
            context, client, target_id, 66, [SimpleNamespace(id=7, chat_id=42)]
        )

        self.assertEqual(entity.title, "中转论坛")
        self.assertTrue(core._uses_bot_api(client, target_id))
        self.assertEqual(sent, [88])
        self.assertEqual(context.http.post.await_count, 2)
        copy_call = context.http.post.await_args_list[1]
        self.assertTrue(copy_call.args[0].endswith("/copyMessage"))
        self.assertEqual(copy_call.kwargs["json"], {
            "chat_id": target_id,
            "from_chat_id": 42,
            "message_id": 7,
            "message_thread_id": 66,
        })

    async def test_bot_api_fallback_creates_topic_and_intro(self):
        target_id = -1004462559854
        client = object()
        context = _Context({"enabled": True, "group_id": str(target_id)})
        context.bot = client
        context.bot_id = ""
        context.accounts = SimpleNamespace(bots={"default": client})
        context.settings = SimpleNamespace(
            default_bot_id="default",
            bot_specs=lambda: [SimpleNamespace(id="default", token="123:secret")],
        )
        context.http = SimpleNamespace(post=AsyncMock(side_effect=[
            _Response({"ok": True, "result": {"message_thread_id": 77}}),
            _Response({"ok": True, "result": {"message_id": 78}}),
        ]))
        self.contexts = getattr(self, "contexts", []) + [context]
        core._bot_api_targets.add(core._target_key(client, target_id))
        user = SimpleNamespace(id=42, first_name="测试", last_name="用户", username="tester")

        topic_id = await core._topic_for(context, client, user, context.config)

        self.assertEqual(topic_id, 77)
        create_call, intro_call = context.http.post.await_args_list
        self.assertTrue(create_call.args[0].endswith("/createForumTopic"))
        self.assertEqual(create_call.kwargs["json"]["chat_id"], target_id)
        self.assertTrue(create_call.kwargs["json"]["name"].endswith(" · 42"))
        self.assertTrue(intro_call.args[0].endswith("/sendMessage"))
        self.assertEqual(intro_call.kwargs["json"]["message_thread_id"], 77)


if __name__ == "__main__":
    unittest.main()
