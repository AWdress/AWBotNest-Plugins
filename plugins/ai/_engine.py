# =============================================================================
# ai 插件私有辅助：OpenAI 兼容接口封装（不被平台识别为插件，_ 开头）
# =============================================================================

import base64
import urllib.request
from typing import Optional

import openai


def classify_error(err: Exception) -> str:
    """把上游/SDK 异常转成可展示的中文提示（脱敏 + 截断）。"""
    msg = str(err) or err.__class__.__name__
    lower = msg.lower()
    # 脱敏：避免把 key/token 打到群里
    if "api_key" in lower or "authorization" in lower or "bearer" in lower:
        msg = "(错误信息已脱敏)"
    if len(msg) > 300:
        msg = msg[:300] + "..."
    if any(k in lower for k in ("model_not_found", "no available channel", "model not found")):
        return f"AI 模型不可用：{msg}"
    if any(k in lower for k in ("401", "403", "unauthorized", "forbidden")):
        return f"AI 鉴权失败（401/403）：{msg}"
    if any(k in lower for k in ("429", "rate limit", "too many requests")):
        return f"AI 请求过于频繁（429）：{msg}"
    if "503" in lower or "service unavailable" in lower:
        return f"AI 服务暂时不可用（503）：{msg}"
    return f"AI 调用失败：{msg}"


async def generate(
    api_key: str,
    base_url: Optional[str],
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
    image_bytes: Optional[bytes] = None,
) -> str:
    """
    调 OpenAI 兼容接口生成回复。messages 为 [{"role","content"}, ...]。
    带 image_bytes 时把图片塞进最后一条 user 消息（vision 格式）。
    出错抛异常，由调用方分类处理。
    """
    client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url or None)
    formatted = [{"role": m["role"], "content": m["content"]} for m in messages]

    if image_bytes and formatted:
        # 找最后一条 user 消息，改成 文本+图片 的 vision 结构
        for i in range(len(formatted) - 1, -1, -1):
            if formatted[i].get("role") == "user":
                text = str(formatted[i].get("content", "")).strip() or "请解释这张图片表达的内容。"
                b64 = base64.b64encode(image_bytes).decode("utf-8")
                formatted[i]["content"] = [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ]
                break

    resp = await client.chat.completions.create(
        model=model, messages=formatted, temperature=temperature
    )
    if resp.choices:
        return resp.choices[0].message.content or ""
    return ""


async def generate_image(
    api_key: str,
    base_url: Optional[str],
    model: str,
    prompt: str,
    size: str = "1024x1024",
    quality: str = "auto",
) -> bytes:
    """调用 OpenAI 兼容 Images API，兼容 b64_json、data URL 和普通 URL。"""
    client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url or None)
    kwargs = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
    }
    if quality and quality != "auto":
        kwargs["quality"] = quality
    resp = await client.images.generate(**kwargs)
    data = getattr(resp, "data", None) or []
    if not data:
        raise RuntimeError("生图接口未返回图片")
    item = data[0]
    encoded = getattr(item, "b64_json", None)
    if encoded:
        return base64.b64decode(encoded)
    url = str(getattr(item, "url", None) or "")
    if url.startswith("data:") and "," in url:
        return base64.b64decode(url.split(",", 1)[1])
    if url:
        def _download() -> bytes:
            request = urllib.request.Request(url, headers={"User-Agent": "AWBotNest-AI/1.1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        import asyncio
        return await asyncio.to_thread(_download)
    raise RuntimeError("生图接口未返回可读取的图片数据")
