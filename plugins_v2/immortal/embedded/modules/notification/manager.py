"""All notifications are delivered through the platform, never a second bot."""
from ...core.runtime import get_runtime


class PlatformNotifications:
    def send(self, message, title=None, **kwargs):
        return get_runtime().notify(message, title)

    def send_event(self, event, data):
        if not isinstance(data, dict):
            return False
        title = {'download': '下载已提交', 'movie_subscribe': '影片订阅',
                 'cast_subscribe': '演员订阅', 'general_subscribe': '综合订阅'}.get(event, 'Immortal 通知')
        content = '\n'.join(str(data[k]) for k in ('number', 'title', 'name') if data.get(k))
        return self.send(content or title, title=title)

    def reload(self, *args, **kwargs):
        raise ValueError("通知渠道请在平台中设置")


pushManager = PlatformNotifications()
