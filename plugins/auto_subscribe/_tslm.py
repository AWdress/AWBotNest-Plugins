"""TSLM 动漫标题实体标注接口适配。"""

from __future__ import annotations

from dataclasses import dataclass

import httpx


class TslmError(RuntimeError):
    """TSLM 返回内容无法用于标题识别。"""


@dataclass(frozen=True)
class TslmResult:
    title: str
    episode: int | None = None


def parse_title(endpoint: str, token: str, title: str, timeout: int = 10) -> TslmResult:
    """调用 TSLM span 标注接口，提取第一段 Title 和可选 Episode。"""
    endpoint = str(endpoint or "").strip()
    title = str(title or "").strip()
    if not endpoint:
        raise TslmError("未配置 TSLM Endpoint")
    if not title:
        raise TslmError("标题为空")

    headers = {"Accept": "application/json"}
    if str(token or "").strip():
        headers["Authorization"] = f"Bearer {str(token).strip()}"
    try:
        response = httpx.post(
            endpoint,
            json={"input": title},
            headers=headers,
            timeout=max(3, min(int(timeout or 10), 60)),
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise TslmError(f"请求失败：{exc}") from exc

    if not isinstance(payload, dict) or payload.get("code") != 200:
        message = payload.get("message") if isinstance(payload, dict) else "响应格式错误"
        raise TslmError(f"接口返回失败：{message or '未知错误'}")
    data = payload.get("data")
    if not isinstance(data, list):
        raise TslmError("接口未返回实体列表")

    labels: dict[str, list[str]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        label, start, end = item.get("label"), item.get("start"), item.get("end")
        if (
            not isinstance(label, str)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(title)
        ):
            continue
        value = title[start:end].strip()
        if value:
            labels.setdefault(label, []).append(value)

    titles = labels.get("Title") or []
    if not titles:
        raise TslmError("接口未识别出动漫名称")
    episode = None
    episodes = labels.get("Episode") or []
    if episodes and str(episodes[0]).isdigit():
        episode = int(episodes[0])
    return TslmResult(title=str(titles[0]).strip(), episode=episode)
