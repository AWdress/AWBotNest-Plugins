import unittest
from unittest.mock import patch

from plugins_v2.auto_subscribe import core


class _Client:
    def __init__(self):
        self.added = []

    def local_library_filter(self, status):
        return {'data': [
            {'tmdb_id': '1', 'media_type': 'tv', 'title': '已有一'},
            {'tmdbId': '2', 'mediaType': 'tv', 'title': '已有二'},
            {'tmdb_id': '3', 'media_type': 'tv', 'title': '新增三'},
            {'tmdb_id': '4', 'media_type': 'tv', 'title': '新增四'},
        ]}

    def list_subscriptions(self):
        return [
            {'tmdb_id': '1', 'media_type': 'tv'},
            {'tmdbId': '2', 'mediaType': 'tv'},
        ]

    def add(self, tmdb_id, media_type, season=None):
        self.added.append(str(tmdb_id))
        return True, 'ok'


class NextFindMissingSubscriptionTests(unittest.TestCase):
    def test_existing_subscriptions_are_skipped_before_limit(self):
        client = _Client()
        cfg = {'auto_subscribe_missing_limit': 1}
        with patch.object(core, '_nf_client', return_value=client):
            stats, titles = core._subscribe_missing_round(cfg)
        self.assertEqual(client.added, ['3'])
        self.assertEqual(stats, {'checked': 4, 'added': 1, 'skipped': 2, 'failed': 0})
        self.assertEqual(titles, ['新增三(缺集)'])


if __name__ == '__main__':
    unittest.main()
