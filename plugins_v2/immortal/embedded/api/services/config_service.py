"""Business settings only; host platform owns Bots, AI, authentication and updates."""
import json
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from ...core.config import config_manager
from ...enums import DownloadClientEnum, SystemConfigEnum, MediaServerEnum
from ...api.services import subscribe_preference_service
from ...models import Config
from ...modules.downloadclient.manager import downloadManager
from ...modules.mediaserver import mediaServerManager
from ...schemas.config import JsonPayload
from ...schemas.response import success

DOWNLOAD_KEYS = {item.value for item in DownloadClientEnum}
MEDIA_KEYS = {item.value for item in MediaServerEnum}
ALLOWED_KEYS = DOWNLOAD_KEYS | MEDIA_KEYS | {
    SystemConfigEnum.SYSTEM_CONFIG.value,
    SystemConfigEnum.SUBSCRIBE_PREFERENCE_CONFIG.value,
    'DashboardConfig',
}
SYSTEM_FIELDS = {'PROXY', 'FLARE_SOLVERR_URL', 'JAVDB_API_HOST'}
DASHBOARD_SECTIONS = {'download_dashboard', 'summary_cards', 'recent_release_subscribes',
                      'subscription_recommendations', 'movie_frequency_stats', 'category_cards'}


def _dashboard_config(payload):
    if set(payload) - {'sections'}:
        raise ValueError('首页配置仅支持栏目设置')
    if 'sections' not in payload:
        return {}
    sections = payload['sections']
    if not isinstance(sections, list) or len(sections) > 32:
        raise ValueError('首页栏目设置必须是列表，且不能超过 32 项')
    if any(not isinstance(section, str) or section not in DASHBOARD_SECTIONS for section in sections):
        raise ValueError('首页配置包含未知栏目')
    return {'sections': list(dict.fromkeys(sections))}


def _check_key(key):
    if key not in ALLOWED_KEYS:
        raise ValueError('此设置由 AWBotNest 平台管理，不能在插件中修改')


def _reload(key, payload):
    if key in DOWNLOAD_KEYS:
        downloadManager.reload(key, payload)
    elif key in MEDIA_KEYS:
        mediaServerManager.reload(key, payload)
    elif key == SystemConfigEnum.SYSTEM_CONFIG.value:
        config_manager.reload(payload)


def save_option(json_payload: JsonPayload, db: Session):
    key = json_payload.key
    _check_key(key)
    payload = json_payload.payload
    if not isinstance(payload, dict):
        raise ValueError('设置内容必须是对象')
    if key == SystemConfigEnum.SYSTEM_CONFIG.value:
        if set(payload) - SYSTEM_FIELDS:
            raise ValueError('系统设置仅支持代理、FlareSolverr 和 JavDB 地址')
        payload = {field: payload.get(field) for field in SYSTEM_FIELDS}
        for field, value in payload.items():
            if not value:
                continue
            parsed = urlsplit(str(value))
            schemes = {'http', 'https', 'socks5', 'socks5h'} if field == 'PROXY' else {'http', 'https'}
            if parsed.scheme not in schemes or not parsed.hostname:
                raise ValueError('系统配置中的地址格式无效')
    elif key == SystemConfigEnum.SUBSCRIBE_PREFERENCE_CONFIG.value:
        payload = subscribe_preference_service.normalize_subscribe_preference_config(payload)
    elif key == 'DashboardConfig':
        payload = _dashboard_config(payload)
    config = db.query(Config).filter(Config.key == key).first()
    if config is None:
        config = Config(key=key)
        db.add(config)
    config.content = json.dumps(payload, ensure_ascii=False)
    db.commit()
    _reload(key, payload)
    return success()


def get_option(key, db: Session):
    _check_key(key)
    config = db.query(Config).filter(Config.key == key).first()
    data = json.loads(str(config.content)) if config and config.content else {}
    if not isinstance(data, dict):
        data = {}
    if key == SystemConfigEnum.SUBSCRIBE_PREFERENCE_CONFIG.value:
        data = subscribe_preference_service.normalize_subscribe_preference_config(data)
    elif key == SystemConfigEnum.SYSTEM_CONFIG.value:
        data = {field: data.get(field) for field in SYSTEM_FIELDS}
    elif key == 'DashboardConfig':
        data = _dashboard_config(data)
    return success(data)


def delete_option(key, db: Session):
    _check_key(key)
    config = db.query(Config).filter(Config.key == key).first()
    if config:
        db.delete(config)
        db.commit()
    _reload(key, {})
    return success()


def list_all_downloader(db: Session):
    configs = db.query(Config).filter(Config.key.in_(DOWNLOAD_KEYS)).all()
    downloaders = []
    for config in configs:
        downloader = json.loads(str(config.content))
        if isinstance(downloader, dict) and downloader.get('save_paths'):
            downloader['id'] = config.key.replace('Downloader.', '')
            downloaders.append(downloader)
    return success(downloaders)
