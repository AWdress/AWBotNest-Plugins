# =============================================================================
# AWBotNest 插件：Emby 剧集季集校验与修复（emby_episode_fix）
#
# 作用：
# 1. 扫描 Emby 中所有 Episode，读取文件名里的 SxxExx。
# 2. 对比 Emby 当前识别的 ParentIndexNumber / IndexNumber。
# 3. 输出不匹配清单。
# 4. 可按“文件名优先”规则，直接把 Emby 元数据修正为文件名中的季集号。
#
# 注意：
# - 只检查文件名中带 SxxExx 的条目。
# - 自动修复会直接写回 Emby 条目元数据，请先用“扫描检查”确认结果。
# =============================================================================

import json
import os
import re
from typing import Any

import requests

__plugin__ = {
    "name": "Emby 剧集季集校验",
    "id": "emby_episode_fix",
    "version": "1.0.0",
    "author": "AWdress",
    "description": "检查 Emby 剧集识别是否与文件名中的 SxxExx 一致，并可按文件名直接修正季集号。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png",
    "changelog": "v1.0.0 初始版本\n- 扫描 Emby Episode 与文件名中的 SxxExx 是否一致\n- 支持测试连接、扫描检查、按文件名自动修复\n- 自动修复后可再次校验确认结果",
    "scope": "user",
    "default_enabled": False,
    "requirements": ["requests>=2.28"],
    "config_schema": {
        "enabled": {
            "type": "boolean", "default": True, "label": "启用插件",
            "section": "功能开关", "cols": 3, "order": 1,
        },
        "auto_delete_command": {
            "type": "boolean", "default": True, "label": "自动删除命令消息",
            "section": "功能开关", "cols": 3, "order": 2,
        },
        "emby_server": {
            "type": "string", "default": "", "label": "Emby 地址",
            "section": "基础配置", "order": 10,
            "help": "例如：https://v.awdys.cn/",
            "required": True,
        },
        "api_key": {
            "type": "password", "default": "", "label": "Emby API Key",
            "section": "基础配置", "order": 11,
            "required": True,
        },
        "user_id": {
            "type": "string", "default": "", "label": "Emby 用户 ID（可选）",
            "section": "基础配置", "order": 12,
            "help": "留空时插件会自动取第一个可用用户；如要稳定写入，建议填写固定用户 ID。",
        },
        "fix_lock_data": {
            "type": "boolean", "default": True, "label": "修复后锁定条目数据",
            "section": "修复策略", "cols": 4, "order": 20,
            "help": "开启后会把 LockData 设为 true，减少后续刷新把季集又刮回去。",
        },
        "max_output": {
            "type": "slider", "default": 50, "label": "输出条目上限",
            "min": 5, "max": 200, "step": 5,
            "section": "修复策略", "order": 21,
            "help": "扫描结果在消息里最多展示多少条；完整信息仍会写日志。",
        },
        "test_connection": {
            "type": "action", "label": "测试连接", "action": "test_connection",
            "section": "操作", "order": 30,
        },
        "scan_now": {
            "type": "action", "label": "扫描检查", "action": "scan_now",
            "section": "操作", "order": 31,
        },
        "fix_now": {
            "type": "action", "label": "按文件名自动修复", "action": "fix_now",
            "section": "操作", "order": 32,
            "danger": True,
        },
        "last_scan_summary": {
            "type": "info", "label": "最近扫描结果", "section": "状态", "order": 40,
            "text": "尚未执行扫描",
        },
    },
}

_REGEX = re.compile(r"[Ss](\d{1,2})[\._\- ]?[Ee](\d+)")
_FIELDS = "Path,ProviderIds,ParentIndexNumber,IndexNumber,SeriesName,Name,SeasonName"


def _cfg(ctx):
    c = ctx.config
    return {
        "enabled": bool(c.get("enabled", True)),
        "emby_server": str(c.get("emby_server", "") or "").strip(),
        "api_key": str(c.get("api_key", "") or "").strip(),
        "user_id": str(c.get("user_id", "") or "").strip(),
        "fix_lock_data": bool(c.get("fix_lock_data", True)),
        "max_output": int(c.get("max_output", 50) or 50),
        "auto_delete_command": bool(c.get("auto_delete_command", True)),
    }


def _headers(api_key: str) -> dict[str, str]:
    return {
        "X-Emby-Token": api_key,
        "Accept": "application/json",
    }


