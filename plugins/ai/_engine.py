# =============================================================================
# ai 插件私有辅助：AI 调用封装（仅使用平台统一 AI）
# =============================================================================

from pathlib import Path


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
    ctx,
    messages: list[dict],
    temperature: float = 0.7,
    image_bytes: bytes | None = None,
) -> str:
    """
    调平台统一 AI 生成回复。messages 为 [{"role","content"}, ...]。
    带 image_bytes 时使用 vision 能力。
    出错抛异常，由调用方分类处理。
    """
    # 提取 system 和最后一条 user 消息
    system_msg = None
    user_prompt = ""
    for msg in messages:
        if msg.get("role") == "system":
            system_msg = msg.get("content", "")
        elif msg.get("role") == "user":
            user_prompt = msg.get("content", "")
    if not user_prompt:
        user_prompt = "请回复。"

    if image_bytes:
        return await ctx.ai.vision(
            image=image_bytes, prompt=user_prompt, system=system_msg
        )
    else:
        return await ctx.ai.chat(
            prompt=user_prompt, system=system_msg, temperature=temperature
        )


async def generate_image(
    ctx,
    prompt: str,
    size: str = "1024x1024",
    quality: str = "auto",
) -> bytes:
    """调用平台统一 AI 生图。"""
    path = await ctx.ai.generate_image(
        prompt=prompt, size=size, quality=quality if quality != "auto" else None
    )
    return path.read_bytes()
