"""AWBotNest 1 configuration export endpoint for the V2 migration assistant."""
from __future__ import annotations

import json
import secrets
import time
from pathlib import Path

__plugin__ = {
    "name": "平台迁移助手",
    "id": "config_migration",
    "version": "1.0.1",
    "author": "AWdress",
    "description": "为 AWBotNest 2 配置迁移助手提供短时、一次性的 V1 配置导出。",
    "changelog": "v1.0.1 统一插件名称\n- V1 与 V2 统一显示为“平台迁移助手”\n- 导出端用途改在插件配置页面说明\n\nv1.0.0 初始版本\n- 提供受管理员 API 与一次性迁移码双重保护的配置导出\n- 导出系统配置、插件配置、启用状态、账号范围与 Bot 路由",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png",
    "scope": "standalone",
    "default_enabled": False,
    "webhook": True,
    "config_schema": {
        "migration_code": {"type": "password", "secret": True, "required": True,
                           "label": "一次性迁移码", "section": "迁移授权", "order": 1,
                           "help": "请设置至少 8 位随机字符；成功导出一次后立即失效。"},
        "expires_minutes": {"type": "number", "default": 10, "min": 1, "max": 60,
                            "label": "有效分钟数", "section": "迁移授权", "order": 2},
        "usage": {"type": "info", "title": "使用方法",
                  "text": "这是 V1 导出端。保存并启用后，立即到 V2 的“平台迁移助手”填写 V1 地址、Webhook 密钥和相同迁移码。迁移完成后请停用本插件。",
                  "section": "说明", "order": 10},
    },
}

_armed_at = 0.0
_used = False


def _load_json(name: str) -> dict:
    path = Path("data") / name
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} 不是 JSON 对象")
    return value


async def setup(ctx):
    global _armed_at, _used
    _armed_at = time.time()
    _used = False

    @ctx.on_webhook
    async def export(req):
        global _used
        supplied = str((req.json or {}).get("code") or "")
        expected = str(ctx.config.get("migration_code") or "")
        ttl = max(1, min(60, int(ctx.config.get("expires_minutes") or 10))) * 60
        if not expected or len(expected) < 8:
            return {"ok": False, "error": "请先设置至少 8 位的一次性迁移码"}
        if _used:
            return {"ok": False, "error": "迁移码已使用，请重新保存配置后再试"}
        if time.time() - _armed_at > ttl:
            return {"ok": False, "error": "迁移码已过期，请重新保存或重载插件"}
        if not secrets.compare_digest(supplied, expected):
            return {"ok": False, "error": "迁移码错误"}
        system = _load_json("config.json")
        plugins = _load_json("plugins_state.json")
        try:
            from kernel.cookies import load_settings as load_cookie_settings
            cookie_settings = load_cookie_settings()
        except Exception as exc:
            ctx.log.warning("CookieCloud 设置未导出：%s", type(exc).__name__)
            cookie_settings = {}
        _used = True
        ctx.log.info("V1 配置迁移包已导出一次（敏感内容未写入日志）")
        return {
            "ok": True,
            "format": "awbotnest-v1-migration",
            "version": 1,
            "created_at": int(time.time()),
            "system": system,
            "plugins": plugins,
            "cookie_settings": cookie_settings,
        }


async def teardown(ctx):
    global _armed_at, _used
    _armed_at = 0.0
    _used = True
