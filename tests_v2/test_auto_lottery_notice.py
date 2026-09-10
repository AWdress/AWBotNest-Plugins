import unittest
from types import SimpleNamespace

from plugins_v2.auto_lottery.core import _participation_success_text


class AutoLotteryNoticeTests(unittest.TestCase):
    def test_success_notice_uses_explicit_chat_entity(self):
        message = SimpleNamespace(chat_id=-100123, link="https://t.me/c/123/9")
        chat = SimpleNamespace(title="抽奖测试群")

        text = _participation_success_text(
            "lottery-id", message, chat, {"prize": "1000 魔力"}, "冲鸭"
        )

        self.assertIn("抽奖测试群", text)
        self.assertIn("1000 魔力", text)
        self.assertIn("冲鸭", text)

    def test_success_notice_falls_back_to_chat_id(self):
        message = SimpleNamespace(chat_id=-100456)

        text = _participation_success_text(
            "lottery-id", message, None, {"prize": "奖品"}, "参与"
        )

        self.assertIn("-100456", text)


if __name__ == "__main__":
    unittest.main()
