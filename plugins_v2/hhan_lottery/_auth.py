"""憨憨小助手统一 Cookie 来源。"""

from __future__ import annotations


def _manual_cookie(ctx) -> tuple[str, str]:
    value = str(ctx.config.get("manual_cookie", "") or "").strip()
    if value.lower().startswith("cookie:"):
        value = value[7:].strip()
    if not value:
        return "", "尚未填写手动 Cookie"
    if "\r" in value or "\n" in value:
        return "", "手动 Cookie 不能包含换行符"
    if "=" not in value:
        return "", "手动 Cookie 格式不正确，应填写 name=value; name2=value2"
    return value, ""


async def cookie_header(ctx, *, path: str, request_sync: bool = True) -> tuple[str, str]:
    source = str(ctx.config.get("cookie_source", "platform") or "platform").lower()
    if source == "manual":
        return _manual_cookie(ctx)
    # V2 CookieService 不再暴露 ``available`` 属性；以 header 能力和结果判断可用性。
    cookies = getattr(ctx, "cookies", None)
    if cookies is None or not callable(getattr(cookies, "header", None)):
        if request_sync:
            try:
                if callable(getattr(cookies, "request_sync", None)):
                    await cookies.request_sync("hhanclub.net")
            except Exception:
                pass
        return "", "平台 Cookie 同步未启用或尚无可用数据"
    try:
        cookie = await cookies.header("hhanclub.net", path=path)
    except Exception as exc:  # noqa: BLE001
        return "", f"读取平台 Cookie 失败：{exc}"
    if cookie:
        return cookie, ""
    if request_sync:
        try:
            await ctx.cookies.request_sync("hhanclub.net")
        except Exception:
            pass
    return "", "未找到 hhanclub.net Cookie，请登录网站后重新同步"
