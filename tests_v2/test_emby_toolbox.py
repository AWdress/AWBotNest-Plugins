import unittest
from unittest.mock import Mock, patch

from plugins_v2.emby_toolbox import core


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.content = b'{}'

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')

    def json(self):
        return self._payload


class EmbyClientLogicTests(unittest.TestCase):
    CFG = {'emby_server': 'https://emby.example', 'api_key': 'token', 'user_id': 'user-1'}

    @patch('plugins_v2.emby_toolbox.core.requests.get')
    def test_library_id_uses_virtual_folders(self, get):
        get.return_value = _Response([{'Name': '动画', 'ItemId': 'lib-1'}])
        self.assertEqual(core._get_library_id(self.CFG, '动画'), 'lib-1')
        url = get.call_args.args[0]
        self.assertTrue(url.endswith('/emby/Library/VirtualFolders'))

    @patch('plugins_v2.emby_toolbox.core.requests.get')
    def test_library_items_walk_nested_folders_and_request_metadata(self, get):
        get.side_effect = [
            _Response({'Items': [
                {'Id': 'folder-1', 'Type': 'Folder'},
                {'Id': 'movie-1', 'Type': 'Movie', 'Name': '电影', 'ProviderIds': {'Tmdb': '10'}},
            ]}),
            _Response({'Items': [
                {'Id': 'series-1', 'Type': 'Series', 'Name': '剧集', 'Genres': ['Drama']},
            ]}),
        ]
        items = core._get_lib_items(self.CFG, 'lib-1')
        self.assertEqual([i['Id'] for i in items], ['movie-1', 'series-1'])
        params = get.call_args_list[0].kwargs['params']
        self.assertEqual(params['Recursive'], 'false')
        self.assertIn('GenreItems', params['Fields'])
        self.assertIn('ProviderIds', params['Fields'])

    @patch('plugins_v2.emby_toolbox.core.requests.post')
    def test_update_item_sends_json_and_reqformat(self, post):
        post.return_value = _Response({}, status=204)
        core._update_item(self.CFG, {'Id': 'item-1', 'Name': '标题'})
        self.assertEqual(post.call_args.kwargs['json']['Id'], 'item-1')
        self.assertEqual(post.call_args.kwargs['params']['reqformat'], 'json')


if __name__ == '__main__':
    unittest.main()
