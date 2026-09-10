import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from plugins_v2.ai._engine import classify_error, generate
from plugins_v2.ai.core import _edit_explanation


def _decode_error():
    return json.JSONDecodeError("Expecting value", "", 0)


class AIEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_explanation_explicitly_uses_html_and_escapes_content(self):
        message = SimpleNamespace(edit=AsyncMock(return_value="edited"))

        result = await _edit_explanation(
            message,
            "问题 <tag> & 内容",
            "回答 <script> & 内容",
        )

        self.assertEqual(result, "edited")
        message.edit.assert_awaited_once_with(
            "<b>消息解释</b>\n"
            "<blockquote><b>Q：</b> 问题 &lt;tag&gt; &amp; 内容</blockquote>\n"
            "<blockquote><b>A：</b> 回答 &lt;script&gt; &amp; 内容</blockquote>",
            parse_mode="html",
        )

    async def test_explanation_falls_back_to_unparsed_plain_text(self):
        message = SimpleNamespace(
            edit=AsyncMock(side_effect=[RuntimeError("HTML failed"), "plain"])
        )

        result = await _edit_explanation(message, "问题 <tag>", "回答 **text**")

        self.assertEqual(result, "plain")
        self.assertEqual(message.edit.await_count, 2)
        message.edit.assert_awaited_with(
            "解释\nQ: 问题 <tag>\n\nA: 回答 **text**",
            parse_mode=None,
        )

    async def test_empty_json_response_is_retried_once(self):
        ai = SimpleNamespace(chat=AsyncMock(side_effect=[_decode_error(), "重试成功"]))
        ctx = SimpleNamespace(ai=ai)

        with patch("plugins_v2.ai._engine.asyncio.sleep", new=AsyncMock()) as sleep:
            result = await generate(ctx, [{"role": "user", "content": "解释一下"}])

        self.assertEqual(result, "重试成功")
        self.assertEqual(ai.chat.await_count, 2)
        sleep.assert_awaited_once_with(1)

    async def test_repeated_invalid_json_becomes_actionable_error(self):
        ai = SimpleNamespace(chat=AsyncMock(side_effect=[_decode_error(), _decode_error()]))
        ctx = SimpleNamespace(ai=ai)

        with patch("plugins_v2.ai._engine.asyncio.sleep", new=AsyncMock()):
            with self.assertRaisesRegex(RuntimeError, "连续返回空响应或非 JSON") as raised:
                await generate(ctx, [{"role": "user", "content": "解释一下"}])

        self.assertIn("接口地址", classify_error(raised.exception))

    def test_json_decode_error_has_clear_message(self):
        message = classify_error(_decode_error())
        self.assertIn("空响应或非 JSON", message)


if __name__ == "__main__":
    unittest.main()
