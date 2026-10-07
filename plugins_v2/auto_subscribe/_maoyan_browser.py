"""Read public Maoyan web rankings inside one host-owned browser session."""

from __future__ import annotations

import asyncio
from datetime import datetime
import math
from urllib.parse import parse_qs, urlsplit

from ._base import RankProvider
from ._maoyan import MAOYAN_URL, PLATFORM_TYPE, SERIES_TYPE, validate_web_payload


MAOYAN_WEB_URL = f"{MAOYAN_URL}/dashboard/web-heat"
_WEB_PATH = "/i/api/encrypt/dashboard/webHeatData"
_CONCURRENCY = 2
_INITIALIZE_TIMEOUT_SECONDS = 20.0
_REQUEST_TIMEOUT_SECONDS = 12.0
_FETCH = """async ({path, seriesType, platformType, showDate, timeoutMs}) => {
    const params = new URLSearchParams({seriesType, showDate});
    if (platformType) params.set('platformType', platformType);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        // Use the site's normally initialized fetch. Its own H5guard attaches
        // the current request signature; never export or replay that signature.
        const response = await window.fetch(path + '?' + params.toString(), {
            credentials: 'include', signal: controller.signal
        });
        if (!response.ok) return {http_status: response.status};
        try { return {http_status: response.status, payload: await response.json()}; }
        catch (_) { return {http_status: response.status, invalid_json: true}; }
    } catch (_) { return {network_error: true}; }
    finally { clearTimeout(timer); }
}"""


def ranking_keys(options):
    """Keep the existing media/platform selection semantics and stable keys."""
    options = options or {}
    platforms = RankProvider.as_list(options.get("web_platforms", options.get("maoyan_web_platforms")))
    media_types = RankProvider.as_list(options.get("web_types", options.get("maoyan_web_types")))
    return dict.fromkeys(f"{SERIES_TYPE[media]}|{PLATFORM_TYPE[platform]}"
                         for platform in platforms if platform in PLATFORM_TYPE
                         for media in media_types if media in SERIES_TYPE)


def collection_timeout(options):
    """Budget every requested batch, not just the first few combinations."""
    batches = math.ceil(len(ranking_keys(options)) / _CONCURRENCY)
    return max(45.0, _INITIALIZE_TIMEOUT_SECONDS + batches * (_REQUEST_TIMEOUT_SECONDS + 1) + 5)


def _is_web_response(response):
    try:
        parsed = urlsplit(response.url)
        return parsed.scheme == "https" and parsed.hostname == "piaofang.maoyan.com" and parsed.path == _WEB_PATH and response.status == 200
    except (AttributeError, TypeError, ValueError):
        return False


def _show_date(url):
    values = parse_qs(urlsplit(url).query).get("showDate", [])
    if len(values) != 1 or len(values[0]) != 8 or not values[0].isdigit():
        raise RuntimeError("猫眼网播页面未提供有效榜单日期")
    try:
        parsed = datetime.strptime(values[0], "%Y%m%d")
    except ValueError:
        raise RuntimeError("猫眼网播页面榜单日期格式无效") from None
    if parsed.strftime("%Y%m%d") != values[0]:
        raise RuntimeError("猫眼网播页面榜单日期格式无效")
    return values[0]


async def collect_web_rankings(page, options, *, timeout_seconds=None, checkpoint=None):
    """Return JSON-only rankings/errors/cookies without owning the browser.

    The caller opens ``MAOYAN_WEB_URL`` with its configured ``ctx.browser`` and
    gives the whole browser stage a bounded deadline. Completed combinations
    survive this helper's timeout; cancellation propagates to SDK cleanup.
    """
    keys = ranking_keys(options)
    # The caller owns this checkpoint too: SDK/outer timeouts must not erase
    # combinations already validated before browser cleanup started.
    result = checkpoint if checkpoint is not None else {"web_data": {}, "web_errors": {}, "cookies": {}}
    tasks = []
    if not keys:
        return result
    if timeout_seconds is None:
        timeout_seconds = collection_timeout(options)
    try:
        async with asyncio.timeout(timeout_seconds):
            try:
                # SDK navigates before the async callback. Reload once with a
                # response waiter already installed, so startup cannot miss the
                # page's first successful normal signed API request.
                async with page.expect_response(_is_web_response,
                                                timeout=min(timeout_seconds, _INITIALIZE_TIMEOUT_SECONDS) * 1000) as waiting:
                    await page.reload(wait_until="domcontentloaded",
                                      timeout=min(timeout_seconds, _INITIALIZE_TIMEOUT_SECONDS) * 1000)
                initial = await waiting.value
                validate_web_payload(await initial.json())
                show_date = _show_date(initial.url)
            except asyncio.CancelledError:
                raise
            except Exception:
                result["web_errors"] = dict.fromkeys(keys, "猫眼网播初始化失败（页面未完成验证、响应无效或加载超时）")
                return result

            try:
                result["cookies"] = {cookie["name"]: cookie["value"] for cookie in await page.context.cookies()
                                     if isinstance(cookie, dict) and isinstance(cookie.get("name"), str)
                                     and isinstance(cookie.get("value"), str)}
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # Movie box is independently readable without cookies.

            semaphore = asyncio.Semaphore(_CONCURRENCY)

            async def collect(key):
                async with semaphore:
                    series_type, platform_type = key.split("|", 1)
                    try:
                        try:
                            response = await asyncio.wait_for(page.evaluate(_FETCH, {
                                "path": _WEB_PATH, "seriesType": series_type, "platformType": platform_type,
                                "showDate": show_date, "timeoutMs": int(_REQUEST_TIMEOUT_SECONDS * 1000),
                            }), timeout=_REQUEST_TIMEOUT_SECONDS + 1)
                        except asyncio.CancelledError:
                            raise
                        except TimeoutError:
                            result["web_errors"][key] = "猫眼网播请求超时"
                            return
                        except Exception:
                            result["web_errors"][key] = "猫眼网播浏览器读取失败"
                            return
                        if not isinstance(response, dict):
                            raise RuntimeError("猫眼网播浏览器响应格式无效")
                        status = response.get("http_status")
                        if response.get("network_error"):
                            raise RuntimeError("猫眼网播请求失败或超时")
                        if not isinstance(status, int) or isinstance(status, bool) or not 200 <= status < 300:
                            raise RuntimeError(f"猫眼网播请求失败（HTTP {status if isinstance(status, int) else '未知'}）")
                        if response.get("invalid_json"):
                            raise RuntimeError("猫眼网播未返回有效 JSON")
                        payload = validate_web_payload(response.get("payload"))
                        result["web_data"][key] = payload
                    except asyncio.CancelledError:
                        raise
                    except TimeoutError:
                        result["web_errors"][key] = "猫眼网播请求超时"
                    except RuntimeError as exc:
                        result["web_errors"][key] = str(exc)
                    except Exception:
                        # Browser exceptions can embed cookies, scripts and
                        # request headers. Never persist or log their raw text.
                        result["web_errors"][key] = "猫眼网播浏览器读取失败"

            tasks = [asyncio.create_task(collect(key)) for key in keys]
            await asyncio.gather(*tasks)
    except TimeoutError:
        for key in keys:
            if key not in result["web_data"] and key not in result["web_errors"]:
                result["web_errors"][key] = "猫眼网播读取达到时间上限"
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    return result
