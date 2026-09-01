# =============================================================================
# 朱雀 PT 站 HTTP API 封装（zhuque_lottery 私有辅助）
#
# 朱雀（https://zhuque.in）是一个 PT 站，本插件的「查询/转盘/魔法卡/道具回收」
# 等功能都是通过其 Web API 实现。所有请求都需要带：
#   - Cookie:        登录态（浏览器 F12 复制整条 Cookie 头）
#   - X-Csrf-Token:  CSRF 令牌（F12 请求头里的 x-csrf-token）
#
# 用第三方库 httpx（平台 venv 已装），不依赖 pyrogram / core / config。
# cookie / xcsrf 由调用方从 ctx.config 取出传入（password 字段）。
#
# 注意：朱雀的 API 返回结构以「实盘」为准，下面字段路径按原项目（aiohttp 版）
# 迁移，关键路径已用注释标注；如站点改版需对照 F12 返回校验。
# =============================================================================
from __future__ import annotations

import asyncio
from typing import Optional, Tuple

import httpx

BASE = "https://zhuque.in"

# 各端点（与原项目一致）
URL_GETINFO = f"{BASE}/api/user/getInfo"
URL_SPIN = f"{BASE}/api/gaming/spinThePrizeWheel"
URL_FIRE = f"{BASE}/api/gaming/fireGenshinCharacterMagic"
URL_LIST_BACKPACK = f"{BASE}/api/mall/listBackpack"
URL_RECYCLE = f"{BASE}/api/mall/recycleMagicCard"

# getInfo 关心的字段：键=朱雀返回字段，值=中文显示名
INFO_FIELDS = {
    "id": "UID",
    "username": "用户名",
    "name": "等级",       # 取自 data.class.name
    "upload": "上传",
    "download": "下载",
    "bonus": "灵石",
}

# 大转盘奖品索引 → 名称
WHEEL_PRIZES = {
    1: "改名卡",
    2: "神佑7天卡",
    3: "邀请卡",
    4: "自动释放7天卡",
    5: "20G",
    6: "10G",
    7: "谢谢惠顾",
}
# 道具回收价值（用于回血估算，索引同上）
CARD_BONUS_VALUES = {1: 300000, 2: 100000, 3: 80000, 4: 30000}
# 道具卡名（背包/回收）
CARD_NAMES = {1: "改名卡", 2: "神佑7天卡", 3: "邀请卡", 4: "自动释放7天卡"}

# 单次转盘消耗灵石
SPIN_COST = 1500


def _headers(cookie: str, xcsrf: str) -> dict:
    return {
        "Cookie": cookie or "",
        "X-Csrf-Token": xcsrf or "",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{BASE}/",
    }


class ZhuqueAPI:
    """朱雀站点 HTTP 封装。每次实例化读取一次 cookie/xcsrf（调用方传入）。"""

    def __init__(self, cookie: str, xcsrf: str, log=None):
        self._cookie = cookie
        self._xcsrf = xcsrf
        self._log = log

    def _warn(self, *a):
        if self._log:
            self._log.warning(*a)

    def _err(self, *a):
        if self._log:
            self._log.error(*a)

    # ── 个人信息查询 ──────────────────────────────────────────────────────
    async def get_info(self, retries: int = 3) -> Optional[dict]:
        """查询个人信息，返回 {field: value} 或 None。字段见 INFO_FIELDS。"""
        headers = _headers(self._cookie, self._xcsrf)
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(URL_GETINFO, headers=headers)
                if resp.status_code != 200:
                    self._warn("getInfo 失败 status=%s", resp.status_code)
                    return None
                data = resp.json().get("data", {}) or {}
                out = {}
                for key in INFO_FIELDS:
                    if key == "name":
                        out[key] = (data.get("class") or {}).get("name", "")
                    else:
                        out[key] = data.get(key, "")
                return out
            except (httpx.HTTPError, ValueError) as e:
                self._warn("getInfo 异常(第%s次): %s", attempt + 1, e)
                await asyncio.sleep(3)
        return None

    # ── 大转盘单抽 ────────────────────────────────────────────────────────
    async def spin_once(self, client: httpx.AsyncClient) -> Optional[int]:
        """转一次大转盘，返回奖品索引（int）或 None。复用传入的 client 以提速。"""
        try:
            resp = await client.post(URL_SPIN, headers=_headers(self._cookie, self._xcsrf))
            if resp.status_code != 200:
                self._warn("转盘请求失败 status=%s", resp.status_code)
                return None
            prize = int((resp.json().get("data") or {}).get("prize", -1))
            return prize if prize != -1 else None
        except (httpx.HTTPError, ValueError, TypeError) as e:
            self._warn("转盘异常: %s", e)
            return None

    # ── 魔法卡释放（原神角色技能）────────────────────────────────────────
    async def fire_genshin(self) -> Optional[Tuple[str, float]]:
        """释放魔法卡，返回 (code, bonus) 或 None。code 含 'SUCCESS' 表示成功。"""
        headers = _headers(self._cookie, self._xcsrf)
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(URL_FIRE, headers=headers, json={"all": 1})
            if resp.status_code != 200:
                self._warn("魔法卡释放失败 status=%s", resp.status_code)
                return None
            data = resp.json().get("data", {}) or {}
            return str(data.get("code", "")), float(data.get("bonus", 0) or 0)
        except (httpx.HTTPError, ValueError, TypeError) as e:
            self._err("魔法卡释放异常: %s", e)
            return None

    # ── 背包道具查询 ──────────────────────────────────────────────────────
    async def list_backpack(self) -> Optional[dict]:
        """查询背包道具数量，返回 {card_id: amount} 或 None。"""
        headers = _headers(self._cookie, self._xcsrf)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(URL_LIST_BACKPACK, headers=headers)
            if resp.status_code != 200:
                self._warn("背包查询失败 status=%s", resp.status_code)
                return None
            card_data = resp.json().get("data", []) or []
            counts = {k: 0 for k in CARD_NAMES}
            for item in card_data:
                cid = item.get("card_id")
                if cid is not None:
                    counts[int(cid)] = item.get("amount", 0)
            return counts
        except (httpx.HTTPError, ValueError, TypeError) as e:
            self._warn("背包查询异常: %s", e)
            return None

    # ── 道具回收 ──────────────────────────────────────────────────────────
    async def recycle_card(self, card_id: int, number: int) -> int:
        """回收 number 张 card_id 道具，返回成功回收的张数。"""
        headers = _headers(self._cookie, self._xcsrf)
        success = 0
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                for _ in range(number):
                    resp = await client.post(URL_RECYCLE, headers=headers, json={"id": card_id})
                    if resp.status_code == 200 and resp.json().get("code"):
                        success += 1
        except (httpx.HTTPError, ValueError, TypeError) as e:
            self._warn("道具回收异常: %s", e)
        return success
