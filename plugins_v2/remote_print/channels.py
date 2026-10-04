"""Read shared messaging channels without persisting platform credentials."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .wecom import normalize_api_base


class PlatformChannels:
    """Resolve the receiving application using the platform's channel choices."""

    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx

    def _channels(self) -> list[dict[str, Any]]:
        settings = getattr(self.ctx, "settings", None)
        channels = getattr(settings, "notification_channels", [])
        if not isinstance(channels, (list, tuple)):
            return []
        result = []
        for raw in channels:
            if not isinstance(raw, Mapping):
                continue
            nested = raw.get("config")
            # Match the platform notifier: top-level values override config.
            config = {**(nested if isinstance(nested, Mapping) else {}), **raw}
            result.append(config)
        return result

    def _route_ids(self) -> list[str]:
        settings = getattr(self.ctx, "settings", None)
        routing = getattr(settings, "bot_routing", {})
        plugin_id = str(getattr(self.ctx, "plugin_id", "remote_print") or "remote_print")
        routes = str(routing.get(plugin_id, "") or "") if isinstance(routing, Mapping) else ""
        return list(dict.fromkeys(part.strip() for part in routes.split(",") if part.strip()))

    def _applications(self) -> list[dict[str, Any]]:
        result = []
        for config in self._channels():
            if config.get("enabled") is False or config.get("type") not in {"wecom", "wechat"}:
                continue
            # A group robot can notify, but cannot receive application media.
            if config.get("url") or config.get("webhook"):
                continue
            corp_id = str(config.get("corpid") or "").strip()
            secret = str(config.get("secret") or "").strip()
            channel_id = str(config.get("id") or "").strip()
            try:
                agent_id = int(config.get("agentid") or 0)
            except (ValueError, TypeError, OverflowError):
                continue
            if (not channel_id or not corp_id or not secret or max(len(corp_id), len(secret)) > 512
                    or isinstance(config.get("agentid"), bool) or not 0 < agent_id < 2 ** 31):
                continue
            result.append({**config, "id": channel_id, "corpid": corp_id,
                           "secret": secret, "agentid": agent_id})
        return result

    @staticmethod
    def _canonical(config: Mapping[str, Any]) -> dict[str, Any]:
        result = {
            "wecom_channel_id": config["id"],
            "wecom_channel_name": str(config.get("name") or config["id"]),
            "wecom_corp_id": config["corpid"],
            "wecom_agent_id": config["agentid"],
            "wecom_secret": config["secret"],
            "wecom_api_base": normalize_api_base(config.get("proxy")),
            "wecom_callback_enabled": config.get("callback_enabled") is True,
            "wecom_callback_users": str(config.get("callback_users") or ""),
        }
        token = config.get("callback_token")
        aes_key = config.get("callback_aes_key")
        if token:
            result["wecom_token"] = str(token).strip()
        if aes_key:
            result["wecom_encoding_aes_key"] = str(aes_key).strip()
        return result

    def wecom_config(self) -> dict[str, Any]:
        """Return the selected platform app, or an empty mapping if absent.

        Multiple applications require an explicit platform route or default.
        No plugin settings are consulted, including old copies of credentials.
        """
        applications = self._applications()
        channels = self._channels()
        for channel_id in self._route_ids():
            matches = [item for item in channels if str(item.get("id") or "") == channel_id]
            if len(matches) > 1:
                raise ValueError("平台企业微信渠道 ID 重复，请检查平台通知设置")
            if not matches or matches[0].get("type") not in {"wechat", "wecom"}:
                continue
            if matches[0].get("enabled") is False:
                raise ValueError("平台绑定的企业微信渠道已停用")
            complete = next((item for item in applications if item["id"] == channel_id), None)
            if complete is None:
                raise ValueError("平台绑定的企业微信自建应用配置不完整，群机器人不能接收文件")
            return self._canonical(complete)
        if not applications:
            return {}
        defaults = [item for item in applications if item.get("is_default")]
        if len(defaults) == 1:
            return self._canonical(defaults[0])
        if len(defaults) > 1 or len(applications) > 1:
            raise ValueError("平台存在多个企业微信应用，请在平台为远程打印绑定渠道或设置默认渠道")
        return self._canonical(applications[0])

    def telegram_bot_id(self) -> str:
        """Choose one platform Bot, without substituting another for a bound Bot."""
        settings = getattr(self.ctx, "settings", None)
        channels = self._channels()
        specs_getter = getattr(settings, "bot_specs", None)
        specs = specs_getter() if callable(specs_getter) else []
        known_ids = {str(getattr(spec, "id", "") or "") for spec in specs}

        def bot_id(config: Mapping[str, Any]) -> str:
            selected = str(config.get("bot_id") or config.get("id") or "").strip()
            if config.get("enabled") is False:
                raise ValueError("平台绑定的 Telegram 渠道已停用")
            if not selected or selected not in known_ids:
                raise ValueError("平台绑定的 Telegram Bot 配置不存在")
            return selected

        selected = ""
        for channel_id in self._route_ids():
            matches = [item for item in channels if str(item.get("id") or "") == channel_id]
            if len(matches) > 1:
                raise ValueError("平台通知渠道 ID 重复，请检查平台通知设置")
            if matches:
                if str(matches[0].get("type") or "telegram") != "telegram":
                    continue
                selected = bot_id(matches[0])
                break
            if channel_id in known_ids:
                selected = channel_id
                break
            raise ValueError("平台绑定的通知渠道不存在")
        if not selected:
            defaults = [item for item in channels
                        if item.get("is_default") and str(item.get("type") or "telegram") == "telegram"]
            if len(defaults) > 1:
                raise ValueError("平台存在多个默认 Telegram 渠道，请检查平台通知设置")
            if defaults:
                selected = bot_id(defaults[0])
            else:
                # ctx.bot_id is our last registration, not a persisted route.
                # Re-read the platform default so a changed default takes effect.
                selected = str(getattr(settings, "default_bot_id", "") or "default")
                if selected not in known_ids:
                    raise ValueError("平台 Telegram Bot 配置不存在")
        getter = getattr(self.ctx, "get_bot", None)
        if callable(getter):
            bot = getter(selected)
            if bot is None:
                raise ValueError("平台选定的 Telegram Bot 当前不可用")
            connected = getattr(bot, "is_connected", None)
            if callable(connected) and not connected():
                raise ValueError("平台选定的 Telegram Bot 当前不可用")
        return selected
