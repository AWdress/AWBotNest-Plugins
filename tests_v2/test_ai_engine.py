import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from plugins_v2.ai._engine import classify_error, generate


def _decode_error():
    return json.JSONDecodeError("Expecting value", "", 0)


class AIEngineTests(unittest.IsolatedAsyncioTestCase):
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