def _post_headers(api_key: str) -> dict[str, str]:
    return {
        "X-Emby-Token": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _base_url(server: str) -> str:
    return server.rstrip("/")


def _validate_config(cfg: dict[str, Any]) -> tuple[bool, str]:
    if not cfg["emby_server"]:
        return False, "未配置 Emby 地址"
    if not cfg["api_key"]:
        return False, "未配置 Emby API Key"
    return True, "ok"


def _get_first_user_id(base: str, api_key: str) -> str:
    url = f"{base}/emby/Users"
    r = requests.get(url, params={"api_key": api_key}, headers=_headers(api_key), timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list) and data:
        uid = data[0].get("Id")
        if uid:
            return str(uid)
    raise RuntimeError("无法自动获取 Emby 用户 ID")


def _resolve_user_id(cfg: dict[str, Any]) -> str:
    if cfg["user_id"]:
        return cfg["user_id"]
    return _get_first_user_id(_base_url(cfg["emby_server"]), cfg["api_key"])


def _get_all_episodes(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    base = _base_url(cfg["emby_server"])
    url = f"{base}/emby/Items"
    params = {
        "api_key": cfg["api_key"],
        "Recursive": "true",
        "IncludeItemTypes": "Episode",
        "Fields": _FIELDS,
    }
    r = requests.get(url, params=params, headers=_headers(cfg["api_key"]), timeout=120)
    r.raise_for_status()
    return r.json().get("Items", [])


def _collect_mismatches(cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    items = _get_all_episodes(cfg)
    mismatches = []
    checked_count = 0

    for item in items:
        file_path = item.get("Path") or ""
        if not file_path:
            continue
        filename = os.path.basename(file_path)
        m = _REGEX.search(filename)
        if not m:
            continue

        checked_count += 1
        file_season = int(m.group(1))
        file_episode = int(m.group(2))
        emby_season = item.get("ParentIndexNumber")
        emby_episode = item.get("IndexNumber")

        if emby_season != file_season or emby_episode != file_episode:
            mismatches.append({
                "id": item.get("Id"),
                "series": item.get("SeriesName") or item.get("Name") or "未知剧集",
                "name": item.get("Name") or "",
                "season_name": item.get("SeasonName") or "",
                "path": file_path,
                "file_season": file_season,
                "file_episode": file_episode,
                "emby_season": emby_season,
                "emby_episode": emby_episode,
                "provider_ids": item.get("ProviderIds") or {},
            })

    return mismatches, checked_count


def _summary_text(mismatches: list[dict[str, Any]], checked_count: int, max_output: int) -> str:
    lines = [
        f"共检查到 {checked_count} 个带 SxxExx 标记的文件。",
        f"发现不匹配 {len(mismatches)} 个。",
    ]
    if not mismatches:
        lines.append("🎉 所有带 SxxExx 标记的文件与 Emby 识别完全一致！")
        return "\n".join(lines)

    lines.append("")
    lines.append("前几条不匹配如下：")
    for row in mismatches[:max_output]:
        lines.append(
            f"- {row['series']}｜文件名 S{row['file_season']:02d}E{row['file_episode']}｜Emby S{row['emby_season']}E{row['emby_episode']}"
        )
    if len(mismatches) > max_output:
        lines.append(f"……其余 {len(mismatches) - max_output} 条请看运行日志")
    return "\n".join(lines)


def _fix_one(cfg: dict[str, Any], user_id: str, row: dict[str, Any]) -> dict[str, Any]:
    base = _base_url(cfg["emby_server"])
    item_id = str(row["id"])
    get_url = f"{base}/emby/Users/{user_id}/Items/{item_id}"
    item = requests.get(get_url, headers=_headers(cfg["api_key"]), timeout=30).json()

    before_season = item.get("ParentIndexNumber")
    before_episode = item.get("IndexNumber")

    item["ParentIndexNumber"] = row["file_season"]
    item["IndexNumber"] = row["file_episode"]
    if cfg["fix_lock_data"]:
        item["LockData"] = True

    post_url = f"{base}/emby/Items/{item_id}?api_key={cfg['api_key']}"
    r = requests.post(
        post_url,
        headers=_post_headers(cfg["api_key"]),
        data=json.dumps(item, ensure_ascii=False),
        timeout=60,
    )
    r.raise_for_status()

    new_item = requests.get(get_url, headers=_headers(cfg["api_key"]), timeout=30).json()
    after_season = new_item.get("ParentIndexNumber")
    after_episode = new_item.get("IndexNumber")

    return {
        "id": item_id,
        "series": row["series"],
        "name": row["name"],
        "before_season": before_season,
        "before_episode": before_episode,
        "after_season": after_season,
        "after_episode": after_episode,
        "expected_season": row["file_season"],
        "expected_episode": row["file_episode"],
        "ok": after_season == row["file_season"] and after_episode == row["file_episode"],
    }


def _auto_delete(ctx, message):
    if not ctx.config.get("auto_delete_command", True):
        return
    async def _run():
        try:
            await message.delete()
        except Exception:
            pass
    import asyncio
    asyncio.create_task(_run())


async def setup(ctx):
    @ctx.action("test_connection")
    async def test_connection_action():
        cfg = _cfg(ctx)
        ok, msg = _validate_config(cfg)
        if not ok:
            return {"ok": False, "message": msg}
        try:
            user_id = _resolve_user_id(cfg)
            base = _base_url(cfg["emby_server"])
            r = requests.get(
                f"{base}/emby/Users/{user_id}",
                headers=_headers(cfg["api_key"]),
                params={"api_key": cfg["api_key"]},
                timeout=30,
            )
            r.raise_for_status()
            return {"ok": True, "message": f"连接成功，用户 ID：{user_id}"}
        except Exception as e:
            ctx.log.error("[emby_episode_fix] 测试连接失败: %r", e)
            return {"ok": False, "message": f"连接失败：{e}"}

    @ctx.action("scan_now")
    async def scan_now_action():
        cfg = _cfg(ctx)
        ok, msg = _validate_config(cfg)
        if not ok:
            return {"ok": False, "message": msg}
        try:
            mismatches, checked_count = _collect_mismatches(cfg)
            summary = _summary_text(mismatches, checked_count, cfg["max_output"])
            ctx.log.info("[emby_episode_fix] 扫描结果：\n%s", summary)
            try:
                ctx.update_config({"last_scan_summary": summary})
            except Exception:
                pass
            return {"ok": True, "message": summary}
        except Exception as e:
            ctx.log.error("[emby_episode_fix] 扫描失败: %r", e)
            return {"ok": False, "message": f"扫描失败：{e}"}

    @ctx.action("fix_now")
    async def fix_now_action():
        cfg = _cfg(ctx)
        ok, msg = _validate_config(cfg)
        if not ok:
            return {"ok": False, "message": msg}
        try:
            user_id = _resolve_user_id(cfg)
            mismatches, checked_count = _collect_mismatches(cfg)
            if not mismatches:
                summary = f"共检查到 {checked_count} 个带 SxxExx 标记的文件，当前没有不匹配项。"
                try:
                    ctx.update_config({"last_scan_summary": summary})
                except Exception:
                    pass
                return {"ok": True, "message": summary}

            results = []
            for row in mismatches:
                try:
                    result = _fix_one(cfg, user_id, row)
                    results.append(result)
                except Exception as e:
                    results.append({
                        "series": row["series"],
                        "name": row["name"],
                        "expected_season": row["file_season"],
                        "expected_episode": row["file_episode"],
                        "ok": False,
                        "error": str(e),
                    })
                    ctx.log.error("[emby_episode_fix] 修复失败 %s: %r", row["path"], e)

            ok_count = sum(1 for x in results if x.get("ok"))
            fail_count = len(results) - ok_count
            lines = [
                f"扫描到 {len(mismatches)} 条不匹配，已尝试按文件名修复。",
                f"成功 {ok_count} 条，失败 {fail_count} 条。",
            ]
            if fail_count:
                lines.append("")
                lines.append("失败条目：")
                for row in results:
                    if not row.get("ok"):
                        lines.append(
                            f"- {row.get('series','未知')}｜目标 S{row.get('expected_season')}E{row.get('expected_episode')}｜错误：{row.get('error','未知错误')}"
                        )
            summary = "\n".join(lines)
            ctx.log.info("[emby_episode_fix] 修复结果：\n%s", summary)
            try:
                ctx.update_config({"last_scan_summary": summary})
            except Exception:
                pass
            return {"ok": fail_count == 0, "message": summary}
        except Exception as e:
            ctx.log.error("[emby_episode_fix] 自动修复失败: %r", e)
            return {"ok": False, "message": f"自动修复失败：{e}"}

    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-11)
    async def emby_episode_fix_cmd(client, message):
        cfg = _cfg(ctx)
        if not cfg["enabled"]:
            return
        text = (message.text or "").strip().lower()
        if text not in ("/embyfix", ".embyfix", "/embycheck", ".embycheck"):
            return
        _auto_delete(ctx, message)
        try:
            mismatches, checked_count = _collect_mismatches(cfg)
            summary = _summary_text(mismatches, checked_count, cfg["max_output"])
            ctx.log.info("[emby_episode_fix] 命令扫描结果：\n%s", summary)
            try:
                await message.edit(summary[:4000])
            except Exception:
                pass
            try:
                ctx.update_config({"last_scan_summary": summary})
            except Exception:
                pass
        except Exception as e:
            ctx.log.error("[emby_episode_fix] 命令扫描失败: %r", e)
            try:
                await message.edit(f"扫描失败：{e}")
            except Exception:
                pass


async def teardown(ctx):
    ctx.log.info("[emby_episode_fix] 插件已停用")
