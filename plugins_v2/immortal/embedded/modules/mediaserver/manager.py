"""Instance-scoped media-server adapters with lazy initialization."""
import importlib
import threading

from ...core.runtime import get_runtime
from ...enums import MediaServerEnum


class MediaServerManager:
    SERVERS = {
        MediaServerEnum.EMBY.value: ('.emby', 'EmbyMediaServer'),
        MediaServerEnum.JELLYFIN.value: ('.jellyfin', 'JellyfinMediaServer'),
        MediaServerEnum.PLEX.value: ('.plex', 'PlexMediaServer'),
        MediaServerEnum.ZSPACE.value: ('.zspace', 'ZSpaceMediaServer'),
    }

    def _state(self):
        runtime = get_runtime()
        if not hasattr(runtime, '_media_manager_state'):
            runtime._media_manager_state = {'configs': {}, 'clients': {}, 'lock': threading.RLock()}
        return runtime._media_manager_state

    @property
    def servers(self):
        state = self._state()
        with state['lock']:
            for name, config in state['configs'].items():
                if name not in state['clients'] and config.get('url'):
                    module, cls = self.SERVERS[name]
                    state['clients'][name] = getattr(importlib.import_module(module, __package__), cls)(dict(config))
            return list(state['clients'].values())

    def register(self, server):
        state = self._state()
        with state['lock']:
            state['clients'][server.name] = server

    def any_movie_exists_by_number(self, number):
        if not number:
            return False
        for server in self.servers:
            get_runtime().check_cancelled()
            # Errors propagate; callers must never treat an unreachable library as missing.
            if server.has_movie_by_number(number):
                return True
        return False

    def reload(self, name, config):
        if name not in self.SERVERS:
            raise ValueError('不支持的媒体服务器')
        state = self._state()
        with state['lock']:
            state['clients'].pop(name, None)
            state['configs'][name] = dict(config or {})

    def close(self):
        state = self._state()
        with state['lock']:
            state['clients'].clear()


mediaServerManager = MediaServerManager()
