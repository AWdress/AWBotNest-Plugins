import unittest
from types import SimpleNamespace

from plugins_v2.transfer import _sites


class TransferNativeTests(unittest.TestCase):
    def test_direction_uses_preloaded_telethon_reply_chain(self):
        mine = SimpleNamespace(_v2_sender=SimpleNamespace(is_self=True))
        other = SimpleNamespace(
            _v2_sender=SimpleNamespace(is_self=False),
            _v2_reply=mine,
        )
        incoming = SimpleNamespace(_v2_reply=other)

        self.assertEqual(_sites.detect_direction(incoming), "in")
        self.assertIs(_sites.counterparty_message(incoming, "in"), other)

        outgoing_reply = SimpleNamespace(
            _v2_sender=SimpleNamespace(is_self=True),
            _v2_reply=other,
        )
        outgoing = SimpleNamespace(_v2_reply=outgoing_reply)
        self.assertEqual(_sites.detect_direction(outgoing), "out")
        self.assertIs(_sites.counterparty_message(outgoing, "out"), other)
