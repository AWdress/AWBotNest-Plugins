import unittest
from pathlib import Path

from awbotnest.plugin_runtime import PluginScanner
from plugins_v2 import msg_forward


class _Message:
    def __init__(self, message_id, text, grouped_id=None):
        self.id = message_id
        self.raw_text = text
        self.grouped_id = grouped_id
        self.media = None
        self.photo = self.video = self.gif = None
        self.document = self.audio = self.voice = None

    async def get_sender(self):
        return None


class _Entity:
    id = 123
    title = '来源群'


class _Client:
    def __init__(self):
        self.forwarded = []
        self.messages = [_Message(3, '相册', 99), _Message(2, '', 99), _Message(1, '普通')]

    async def get_entity(self, source):
        return _Entity()

    async def forward_messages(self, target, messages):
        self.forwarded.append((target, [message.id for message in messages]))

    def iter_messages(self, source, limit):
        async def generate():
            for message in self.messages[:limit]:
                yield message
        return generate()


class _Log:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


class MessageForwardBackfillTests(unittest.IsolatedAsyncioTestCase):
    def test_final_version_is_statically_scannable(self):
        metadata = PluginScanner.metadata(Path(msg_forward.__file__))

        self.assertEqual(metadata["version"], "2.0.4")
        self.assertIn("backfill_limit", metadata["config_schema"])
        self.assertTrue(metadata["changelog"].startswith("v2.0.4"))

    async def test_backfill_sends_oldest_first_groups_album_and_deduplicates(self):
        client = _Client()
        sent = set()

        async def resolve(client, value):
            return str(value)

        rule = {'source': '-100123', 'targets': '-100456'}
        result = await msg_forward._backfill(client, [rule], 100, sent, _Log(), resolve)
        self.assertEqual(result, (2, 0))
        self.assertEqual(client.forwarded, [(-100456, [1]), (-100456, [2, 3])])

        result = await msg_forward._backfill(client, [rule], 100, sent, _Log(), resolve)
        self.assertEqual(result, (0, 2))
        self.assertEqual(len(client.forwarded), 2)


if __name__ == '__main__':
    unittest.main()
