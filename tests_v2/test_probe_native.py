import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from plugins_v2.probe import core


class ProbeNativeTests(unittest.IsolatedAsyncioTestCase):
    def test_report_uses_telethon_fields_and_registration_syntax(self):
        button = SimpleNamespace(text="确认", data=b"ok:1", url=None)
        message = SimpleNamespace(
            id=9,
            chat_id=-100123,
            sender_id=42,
            raw_text="测试正文",
            message="测试正文",
            entities=[],
            media=SimpleNamespace(),
            grouped_id=7788,
            file=SimpleNamespace(name="a.jpg", mime_type="image/jpeg", size=10),
            buttons=[[button]],
            is_private=False,
            is_group=True,
            is_channel=True,
            outgoing=False,
            date=None,
            edit_date=None,
            views=None,
            author_signature=None,
            reply_to_msg_id=None,
            forward=None,
            action=None,
            via_bot_id=None,
        )
        chat = SimpleNamespace(title="测试群", username="group", verified=False)
        sender = SimpleNamespace(
            id=42, bot=False, username="user", first_name="U", last_name=None,
        )

        report = core._build_report(message, "测试", 300, chat=chat, sender=sender)

        self.assertIn("message.grouped_id", report)
        self.assertIn("@ctx.on_message(incoming=True", report)
        self.assertIn("@ctx.on_callback(pattern=rb", report)
        self.assertNotIn("ctx.filters", report)
        self.assertNotIn("media_group_id", report)

    async def test_delivery_uses_telethon_send_file(self):
        client = SimpleNamespace(send_file=AsyncMock())
        context = SimpleNamespace(bot=None, settings=None)

        destination = await core._deliver(context, client, "内容", "测试")

        self.assertEqual(destination, "收藏夹（Bot 不可用回退）")
        client.send_file.assert_awaited_once()
        self.assertEqual(client.send_file.await_args.args[0], "me")
