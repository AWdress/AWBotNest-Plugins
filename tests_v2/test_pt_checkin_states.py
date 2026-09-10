import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from plugins_v2.pt_multi_checkin import core


class PTCheckinStateTests(unittest.TestCase):
    def test_ourbits_generic_home_navigation_is_not_signed_state(self):
        text = '首页 论坛 种子 控制面板 用户详情'
        self.assertIsNone(core._site_result_state(text, 'ourbits.club', confirmed=True))

    def test_ourbits_explicit_signed_marker_is_accepted(self):
        state = core._site_result_state('今日已签到，已连续签到 10 天', 'ourbits.club', confirmed=True)
        self.assertEqual(state, ('already', '今天已经签到'))

    def test_audiences_reads_turnstile_get_response_token(self):
        class Locator:
            def __init__(self, selector, page):
                self.selector = selector
                self.page = page

            def count(self):
                return 1 if self.selector in ("#attendance-form", "#attendance-form .cf-turnstile") else 0

            def inner_text(self, timeout=None):
                return self.page.texts.pop(0)

        class Page:
            def __init__(self):
                self.texts = ["等待验证", "今日已签到"]
                self.frames = []
                self.scripts = []

            def locator(self, selector):
                return Locator(selector, self)

            def content(self):
                return "<form id='attendance-form'><div class='cf-turnstile'></div></form>"

            def evaluate(self, script):
                self.scripts.append(script)
                if "const names" in script:
                    return {"token": "signed-token", "source": "turnstile.getResponse"}
                return None

            def wait_for_timeout(self, milliseconds):
                return None

        page = Page()
        context = SimpleNamespace(log=MagicMock())

        result = core._audiences_turnstile_checkin(page, context)

        self.assertEqual(result["status"], "already")
        self.assertTrue(any("turnstile.getResponse" in script for script in page.scripts))
        self.assertTrue(context.log.info.called)


if __name__ == '__main__':
    unittest.main()
