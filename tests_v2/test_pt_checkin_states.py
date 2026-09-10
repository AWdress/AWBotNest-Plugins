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

    def test_u2_rejected_answer_is_not_reported_as_success(self):
        self.assertEqual(
            core._u2_result_state('{"status":"error","message":"Wrong answer"}'),
            ("failed", "U2 未接受本次签到验证答案"),
        )

    def test_u2_json_success_receipt_is_recognized(self):
        self.assertEqual(
            core._u2_result_state('{"status":"success","message":"ok"}'),
            ("success", "签到成功"),
        )

    def test_u2_submission_uses_real_browser_click(self):
        class Submit:
            clicked = False

            def click(self, timeout=None):
                self.clicked = True
                self.timeout = timeout

        class Page:
            waited = []

            def wait_for_load_state(self, state, timeout=None):
                self.waited.append((state, timeout))

            def wait_for_timeout(self, milliseconds):
                self.waited.append(("timeout", milliseconds))

            def content(self):
                return "<p>签到成功</p>"

        page, submit = Page(), Submit()
        body = core._u2_submit_with_browser(page, submit)

        self.assertTrue(submit.clicked)
        self.assertEqual(submit.timeout, 15_000)
        self.assertEqual(body, "<p>签到成功</p>")


if __name__ == '__main__':
    unittest.main()
