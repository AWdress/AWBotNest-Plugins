import re
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from plugins_v2.zhuque_lottery import core


class _Store:
    def __init__(self):
        self.records = []

    def add_record(self, value):
        self.records.append(value)


class ZhuqueYdxTests(unittest.IsolatedAsyncioTestCase):
    async def test_reveal_uses_preloaded_telethon_reply(self):
        reply = SimpleNamespace(text="下注记录")
        message = SimpleNamespace(
            text="已结算: 结果为 4 大",
            _v2_reply=reply,
        )
        state = {
            "bet_models": {},
            "big_count": 0,
            "small_count": 0,
            "bet_count": 0,
        }
        store = _Store()
        context = SimpleNamespace(
            config={"ydx_dice_reveal": True},
            log=MagicMock(),
        )
        client = SimpleNamespace(me=SimpleNamespace(id=123))
        match = re.search(r"已结算: 结果为 (\d+) (.)", message.text)

        def winner_name(value, _me_id):
            return "测试用户" if value is reply else None

        with (
            patch.object(core._ydx, "listof_winners_check", side_effect=winner_name),
            patch.object(core._ydx, "extract_bet_info", return_value=("Big", 500)),
            patch.object(core._ydx, "extract_winner_amount", return_value=0),
        ):
            await core._ydx_reveal(context, state, store, client, message, match)

        self.assertEqual(store.records[0]["bet_side"], "Big")
        self.assertEqual(store.records[0]["bet_amount"], 500.0)
        self.assertEqual(state["bet_count"], 1)
