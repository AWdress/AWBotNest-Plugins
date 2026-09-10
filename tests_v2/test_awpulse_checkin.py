import unittest

from plugins_v2.awpulse._core.checkin_state import checkin_state


class AWPulseCheckinStateTests(unittest.TestCase):
    def test_reads_real_unsigned_button(self):
        html = '<a class="ddpc_sign_btn_grey">今日未签到，点击签到</a>'
        self.assertEqual(checkin_state(html), 'unsigned')

    def test_reads_real_signed_button(self):
        html = '<a class="ddpc_sign_btn">今日已签到</a>'
        self.assertEqual(checkin_state(html), 'signed')

    def test_does_not_treat_statistics_as_signed(self):
        html = '<div class="stats">今日已签到 31842 人</div>'
        self.assertEqual(checkin_state(html), 'unknown')


if __name__ == '__main__':
    unittest.main()
