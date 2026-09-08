"""Import AWBotNest 1 settings through the companion V1 migration plugin."""
from __future__ import annotations

import copy
import json
import time
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

__plugin__ = {
    "name": "配置迁移助手",
    "id": "config_migration",
    "version": "1.0.0",
    "author": "AWdress",
    "description": "通过 V1 配置迁移源，将系统设置和插件配置安全迁移到 AWBotNest 2。",
    "changelog": "v1.0.0 初始版本\n- 支持连接 V1 迁移源并生成脱敏预览\n- 支持系统设置、插件配置、启用状态、账号范围和 Bot 路由选择性迁移\n- 执行前自动备份 V2 配置，默认保留已有有效值",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png",
    "scope": "standalone",
    "render_mode": "vue",
    "tags": ["配置迁移", "版本升级", "安全备份"],
    "resources": {"timeout_seconds": 60, "max_concurrency": 1, "max_background_tasks": 1},
    "config_schema": {
        "v1_url": {"type": "string", "default": "", "label": "V1 平台地址"},
        "v1_webhook_secret": {"type": "password", "secret": True, "default": "", "label": "V1 Webhook 密钥"},
        "migration_code": {"type": "password", "secret": True, "default": "", "label": "一次性迁移码"},
    },
}

_ctx = None
_bundle: dict | None = None
_preview: dict | None = None

_SYSTEM_MAP = {
    "API_ID": "api_id", "API_HASH": "api_hash", "BOT_TOKEN": "bot_token",
    "BOT_NAME": "bot_name", "DEFAULT_BOT_ID": "default_bot_id",
    "DEFAULT_BOT_CHAT_ID": "default_bot_chat_id", "WEB_UI_PORT": "web_port",
    "WEBHOOK_SECRET": "webhook_secret", "API_KEY": "api_key",
    "PIP_INDEX_URL": "pip_index_url", "PLUGIN_REPO_INTERVAL": "plugin_repo_interval",
}
_SECRET_WORDS = ("token", "secret", "password", "api_key", "api_hash", "cookie", "session")


def _body(request) -> dict:
    return request.json if isinstance(request.json, dict) else {}


