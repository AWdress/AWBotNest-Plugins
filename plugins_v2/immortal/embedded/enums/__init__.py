from enum import Enum, unique


@unique
class DownloadClientEnum(Enum):
    QBITTORRENT = "Downloader.qbittorrent"
    TRANSMISSION = "Downloader.transmission"
    THUNDER = "Downloader.thunder"
    CLOUDDRIVE = "Downloader.clouddrive"


@unique
class PusherEnum(Enum):
    WECHAT = "Notification.wechat"
    TELEGRAM = "Notification.telegram"
    DISCORD = "Notification.discord"


@unique
class SystemConfigEnum(Enum):
    SYSTEM_CONFIG = "SystemConfig"
    PAGE_AGENT_CONFIG = "PageAgentConfig"
    TG_BOT_CONFIG = "TGBotConfig"
    DISCORD_BOT_CONFIG = "DiscordBotConfig"
    WECOM_BOT_CONFIG = "WeComBotConfig"
    SUBSCRIBE_PREFERENCE_CONFIG = "SubscribePreferenceConfig"
    UPDATE_CHECK_NOTIFY_STATE = "UpdateCheckNotifyState"


@unique
class SubscribeStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELED = "canceled"
    COMPLETED = "completed"


@unique
class MediaServerEnum(Enum):
    EMBY = "MediaServer.emby"
    JELLYFIN = "MediaServer.jellyfin"
    PLEX = "MediaServer.plex"
    ZSPACE = "MediaServer.zspace"
