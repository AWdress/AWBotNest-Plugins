"""Native print cards through the selected platform application's HTTP service.

Incoming messages and media are handled exclusively by the platform WeCom SDK.
"""
from __future__ import annotations

import asyncio
import hmac
import re
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit


_EXPIRED_TOKEN_CODES = {40001, 40014, 42001}


def normalize_api_base(value: Any = None) -> str:
    """Validate the platform-owned API relay root; never accept caller URLs."""
    base = str(value or "https://qyapi.weixin.qq.com").strip().rstrip("/")
    if (not base or len(base) > 2048 or any(character in base for character in "\\?#")
            or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in base)):
        raise ValueError("平台企业微信代理地址无效")
    if base.startswith("//"):
        base = "https:" + base
    elif "://" not in base:
        base = "https://" + base
    try:
        parsed = urlsplit(base)
        if (parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or parsed.port == 0):
            raise ValueError
        # Accessing port above also rejects malformed or out-of-range ports.
        return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path.rstrip("/"), "", ""))
    except ValueError:
        raise ValueError("平台企业微信代理地址无效") from None


class WeCom:
    """The configuration getter is re-read so changed credentials take effect."""

    def __init__(self, ctx: Any, config_getter: Callable[[], Mapping[str, Any]]) -> None:
        self.ctx = ctx
        self.config_getter = config_getter
        self._token_lock = asyncio.Lock()
        self._access_token = ""
        self._token_until = 0.0
        self._token_credentials: tuple[str, str, str] | None = None

    def _config(self) -> Mapping[str, Any]:
        config = self.config_getter()
        if not isinstance(config, Mapping):
            raise ValueError("企业微信配置无效")
        return dict(config)

    @staticmethod
    def _setting(config: Mapping[str, Any], key: str) -> str:
        value = str(config.get(key) or "").strip()
        if not value or len(value) > 512:
            raise ValueError("企业微信配置不完整")
        return value

    async def _request(self, method: str, endpoint: str, *, api_base: str | None = None, **kwargs: Any) -> Any:
        base = normalize_api_base(api_base if api_base is not None else self._config().get("wecom_api_base"))
        try:
            response = await self.ctx.http.request(
                method, base + "/cgi-bin/" + endpoint, timeout=30, follow_redirects=False, **kwargs,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # HTTP errors can contain query strings with secrets or access tokens.
            raise ValueError("企业微信接口连接失败") from None
        if not 200 <= response.status_code < 300:
            raise ValueError("企业微信接口请求失败")
        try:
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError
            return result
        except Exception:
            raise ValueError("企业微信接口响应无效") from None

    @staticmethod
    def _error_code(result: Mapping[str, Any]) -> int:
        try:
            return int(result.get("errcode", 0))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("企业微信接口响应无效") from None

    def _check_delivery(self, config, permission_check):
        if permission_check is not None:
            permission_check()
        current = self._config()
        fields = ("wecom_channel_id", "wecom_corp_id", "wecom_agent_id", "wecom_secret", "wecom_api_base")
        if any(current.get(key) != config.get(key) for key in fields):
            raise ValueError("企业微信打印入口已更改，本次回执未发送")

    async def _token(self, config: Mapping[str, Any] | None = None, *, permission_check=None) -> str:
        config = self._config() if config is None else config
        credentials = (
            self._setting(config, "wecom_corp_id"), self._setting(config, "wecom_secret"),
            normalize_api_base(config.get("wecom_api_base")),
        )
        async with self._token_lock:
            self._check_delivery(config, permission_check)
            if credentials == self._token_credentials and self._access_token and time.monotonic() < self._token_until:
                return self._access_token
            result = await self._request("GET", "gettoken", api_base=credentials[2], params={
                "corpid": credentials[0], "corpsecret": credentials[1],
            })
            access_token = result.get("access_token")
            if self._error_code(result) or not isinstance(access_token, str) or not access_token or len(access_token) > 1024:
                raise ValueError("企业微信访问凭据获取失败，请检查应用配置")
            try:
                expires = int(result.get("expires_in", 7200))
                if expires <= 0:
                    raise ValueError
            except (TypeError, ValueError, OverflowError):
                raise ValueError("企业微信访问凭据有效期无效") from None
            self._access_token = access_token
            self._token_credentials = credentials
            self._token_until = time.monotonic() + max(0, min(expires, 7200) - 60)
            return access_token

    async def _invalidate(self, access_token: str) -> None:
        async with self._token_lock:
            if hmac.compare_digest(self._access_token, access_token):
                self._token_until = 0.0

    @staticmethod
    def _recipient(user: str) -> str:
        if not isinstance(user, str) or user.lower() == "@all" or not re.fullmatch(r"[A-Za-z0-9_.@-]{1,128}", user):
            raise ValueError("企业微信通知用户无效")
        return user

    @staticmethod
    def _agent_id(config: Mapping[str, Any]) -> int:
        try:
            agent_id = int(config.get("wecom_agent_id", 0))
            if isinstance(config.get("wecom_agent_id"), bool) or not 0 < agent_id < 2 ** 31:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            raise ValueError("企业微信应用 AgentID 无效") from None
        return agent_id

    async def _send_message(self, user: str, message: Mapping[str, Any], *, permission_check=None) -> None:
        """Freeze the platform application for a single delivery and token retry."""
        user = self._recipient(user)
        config = self._config()
        payload = dict(message)
        payload.update(touser=user, agentid=self._agent_id(config))
        api_base = normalize_api_base(config.get("wecom_api_base"))
        for attempt in range(2):
            self._check_delivery(config, permission_check)
            access_token = await self._token(config, permission_check=permission_check)
            self._check_delivery(config, permission_check)
            result = await self._request("POST", "message/send", api_base=api_base,
                                         params={"access_token": access_token}, json=payload)
            code = self._error_code(result)
            if code in _EXPIRED_TOKEN_CODES and not attempt:
                await self._invalidate(access_token)
                continue
            if code or result.get("invaliduser") or result.get("unlicenseduser"):
                raise ValueError("企业微信通知发送失败，请检查应用可见范围")
            return
        raise ValueError("企业微信通知访问凭据已失效")

    async def send(self, user: str, text: str, *, permission_check=None) -> None:
        self._recipient(user)
        content = str(text).encode("utf-8")[:2048].decode("utf-8", errors="ignore")
        if not content:
            return
        await self._send_message(user, {"msgtype": "text", "text": {"content": content}, "safe": 0},
                                 permission_check=permission_check)

    async def send_card(self, user: str, card: Mapping[str, Any], *, permission_check=None) -> None:
        """Send one native print card, never a broadcast or a silent text fallback.

        Keys carry the exact queue job ID. Ownership, source application, current
        state and copy limits must still be checked again by the callback handler.
        """
        self._recipient(user)
        if not isinstance(card, Mapping) or card.get("card_type") != "button_interaction":
            raise ValueError("企业微信打印卡片无效")
        task_id = str(card.get("task_id") or "")
        if not re.fullmatch(r"rp-[a-f0-9]{16}", task_id):
            raise ValueError("企业微信打印卡片任务无效")
        job_id = task_id[3:]
        main_title = card.get("main_title")
        buttons = card.get("button_list")
        if (not isinstance(main_title, Mapping) or not isinstance(main_title.get("title"), str)
                or not main_title["title"] or len(main_title["title"]) > 36
                or not isinstance(buttons, (list, tuple)) or not 1 <= len(buttons) <= 6):
            raise ValueError("企业微信打印卡片内容无效")
        keys = set()
        normalized_buttons = []
        for button in buttons:
            if not isinstance(button, Mapping):
                raise ValueError("企业微信打印卡片按钮无效")
            key = button.get("key")
            label = button.get("text")
            style = button.get("style", 1)
            if (not isinstance(key, str) or key in keys
                    or not re.fullmatch(rf"rp:(?:print:{job_id}:[1-9][0-9]?|(?:cancel|status):{job_id})", key)
                    or not isinstance(label, str) or not label or len(label) > 10
                    or button.get("type", 0) != 0 or isinstance(style, bool)
                    or not isinstance(style, int) or not 1 <= style <= 4):
                raise ValueError("企业微信打印卡片按钮无效")
            keys.add(key)
            normalized_buttons.append({"type": 0, "text": label, "key": key, "style": style})
        # Build an allowlisted payload: no caller-supplied navigation, recipients
        # or ID-transformation syntax can escape this single-job confirmation.
        normalized = {
            "card_type": "button_interaction", "task_id": task_id,
            "main_title": {"title": main_title["title"]}, "button_list": normalized_buttons,
        }
        for field, maximum in (("desc", 44),):
            value = main_title.get(field)
            if value is not None:
                if not isinstance(value, str) or len(value) > maximum:
                    raise ValueError("企业微信打印卡片内容无效")
                normalized["main_title"][field] = value
        subtitle = card.get("sub_title_text")
        if subtitle is not None:
            if not isinstance(subtitle, str) or len(subtitle) > 160:
                raise ValueError("企业微信打印卡片内容无效")
            normalized["sub_title_text"] = subtitle
        await self._send_message(user, {
            "msgtype": "template_card", "template_card": normalized,
            "enable_id_trans": 0, "enable_duplicate_check": 1, "duplicate_check_interval": 600,
        }, permission_check=permission_check)

    async def send_print_card(self, user: str, job: Mapping[str, Any], actions=None, *, permission_check=None) -> None:
        """One file, one confirmation card; callers should not resend its task ID."""
        if not isinstance(job, Mapping) or not re.fullmatch(r"[a-f0-9]{16}", str(job.get("id", ""))):
            raise ValueError("企业微信打印卡片任务无效")
        job_id = job["id"]
        if actions is None:
            actions = [
                {"text": "打印1份", "key": f"rp:print:{job_id}:1", "style": 1},
                {"text": "打印2份", "key": f"rp:print:{job_id}:2", "style": 1},
                {"text": "取消", "key": f"rp:cancel:{job_id}", "style": 4},
                {"text": "查看进度", "key": f"rp:status:{job_id}", "style": 2},
            ]
        filename = str(job.get("filename") or "收到的文件")
        description = filename.encode("utf-8")[:128].decode("utf-8", errors="ignore")[:44]
        page_hint = f"共 {job['pages']} 页。" if job.get("pages") else ""
        card_text = str(job.get("card_text") or f"{page_hint}点击按钮开始打印。照片会完整缩放，不会裁切。")[:160]
        await self.send_card(user, {
            "card_type": "button_interaction", "task_id": f"rp-{job_id}",
            "main_title": {"title": "文件已收到", "desc": description},
            "sub_title_text": card_text,
            "button_list": actions,
        }, permission_check=permission_check)