def _masked(value):
    if isinstance(value, dict):
        return {str(k): ("********" if any(w in str(k).lower() for w in _SECRET_WORDS) and v not in (None, "") else _masked(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_masked(v) for v in value]
    return value


def _nonempty(value) -> bool:
    return value not in (None, "", [], {}, 0, False)


def _session_names(value) -> list[str]:
    result=[]
    for item in value or []:
        name = item.get("session") or item.get("name") if isinstance(item, dict) else item
        name = str(name or "").strip()
        if name and name not in result:
            result.append(name)
    return result


def _convert(bundle: dict) -> dict:
    source = bundle.get("system") if isinstance(bundle.get("system"), dict) else {}
    state = bundle.get("plugins") if isinstance(bundle.get("plugins"), dict) else {}
    system = {target: copy.deepcopy(source[key]) for key, target in _SYSTEM_MAP.items() if _nonempty(source.get(key))}
    for key in ("api_id", "web_port", "plugin_repo_interval"):
        if key in system:
            try: system[key] = int(system[key])
            except (TypeError, ValueError): system.pop(key, None)
    if isinstance(source.get("BOTS"), list):
        system["bots"] = [{"id": str(x.get("id") or ""), "name": str(x.get("name") or x.get("id") or "Bot"),
                           "token": str(x.get("token") or "")} for x in source["BOTS"] if isinstance(x, dict) and x.get("id")]
    sessions = _session_names(source.get("ACCOUNTS"))
    if sessions:
        system["user_sessions"] = sessions
    repos=[]
    for item in source.get("PLUGIN_REPOS") or []:
        value = item.get("url") if isinstance(item, dict) else item
        value = str(value or "").strip()
        if value and value not in repos: repos.append(value)
    if repos: system["plugin_repos"] = repos
    proxy = source.get("proxy_set") or {}
    if isinstance(proxy, dict):
        p = proxy.get("proxy") or proxy
        if isinstance(p, dict) and p.get("hostname"):
            auth = ""
            if p.get("username"): auth = f"{p.get('username')}:{p.get('password','')}@"
            system["proxy_url"] = f"{p.get('scheme') or 'socks5'}://{auth}{p['hostname']}:{p.get('port') or 1080}"
    channels=source.get("NOTIFICATION_CHANNELS")
    if isinstance(channels,list): system["notification_channels"] = copy.deepcopy(channels)
    ai_settings=source.get("AI_SERVICES")
    if isinstance(ai_settings,dict): system["ai_settings"] = copy.deepcopy(ai_settings)
    cookie_settings=bundle.get("cookie_settings")
    if isinstance(cookie_settings,dict): system["cookie_settings"] = copy.deepcopy(cookie_settings)
    enabled_raw=state.get("enabled") or {}
    enabled=[str(k) for k,v in enabled_raw.items() if v] if isinstance(enabled_raw,dict) else [str(x) for x in enabled_raw]
    return {
        "system": system,
        "plugin_config": copy.deepcopy(state.get("config") or {}),
        "enabled_plugins": enabled,
        "plugin_accounts": copy.deepcopy(state.get("account_scope") or {}),
        "bot_routing": copy.deepcopy(state.get("bot_choice") or {}),
    }


def _summary(converted: dict) -> dict:
    return {
        "system_fields": len(converted["system"]),
        "plugin_configs": len(converted["plugin_config"]),
        "enabled_plugins": len(converted["enabled_plugins"]),
        "account_scopes": len(converted["plugin_accounts"]),
        "bot_routes": len(converted["bot_routing"]),
        "system_preview": _masked(converted["system"]),
        "plugin_ids": sorted(set(converted["plugin_config"]) | set(converted["enabled_plugins"])),
    }


async def _fetch(ctx, values: dict) -> dict:
    base=str(values.get("v1_url") or "").strip().rstrip("/")
    parsed=urlparse(base)
    if parsed.scheme not in {"http","https"} or not parsed.netloc:
        raise ValueError("V1 平台地址无效")
    key=str(values.get("v1_webhook_secret") or "").strip()
    code=str(values.get("migration_code") or "")
    if not key or len(code)<8: raise ValueError("请填写 V1 Webhook 密钥和至少 8 位迁移码")
    url=f"{base}/api/v1/plugin/config_migration/webhook"
    response=await ctx.http.post(url, params={"apikey":key}, json={"code":code}, timeout=30)
    response.raise_for_status()
    data=response.json()
    if not data.get("ok"): raise ValueError(str(data.get("error") or "V1 拒绝导出"))
    if data.get("format")!="awbotnest-v1-migration": raise ValueError("迁移包格式不正确")
    return data


async def setup(ctx):
    global _ctx, _bundle, _preview
    _ctx=ctx; _bundle=None; _preview=None

    async def status(request):
        return {"ok":True, "ready":_bundle is not None, "preview":_preview}

    async def preview(request):
        global _bundle, _preview
        values=_body(request)
        _bundle=await _fetch(ctx, values)
        converted=_convert(_bundle); _preview=_summary(converted)
        ctx.log.info("已读取 V1 迁移包：%s 个插件配置（敏感内容未写入日志）", _preview["plugin_configs"])
        return {"ok":True, "preview":_preview, "warning":"预览已脱敏；执行迁移前会自动备份 V2 配置。"}

    async def migrate(request):
        global _bundle, _preview
        if _bundle is None: return {"ok":False,"error":"请先读取并预览 V1 配置"}
        options=_body(request); converted=_convert(_bundle); settings=ctx.settings
        backup_dir=ctx.data_dir/"backups"; backup_dir.mkdir(parents=True,exist_ok=True)
        backup=backup_dir/f"v2-config-{time.strftime('%Y%m%d-%H%M%S')}.json"
        backup.write_text(json.dumps(asdict(settings),ensure_ascii=False,indent=2),encoding="utf-8")
        overwrite=bool(options.get("overwrite")); changed={}
        def merge_dict(current,incoming):
            result=dict(current or {})
            for k,v in (incoming or {}).items():
                if overwrite or not _nonempty(result.get(k)): result[k]=copy.deepcopy(v)
            return result
        if options.get("system",True):
            for key,value in converted["system"].items():
                current=getattr(settings,key,None)
                if overwrite or not _nonempty(current):
                    if key == "bots":
                        from awbotnest.config import BotSettings
                        value = [BotSettings(**item) for item in value]
                    setattr(settings,key,copy.deepcopy(value)); changed[key]=1
        if options.get("plugins",True): settings.plugin_config=merge_dict(settings.plugin_config,converted["plugin_config"]); changed["plugin_config"]=len(converted["plugin_config"])
        if options.get("accounts",True): settings.plugin_accounts=merge_dict(settings.plugin_accounts,converted["plugin_accounts"]); changed["plugin_accounts"]=len(converted["plugin_accounts"])
        if options.get("routing",True): settings.bot_routing=merge_dict(settings.bot_routing,converted["bot_routing"]); changed["bot_routing"]=len(converted["bot_routing"])
        if options.get("enabled",False):
            settings.enabled_plugins=list(dict.fromkeys([*settings.enabled_plugins,*converted["enabled_plugins"]])); changed["enabled_plugins"]=len(converted["enabled_plugins"])
        from awbotnest.config import save_settings
        save_settings(settings)
        _bundle=None; _preview=None
        ctx.log.info("V1 配置迁移完成，V2 原配置已备份到 %s", backup.name)
        return {"ok":True,"message":"迁移完成。连接类系统设置需重启 V2 后生效。","backup":str(backup),"changed":changed,"restart_required":True}

    ctx.on_api("status",status); ctx.on_api("preview",preview); ctx.on_api("migrate",migrate)


async def teardown(ctx):
    global _ctx,_bundle,_preview
    _ctx=None; _bundle=None; _preview=None
