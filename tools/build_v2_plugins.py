"""Build self-contained AWBotNest 2 packages without changing V1 plugins."""
from __future__ import annotations

import ast
import json
import pprint
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugins"
OUTPUT = ROOT / "plugins_v2"
COMPAT = ROOT / "tools" / "v2_compat_runtime.py"
SKIP_NAMES = {"node_modules", ".npm-cache", "__pycache__", "frontend"}


def entries():
    yield from sorted(p for p in SOURCE.glob("*.py") if not p.name.startswith("_"))
    yield from sorted(
        p / "__init__.py" for p in SOURCE.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "__init__.py").exists()
    )


def literal(tree, name, default=None):
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                try:
                    return ast.literal_eval(node.value)
                except Exception:
                    return default
    return default


def inferred_schema(defaults):
    schema = {
        "v2_compat_notice": {
            "type": "info", "title": "AWBotNest 2 兼容模式",
            "text": "V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。",
            "section": "兼容性", "order": -100,
        }
    }
    for index, (key, value) in enumerate((defaults or {}).items(), start=1):
        if key.startswith("_") or key in {"last_result", "last_summary", "history"}:
            continue
        field = {"title": key.replace("_", " "), "section": "V2 配置", "order": index}
        lowered = key.lower()
        if any(word in lowered for word in ("password", "passwd", "secret", "token", "api_key", "cookie")):
            field.update(type="password", default="")
        elif isinstance(value, bool):
            field.update(type="boolean", default=value)
        elif isinstance(value, (int, float)):
            field.update(type="number", default=value)
        elif isinstance(value, list):
            field.update(type="text", default="\n".join(map(str, value)), help="每行一项")
        elif isinstance(value, dict):
            field.update(type="text", default=json.dumps(value, ensure_ascii=False, indent=2))
        else:
            field.update(type="string", default=value if value is not None else "")
        schema[key] = field
    return schema


