from __future__ import annotations

import asyncio
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from awbotnest.config import Settings
from awbotnest.context import PluginContext
from awbotnest.routing import PluginRoutes
from awbotnest.scheduler import PluginScheduler
from awbotnest.services import PlatformServices
from awbotnest.sessions import SessionManager

import plugins_v2.auto_changename as auto_changename
import plugins_v2.bomb_game as bomb_game
import plugins_v2.human_lottery as human_lottery
import plugins_v2.transfer as transfer
import plugins_v2.transfer.core as transfer_core
from plugins_v2.bomb_game.state import GameStateManager


class Log:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class MemoryStorage:
    def __init__(self, values=None, delay=0):
        self.values = copy.deepcopy(values or {})
        self.delay = delay
        self.active_writes = 0
        self.max_active_writes = 0

    async def items(self):
        return copy.deepcopy(self.values)

    async def get(self, key, default=None):
        return copy.deepcopy(self.values.get(key, default))

    async def set(self, key, value):
        self.active_writes += 1
        self.max_active_writes = max(self.max_active_writes, self.active_writes)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            self.values[key] = copy.deepcopy(value)
        finally:
            self.active_writes -= 1

    async def delete(self, key):
        self.values.pop(key, None)


class StateContext:
    def __init__(self, storage=None, instance="test"):
        self.config = {}
        self.storage = storage or MemoryStorage()
        self.sessions = SessionManager("bomb_game", instance)
        self.log = Log()
        self.tasks = []

    def create_task(self, awaitable, **kwargs):
        task = asyncio.create_task(awaitable, name=kwargs.get("name"))
        self.tasks.append(task)
        return task


class TelegramClient:
    async def get_entity(self, value):
        return SimpleNamespace(id=value, first_name="玩家", last_name=None)


class NativeReferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_human_lottery_invalid_create_reply_is_cleaned_up(self):
        class Message:
            def __init__(self, text, mid=10):
                self.raw_text = text; self.text = text; self.id = mid; self.chat_id = -1001
                self.deleted = False
            async def delete(self): self.deleted = True
        class Client:
            def __init__(self): self.sent = []
            async def send_message(self, chat_id, text, **kwargs):
                self.sent.append(text); return Message(text, 20 + len(self.sent))
        class Context:
            def __init__(self):
                self.config = {"delete_commands": True, "participation_reply_delete": 0}
                self.storage = MemoryStorage(); self.log = Log(); self.handlers = []; self.tasks = []
            def on_message(self, **kwargs):
                return lambda fn: (self.handlers.append(fn) or fn)
            def on_api(self, *args, **kwargs): return lambda fn: fn
            def create_task(self, awaitable, **kwargs):
                task = asyncio.create_task(awaitable, name=kwargs.get("name")); self.tasks.append(task); return task
            async def notify(self, *args, **kwargs): pass
        class Event:
            is_group = True; chat_id = -1001
            def __init__(self, message, client): self.message = message; self.client = client
            async def get_chat(self): return SimpleNamespace(id=self.chat_id, title="测试群")
            async def get_sender(self): return SimpleNamespace(id=1, first_name="测试")
        ctx = Context(); await human_lottery.setup(ctx)
        command = Message("创建抽奖 1000魔力 3 10分钟")
        client = Client(); await ctx.handlers[0](Event(command, client))
        self.assertTrue(command.deleted)
        self.assertEqual(len(client.sent), 1)
        await asyncio.gather(*ctx.tasks, return_exceptions=True)

    async def test_transfer_ssd_telethon_rows_are_clickable(self):
        class Context:
            def __init__(self):
                self.config = {"ssd_click_mode": "once"}; self.storage = MemoryStorage(); self.kv = self.storage
                self.log = Log(); self.handlers = []; self.cleanups = []
            def on_message(self, **kwargs): return lambda fn: (self.handlers.append(fn) or fn)
            def on_edited_message(self, **kwargs): return lambda fn: fn
            def on_api(self, *args, **kwargs): return lambda fn: fn
            def add_cleanup(self, fn): self.cleanups.append(fn)
        class Message:
            def __init__(self, text, reply=None, is_self=False):
                self.text = text; self.raw_text = text; self.caption = ""; self.chat_id = -1002014253433
                self.id = 30; self.reply_to_msg_id = 29; self._reply = reply
                self._is_self = is_self
                self.reply_markup = SimpleNamespace(rows=[SimpleNamespace(buttons=[SimpleNamespace(text="确认")])])
                self.clicked = []
            async def get_reply_message(self): return self._reply
            async def get_sender(self): return SimpleNamespace(id=1 if self._is_self else 2, is_self=self._is_self)
            async def click(self, **kwargs): self.clicked.append(kwargs)
        class Event:
            is_group = True
            def __init__(self, message): self.message = message; self.client = SimpleNamespace()
            @property
            def chat_id(self): return self.message.chat_id
            async def get_sender(self): return await self.message.get_sender()
            async def get_reply_message(self): return await self.message.get_reply_message()
        reply = Message("+100", is_self=True)
        message = Message("请确认你的转账", reply)
        ctx = Context(); await transfer.setup(ctx)
        handler = next(fn for fn in ctx.handlers if fn.__name__ == "ssd_confirm_click")
        await handler(Event(message))
        self.assertEqual(message.clicked, [{"x": 0, "y": 0}])

    async def test_transfer_rich_updates_expose_message_id_for_cleanup(self):
        update = SimpleNamespace(message=SimpleNamespace(id=77))
        updates = SimpleNamespace(updates=[update])
        self.assertEqual(transfer_core._sent_message_id(updates), 77)
        self.assertEqual(transfer_core._sent_message_id({"ok": True, "result": {"message_id": 88}}), 88)

    async def test_auto_changename_native_scheduler_and_telethon_request(self):
        class User:
            def __init__(self):
                self.requests = []

            async def __call__(self, request):
                self.requests.append(request)

        class Context:
            config = {"interval_min": 3, "name_format": "{H}:{M}", "name_field": "both"}
            log = Log()

            def __init__(self):
                self.users = [User()]
                self.jobs = []

            def schedule_interval(self, name, callback, *, seconds):
                self.jobs.append((name, callback, seconds))

        context = Context()
        await auto_changename.setup(context)
        self.assertEqual(context.jobs[0][2], 180)
        await context.jobs[0][1]()
        request = context.users[0].requests[0]
        self.assertTrue(request.first_name)
        self.assertTrue(request.last_name)
        await auto_changename.teardown(context)

    async def test_bomb_game_lifecycle_participation_guess_and_recovery(self):
        storage = MemoryStorage()
        context = StateContext(storage)
        state = GameStateManager(context)
        await state.initialize()
        client = TelegramClient()

        self.assertTrue(await state.start_game(client, -1001, 80, 1))
        self.assertFalse(await state.start_game(client, -1001, 70, 1))
        self.assertTrue(await state.add_pending_participant(-1001, 10, 888, 101))
        self.assertFalse(await state.add_pending_participant(-1001, 10, 888, 102))
        self.assertTrue(state.has_pending_participation(-1001, 10))
        self.assertTrue(await state.confirm_participation(-1001, 10))
        self.assertEqual(state.get_pool_info(-1001)["amount"], 888)
        self.assertEqual(state.calculate_pool_reward(-1001), (444, 444))

        self.assertTrue(await state.add_pending_participant(-1001, 11, 888, 103))
        self.assertTrue(await state.confirm_participation(-1001, 11))
        game = state.get_game_info(-1001)
        game["game_phase"] = "playing"
        game["dynamic_mode"] = False
        game["explosion_scenario"] = "last_1"

        low = await state.evaluate_guess(-1001, 10, 20)
        self.assertEqual(low["result"], "too_low")
        self.assertGreater(low["range"][0], 20)
        cooldown = await state.evaluate_guess(-1001, 10, 30)
        self.assertEqual(cooldown["status"], "cooldown")
        high = await state.evaluate_guess(-1001, 11, 90)
        self.assertEqual(high["result"], "too_high")

        self.assertTrue(await state.add_pending_participant(-1001, 12, 888, 104))
        self.assertTrue(await state.confirm_participation(-1001, 12))
        exploded = await state.evaluate_guess(-1001, 12, 80)
        self.assertEqual(exploded["status"], "explode")
        duplicate = await state.evaluate_guess(-1001, 11, 80)
        self.assertEqual(duplicate["status"], "inactive")
        self.assertTrue(await state.release_settlement(-1001))
        retried = await state.evaluate_guess(-1001, 12, 80)
        self.assertEqual(retried["status"], "explode")

        recovered_context = StateContext(storage, "recovered")
        recovered = GameStateManager(recovered_context)
        await recovered.initialize()
        self.assertEqual(recovered.get_pool_info(-1001)["amount"], 2664)
        self.assertTrue(await state.end_game(-1001, 12))
        self.assertFalse(state.is_game_active(-1001))

        self.assertTrue(await state.start_game(client, -1003, 70, 3, continuous=True))
        self.assertTrue(state.get_game_info(-1003)["continuous"])
        self.assertTrue(await state.add_pending_participant(-1003, 13, 888, 105))
        self.assertTrue(await state.confirm_participation(-1003, 13))
        state.state["-1003"]["game_phase"] = "playing"
        moved = await state.evaluate_guess(-1003, 13, 10)
        self.assertEqual(moved["status"], "accepted")
        self.assertGreater(state.get_game_info(-1003)["adjustment_count"], 0)

        await context.sessions.close()
        await recovered_context.sessions.close()

    async def test_bomb_setup_close_reload_has_no_duplicate_handlers_or_tasks(self):
        class HandlerClient:
            def __init__(self):
                self.handlers = []

            def is_connected(self):
                return True

            def add_event_handler(self, callback, builder):
                self.handlers.append((callback, builder))

            def remove_event_handler(self, callback, builder):
                self.handlers.remove((callback, builder))

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            scheduler = PluginScheduler()
            settings = Settings(api_id=1, api_hash="test")
            client = HandlerClient()
            accounts = SimpleNamespace(
                users={"user": client}, bots={},
                clients_for_scope=lambda scope, bot_id: [client],
                choose_bot=lambda bot_id: None,
            )
            patchers = [
                patch("awbotnest.services.DATA_DIR", root),
                patch("awbotnest.context.DATA_DIR", root),
                patch("awbotnest.storage.DATA_DIR", root),
            ]
            for item in patchers:
                item.start()
            try:
                services = PlatformServices(settings)
                first = PluginContext("bomb_game", "user", accounts, scheduler, settings,
                                      services, PluginRoutes(), SimpleNamespace())
                await bomb_game.setup(first)
                self.assertEqual(len(client.handlers), 3)
                await first.close()
                self.assertEqual(client.handlers, [])
                self.assertEqual(first.governor.background_tasks("bomb_game"), 0)

                second = PluginContext("bomb_game", "user", accounts, scheduler, settings,
                                       services, PluginRoutes(), SimpleNamespace())
                await bomb_game.setup(second)
                self.assertEqual(len(client.handlers), 3)
                await second.close()
                self.assertEqual(client.handlers, [])
                self.assertEqual(second.governor.background_tasks("bomb_game"), 0)
            finally:
                scheduler.stop()
                for item in reversed(patchers):
                    item.stop()
    async def test_different_chat_storage_runs_concurrently(self):
        storage = MemoryStorage(delay=0.03)
        context = StateContext(storage, "parallel")
        state = GameStateManager(context)
        await state.initialize()
        client = TelegramClient()
        for chat_id, user_id in ((-1, 1), (-2, 2)):
            await state.start_game(client, chat_id, 90, user_id)
            await state.add_pending_participant(chat_id, user_id, 888, user_id)
            await state.confirm_participation(chat_id, user_id)
            state.state[str(chat_id)]["game_phase"] = "playing"
            state.state[str(chat_id)]["dynamic_mode"] = False

        results = await asyncio.gather(
            state.evaluate_guess(-1, 1, 20), state.evaluate_guess(-2, 2, 30),
        )
        self.assertEqual([item["status"] for item in results], ["accepted", "accepted"])
        self.assertGreaterEqual(storage.max_active_writes, 2)
        await context.sessions.close()


if __name__ == "__main__":
    unittest.main()
