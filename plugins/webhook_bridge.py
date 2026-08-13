"""把外部系统的 Webhook 转成 AWBotNest 统一通知。"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from typing import Any


__plugin__ = {
    "name": "Webhook 通知桥",
    "id": "webhook_bridge",
    "version": "1.0.1",
    "author": "AWdress",
    "description": "接收 NAS、下载器、监控、CI 等外部 Webhook，自动提取内容并通过平台统一通知渠道推送。",
    "changelog": "v1.0.1 加固首次加载配置兜底\n- 配置尚未持久化时仍使用内置字段提取与敏感字段过滤默认值\n- 防止完整载荷兜底通知意外包含令牌、密码等敏感字段\n\nv1.0.0 初始版本\n- 支持 GET、JSON、表单与纯文本事件\n- 支持自动字段提取、模板、去重和限流\n- 提供测试通知、统计查看与状态清理动作",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_relay.png",
    "scope": "standalone",
    "default_enabled": False,
    "webhook": True,
    "config_schema": {
        "enabled": {
            "type": "boolean", "default": True, "label": "接收并转发",
            "section": "基本设置", "cols": 4, "order": 1,
        },
        "category": {
            "type": "string", "default": "外部事件", "label": "通知分类",
            "section": "基本设置", "cols": 4, "order": 2,
        },
        "default_level": {
            "type": "select", "default": "info", "label": "默认级别",
            "options": [
                {"value": "info", "label": "信息"},
                {"value": "success", "label": "成功"},
                {"value": "warning", "label": "警告"},
                {"value": "error", "label": "错误"},
            ],
            "section": "基本设置", "cols": 4, "order": 3,
        },
        "title_fields": {
            "type": "string", "default": "title,subject,name,event,event_type,status",
            "label": "标题字段", "section": "内容提取", "cols": 6, "order": 10,
            "help": "按顺序查找，支持点路径，如 project.name。用英文逗号分隔。",
        },
        "message_fields": {
            "type": "string", "default": "message,text,content,description,body,summary",
            "label": "正文字段", "section": "内容提取", "cols": 6, "order": 11,
            "help": "找不到正文时会发送过滤后的完整结构化数据。",
        },
        "level_field": {
            "type": "string", "default": "level,severity,priority,status",
            "label": "级别字段", "section": "内容提取", "cols": 6, "order": 12,
        },
        "source_field": {
            "type": "string", "default": "source,service,app,application,repository.name",
            "label": "来源字段", "section": "内容提取", "cols": 6, "order": 13,
        },
        "title_template": {
            "type": "string", "default": "{source}{title}", "label": "标题模板",
            "section": "内容提取", "cols": 12, "order": 14,
            "help": "可用 {source}、{title}、{event}、{method}；来源会自动加“ · ”。留空不显示标题。",
        },
        "include_metadata": {
            "type": "boolean", "default": True, "label": "附加来源与事件信息",
            "section": "内容提取", "cols": 4, "order": 15,
        },
        "max_chars": {
            "type": "number", "default": 3500, "label": "最大正文字符数",
            "min": 200, "max": 12000, "step": 100,
            "section": "安全控制", "cols": 4, "order": 20,
        },
        "dedupe_seconds": {
            "type": "number", "default": 60, "label": "重复事件忽略秒数",
            "min": 0, "max": 86400, "step": 10,
            "section": "安全控制", "cols": 4, "order": 21,
            "help": "按请求内容去重，0 表示关闭。",
        },
        "rate_limit": {
            "type": "number", "default": 30, "label": "每分钟最大通知数",
            "min": 1, "max": 1000, "step": 1,
            "section": "安全控制", "cols": 4, "order": 22,
        },
        "ignored_fields": {
            "type": "string", "default": "token,apikey,api_key,password,secret,authorization,cookie",
            "label": "敏感字段过滤", "section": "安全控制", "cols": 8, "order": 23,
            "help": "字段名不区分大小写；输出完整载荷时递归移除。",
        },
        "test_notify": {
            "type": "action", "label": "发送测试通知", "action": "test_notify",
            "section": "维护", "cols": 4, "order": 30,
        },
        "show_stats": {
            "type": "action", "label": "查看接收统计", "action": "show_stats",
            "section": "维护", "cols": 4, "order": 31,
        },
        "clear_state": {
            "type": "action", "label": "清空统计和去重状态", "action": "clear_state",
            "danger": True, "section": "维护", "cols": 4, "order": 32,
        },
        "runtime_status": {
            "type": "info", "default": "等待接收事件", "label": "运行状态",
            "section": "维护", "cols": 12, "order": 33,
        },
    },
}


_LEVEL_ALIASES = {
    "ok": "success", "success": "success", "successful": "success", "resolved": "success",
    "warn": "warning", "warning": "warning", "degraded": "warning", "medium": "warning",
    "error": "error", "err": "error", "failed": "error", "failure": "error",
    "critical": "error", "fatal": "error", "high": "error", "down": "error", "firing": "error",
    "info": "info", "notice": "info", "debug": "info", "low": "info", "up": "success",
}

_DEFAULT_TITLE_FIELDS = "title,subject,name,event,event_type,status"
_DEFAULT_MESSAGE_FIELDS = "message,text,content,description,body,summary"
_DEFAULT_LEVEL_FIELDS = "level,severity,priority,status"
_DEFAULT_SOURCE_FIELDS = "source,service,app,application,repository.name"
_DEFAULT_IGNORED_FIELDS = "token,apikey,api_key,password,secret,authorization,cookie"


def _fields(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _lookup(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if not isinstance(current, Mapping):
            return None
        lowered = {str(key).lower(): value for key, value in current.items()}
        current = lowered.get(part.lower())
        if current is None:
            return None
    return current


def _first(data: Any, paths: list[str]) -> Any:
    for path in paths:
        value = _lookup(data, path)
        if value not in (None, "", [], {}):
            return value
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return str(value).strip()


def _redact(value: Any, ignored: set[str]) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _redact(item, ignored)
            for key, item in value.items()
            if str(key).lower() not in ignored
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item, ignored) for item in value]
    return value


def _payload(req: Any) -> Any:
    if req.json is not None:
        return req.json
    text = (req.text or "").strip()
    if text:
        # 兼容 application/x-www-form-urlencoded，无需引入 urllib 之外的依赖。
        content_type = str(req.headers.get("content-type", "")).lower()
        if "application/x-www-form-urlencoded" in content_type:
            from urllib.parse import parse_qs
            return {key: values[-1] if len(values) == 1 else values for key, values in parse_qs(text).items()}
        return text
    return dict(req.query or {})


def _normalize_level(value: Any, default: str) -> str:
    raw = str(value or "").strip().lower()
    if raw.isdigit():
        number = int(raw)
        if number >= 4:
            return "error"
        if number == 3:
            return "warning"
    for key, level in _LEVEL_ALIASES.items():
        # 短词（up/ok/err）只做精确匹配，避免 backup 等普通单词误判级别。
        if key == raw or (len(key) >= 4 and key in raw):
            return level
    return default if default in {"info", "success", "warning", "error"} else "info"


def _event_name(req: Any, data: Any) -> str:
    header_names = (
        "x-github-event", "x-gitlab-event", "x-event-key", "x-event-type",
        "x-webhook-event", "x-hook-event",
    )
    for name in header_names:
        value = str(req.headers.get(name, "")).strip()
        if value:
            return value
    value = _first(data, ["event", "event_type", "type", "action"])
    return _text(value)


def _digest(req: Any) -> str:
    raw = req.method.encode("utf-8") + b"\0" + (req.body or b"")
    if not req.body:
        raw += json.dumps(req.query or {}, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _limited(text: str, maximum: int) -> str:
    if len(text) <= maximum:
        return text
    omitted = len(text) - maximum
    return f"{text[:maximum].rstrip()}\n\n… 已截断 {omitted} 个字符"


def _stats(ctx: Any) -> dict[str, Any]:
    value = ctx.kv.get("stats", {})
    return value if isinstance(value, dict) else {}


def _save_stat(ctx: Any, outcome: str, detail: str = "") -> None:
    stats = _stats(ctx)
    stats["received"] = int(stats.get("received", 0)) + 1
    stats[outcome] = int(stats.get(outcome, 0)) + 1
    stats["last_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    stats["last_outcome"] = outcome
    if detail:
        stats["last_detail"] = detail[:300]
    ctx.kv.set("stats", stats)


async def setup(ctx):
    ctx.log.info("Webhook 通知桥已启用")

    @ctx.on_webhook
    async def on_webhook(req):
        cfg = ctx.config
        if not cfg.get("enabled", True):
            _save_stat(ctx, "disabled")
            return {"ok": False, "ignored": True, "reason": "plugin forwarding disabled"}

        now = time.time()
        limit = max(1, int(cfg.get("rate_limit", 30) or 30))
        rate = ctx.kv.get("rate", {})
        if not isinstance(rate, dict) or now - float(rate.get("start", 0) or 0) >= 60:
            rate = {"start": now, "count": 0}
        if int(rate.get("count", 0)) >= limit:
            _save_stat(ctx, "rate_limited")
            ctx.log.warning("Webhook 已触发速率限制：%s/分钟", limit)
            return {"ok": False, "ignored": True, "reason": "rate limit exceeded"}
        rate["count"] = int(rate.get("count", 0)) + 1
        ctx.kv.set("rate", rate)

        digest = _digest(req)
        dedupe_seconds = max(0, int(cfg.get("dedupe_seconds", 60) or 0))
        recent = ctx.kv.get("recent", {})
        if not isinstance(recent, dict):
            recent = {}
        last_seen = float(recent.get(digest, 0) or 0)
        if dedupe_seconds and now - last_seen < dedupe_seconds:
            _save_stat(ctx, "duplicate")
            return {"ok": True, "ignored": True, "reason": "duplicate"}
        recent = {key: seen for key, seen in recent.items() if now - float(seen or 0) < max(dedupe_seconds, 60)}
        recent[digest] = now
        ctx.kv.set("recent", recent)

        try:
            data = _payload(req)
            ignored = {
                name.lower()
                for name in _fields(cfg.get("ignored_fields", _DEFAULT_IGNORED_FIELDS))
            }
            safe_data = _redact(data, ignored)
            structured = safe_data if isinstance(safe_data, Mapping) else {}

            title = _text(_first(
                structured, _fields(cfg.get("title_fields", _DEFAULT_TITLE_FIELDS)),
            ))
            message = _text(_first(
                structured, _fields(cfg.get("message_fields", _DEFAULT_MESSAGE_FIELDS)),
            ))
            source = _text(_first(
                structured, _fields(cfg.get("source_field", _DEFAULT_SOURCE_FIELDS)),
            ))
            event = _event_name(req, structured)
            raw_level = _first(
                structured, _fields(cfg.get("level_field", _DEFAULT_LEVEL_FIELDS)),
            )
            level = _normalize_level(raw_level, str(cfg.get("default_level", "info")))

            if not message:
                message = _text(safe_data) or "（空事件）"
            maximum = min(12000, max(200, int(cfg.get("max_chars", 3500) or 3500)))
            message = _limited(message, maximum)

            source_label = f"{source} · " if source else ""
            template = str(cfg.get("title_template", "{source}{title}") or "")
            try:
                rendered_title = template.format(
                    source=source_label, title=title, event=event, method=req.method,
                ).strip(" ·-")
            except (KeyError, ValueError):
                rendered_title = f"{source_label}{title}".strip(" ·-")

            parts = []
            if rendered_title:
                parts.append(f"【{rendered_title}】")
            parts.append(message)
            if cfg.get("include_metadata", True):
                metadata = []
                if source and source not in rendered_title:
                    metadata.append(f"来源：{source}")
                if event:
                    metadata.append(f"事件：{event}")
                if metadata:
                    parts.append("\n".join(metadata))

            category = str(cfg.get("category", "外部事件") or "外部事件").strip()
            await ctx.notify("\n\n".join(parts), level=level, category=category)
            detail = rendered_title or event or source or "事件已转发"
            _save_stat(ctx, "forwarded", detail)
            ctx.update_config({"runtime_status": f"最近转发：{time.strftime('%Y-%m-%d %H:%M:%S')} · {detail}"})
            return {"ok": True, "forwarded": True, "level": level}
        except Exception as exc:
            _save_stat(ctx, "failed", str(exc))
            ctx.update_config({"runtime_status": f"最近失败：{time.strftime('%Y-%m-%d %H:%M:%S')} · {exc}"})
            ctx.log.exception("Webhook 转发失败")
            raise

    @ctx.action("test_notify")
    async def test_notify():
        await ctx.notify(
            "【Webhook 通知桥】\n\n这是一条测试通知。插件已能使用平台统一通知渠道。",
            level=str(ctx.config.get("default_level", "info")),
            category=str(ctx.config.get("category", "外部事件") or "外部事件"),
        )
        return {"ok": True, "message": "测试通知已提交，请检查所配置的通知渠道。"}

    @ctx.action("show_stats")
    async def show_stats():
        stats = _stats(ctx)
        if not stats:
            return {"ok": True, "message": "尚未收到 Webhook。"}
        labels = {
            "received": "总接收", "forwarded": "已转发", "duplicate": "重复忽略",
            "rate_limited": "限流忽略", "disabled": "停用忽略", "failed": "失败",
            "last_time": "最近时间", "last_outcome": "最近结果", "last_detail": "最近详情",
        }
        lines = [f"{labels.get(key, key)}：{value}" for key, value in stats.items()]
        return {"ok": True, "message": "\n".join(lines)}

    @ctx.action("clear_state")
    def clear_state():
        for key in ("stats", "recent", "rate"):
            ctx.kv.delete(key)
        ctx.update_config({"runtime_status": "统计和去重状态已清空"})
        return {"ok": True, "message": "统计、限流和去重状态已清空。"}


async def teardown(ctx):
    ctx.log.info("Webhook 通知桥已停用")