def declared_config_keys(entry):
    files = [entry] if entry.name != "__init__.py" else list(entry.parent.rglob("*.py"))
    keys = set()
    patterns = [
        r"ctx\.config\.get\(\s*['\"]([^'\"]+)",
        r"ctx\.config\[\s*['\"]([^'\"]+)",
        r"ctx\.update_config\(\s*\{\s*['\"]([^'\"]+)",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            keys.update(re.findall(pattern, text))
    return keys


def complete_schema(schema, entry):
    schema = dict(schema or {})
    for index, key in enumerate(sorted(declared_config_keys(entry)), start=9000):
        if key in schema:
            continue
        lowered = key.lower()
        sensitive = any(word in lowered for word in ("password", "passwd", "secret", "token", "api_key", "cookie"))
        schema[key] = {
            "type": "password" if sensitive else "string", "default": "",
            "title": key.replace("_", " "), "section": "V2 兼容字段", "order": index,
        }
    # V2 can resolve Telegram chat IDs to names in its native picker.  Promote
    # legacy target/chat fields so groups and channels are selectable instead of
    # requiring opaque numeric IDs.
    for key, field in schema.items():
        lowered = key.lower()
        if ("chat" in lowered or "channel" in lowered or "group" in lowered) and isinstance(field, dict):
            if field.get("type") in {"string", "number"} and not any(
                word in lowered for word in ("name", "title", "username")
            ):
                field["type"] = "chat"
                field.setdefault("chat_types", ["group", "channel"])
                field.setdefault("session", True)
    return schema


def default_tags(plugin_id, metadata):
    """Supply useful V2 market filters when old V1 metadata had no tags."""
    existing = metadata.get("tags")
    if isinstance(existing, list) and len(existing) >= 2:
        return [str(item) for item in existing[:4]]
    lowered = plugin_id.lower()
    curated = {
        "auto_avatar": ["头像轮换", "图片池", "定时任务"], "auto_changename": ["昵称报时", "日期模板", "定时任务"],
        "common_lottery": ["通用抽奖", "Lottery8Bot", "群组管理"], "custom_auto_reply": ["自定义回复", "延迟发送", "定时规则"],
        "emby_episode_fix": ["Emby剧集", "文件名校正", "元数据修复"], "getmsg": ["消息提取", "链接解析", "媒体信息"],
        "gptgod_checkin": ["GPT-GOD签到", "多账号", "网页自动化"], "hdhive_lottery": ["海胆抽奖", "积分抽奖", "奖品统计"],
        "id": ["身份查询", "用户信息", "Telegram账号"], "jupai": ["句牌生成", "文字图片", "群组互动"],
        "msg_forward": ["消息转发", "规则路由", "跨群同步"], "probe": ["网络探测", "延迟测试", "服务监控"],
        "pterclub_bonus": ["PterClub赠魔", "魔力转赠", "Cookie登录"], "self_delete": ["消息自删", "延时删除", "群组清理"],
        "trans115search": ["115资源搜索", "网盘检索", "磁链转换"], "u2_dmhy": ["U2赠魔", "魔力转赠", "站点Cookie"],
        "webhook_bridge": ["Webhook桥接", "外部通知", "签名校验"], "xjj": ["小鸡签到", "站点自动化", "签到提醒"],
        "zf": ["转发助手", "消息过滤", "频道同步"], "zpr": ["桌面提醒", "定时通知", "消息推送"],
        "ai": ["AI对话", "智能回复", "主动搭话"], "auto_lottery": ["自动抽奖", "中奖统计", "奖品发放"],
        "auto_subscribe": ["自动订阅", "影视搜索", "订阅管理"], "awblackjack": ["二十一点", "Telegram游戏", "积分下注"],
        "awembypush": ["Emby推送", "媒体通知", "TMDB匹配"], "awpulse": ["色花堂助手", "自动签到", "自动发帖"],
        "awrelay": ["消息中继", "话题转发", "验证码处理"], "bomb_game": ["炸弹游戏", "群组娱乐", "互动玩法"],
        "custom_plugin": ["自定义插件", "脚本执行", "扩展开发"], "digital_pet": ["电子宠物", "喂养互动", "随机事件"],
        "dyp_redpacket": ["红包领取", "动态口令", "自动抢包"], "emby_toolbox": ["Emby维护", "媒体库清理", "元数据管理"],
        "hdhive_quiz": ["海胆答题", "题库管理", "AI出题"], "hdsky_redpacket": ["天空红包", "自动领取", "动态密码"],
        "hhan_lottery": ["幸运转盘", "赠豆", "消息管理"], "human_lottery": ["人工抽奖", "抽奖活动", "中奖记录"],
        "keyword_auto_reply": ["关键词回复", "定时规则", "自动删除"], "movie_monitor_115": ["115影视监控", "资源订阅", "自动推送"],
        "pt_multi_checkin": ["PT站签到", "多站点", "Cloudflare", "Cookie"], "quiz_game": ["群组答题", "AI出题", "积分排行"],
        "red_packet_grab": ["红包监控", "自动抢包", "群组通知"], "red_packet_send": ["红包发送", "定时发包", "活动管理"],
        "transfer": ["站点转赠", "魔力转移", "排行榜"], "yingchao_redpacket": ["应超红包", "自动领取", "口令解析"],
        "zhuque_lottery": ["朱雀抽奖", "魔力抽取", "转盘任务"],
    }
    if plugin_id in curated:
        return curated[plugin_id]
    tags = []
    if any(word in lowered for word in ("checkin", "sign", "pulse")):
        tags.append("自动化")
    if any(word in lowered for word in ("lottery", "packet", "bonus", "transfer")):
        tags.append("福利")
    if any(word in lowered for word in ("emby", "movie", "115", "subscribe")):
        tags.append("媒体")
    if any(word in lowered for word in ("reply", "forward", "msg", "ai", "quiz", "game")):
        tags.append("消息处理")
    if len(tags) == 1:
        tags.append("Telegram")
    return tags[:4] or ["工具", "Telegram"]


def bump_patch_version(value):
    """Increment the V2 package patch version without changing the V1 source."""
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(.*)", str(value or "0.0.0"))
    if not match:
        return str(value or "0.0.1")
    return f"{match.group(1)}.{match.group(2)}.{int(match.group(3)) + 1}{match.group(4)}"


def copy_source(entry, target):
    if entry.name != "__init__.py":
        shutil.copy2(entry, target / "_legacy.py")
        return "._legacy"
    legacy = target / "_legacy"
    source_dir = entry.parent
    shutil.copytree(
        source_dir, legacy,
        ignore=lambda _dir, names: [name for name in names if name in SKIP_NAMES],
    )
    # V2 officially supports module-federated Vue configs.  Publish only the
    # built dist (never node_modules or source tooling) when a plugin provides it.
    frontend_dist = entry.parent / "frontend" / "dist"
    if frontend_dist.is_dir() and any((frontend_dist / name).is_file() for name in ("remoteEntry.js", "assets/remoteEntry.js")):
        shutil.copytree(frontend_dist, target / "frontend" / "dist")
    legacy_entry = legacy / "__init__.py"
    if entry.parent.name == "awrelay":
        text = legacy_entry.read_text(encoding="utf-8")
        text = text.replace(
            "from pyrogram import raw\nfrom pyrogram.enums import ParseMode\nfrom pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyParameters",
            "from .._compat import raw, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup, ReplyParameters",
        )
        legacy_entry.write_text(text, encoding="utf-8")
    elif entry.parent.name == "human_lottery":
        text = legacy_entry.read_text(encoding="utf-8").replace(
            "from pyrogram.enums import ParseMode", "from .._compat import ParseMode"
        )
        legacy_entry.write_text(text, encoding="utf-8")
    return "._legacy"


def build_one(entry):
    source = entry.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(entry))
    metadata = dict(literal(tree, "__plugin__", {}) or {})
    plugin_id = str(metadata.get("id") or (entry.parent.name if entry.name == "__init__.py" else entry.stem))
    if not plugin_id:
        raise ValueError(f"missing plugin id: {entry}")
    target = OUTPUT / plugin_id
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    shutil.copy2(COMPAT, target / "_compat.py")
    module = copy_source(entry, target)

    metadata.pop("render_mode", None)
    metadata.pop("plugin_api_version", None)
    metadata.pop("min_platform_version", None)
    metadata.pop("default_enabled", None)
    if not isinstance(metadata.get("config_schema"), dict):
        metadata["config_schema"] = inferred_schema(literal(tree, "DEFAULTS", {}))
    metadata["config_schema"] = complete_schema(metadata["config_schema"], entry)
    metadata["changelog"] = (
        "AWBotNest 2 兼容发布\n- 使用 Telethon 原生事件、调度和生命周期托管\n"
        "- 保留 AWBotNest 1 版本与原有数据\n\n" + str(metadata.get("changelog") or "")
    )
    metadata["v1_compatible_version"] = str(metadata.get("version") or "")
    metadata["version"] = bump_patch_version(metadata.get("version"))
    metadata["v2_adapter"] = "telethon"
    metadata["tags"] = default_tags(plugin_id, metadata)
    if entry.name == "__init__.py" and any((entry.parent / "frontend" / "dist" / name).is_file() for name in ("remoteEntry.js", "assets/remoteEntry.js")):
        metadata["render_mode"] = "vue"

    wrapper = f'''"""AWBotNest 2 entry; generated from the maintained V1 plugin."""
from __future__ import annotations

from ._compat import adapt
from {module} import setup as _legacy_setup
try:
    from {module} import DEFAULTS as _legacy_defaults
except ImportError:
    _legacy_defaults = {{}}
try:
    from {module} import teardown as _legacy_teardown
except ImportError:
    _legacy_teardown = None

__plugin__ = {pprint.pformat(metadata, width=110, sort_dicts=False)}
_active_context = None


async def setup(ctx):
    global _active_context
    _active_context = adapt(ctx, _legacy_defaults)
    await _legacy_setup(_active_context)


async def teardown(ctx):
    global _active_context
    adapted = _active_context
    _active_context = None
    if adapted is not None and _legacy_teardown is not None:
        await _legacy_teardown(adapted)
    if adapted is not None:
        await adapted.close()
'''
    (target / "__init__.py").write_text(wrapper, encoding="utf-8")
    return plugin_id, metadata, target


def main():
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    manifest = {"plugins": {}}
    for entry in entries():
        plugin_id, metadata, target = build_one(entry)
        manifest["plugins"][plugin_id] = {
            key: metadata.get(key, "")
            for key in ("name", "version", "author", "description", "changelog", "icon", "tags", "scope", "render_mode")
        }
        manifest["plugins"][plugin_id]["path"] = target.relative_to(ROOT).as_posix() + "/"
    (ROOT / "manifest_v2.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"built {len(manifest['plugins'])} V2 packages")


if __name__ == "__main__":
    main()
