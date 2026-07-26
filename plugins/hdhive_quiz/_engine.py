# =============================================================================
# 影巢答题红包插件 - 大模型兜底作答（优先平台 AI，回退自带配置）
# =============================================================================
from __future__ import annotations

import re

_SINGLE_SYS = (
    "你是严谨的答题助手。下面给你一道单选题和 4 个选项，请判断正确答案。"
    "只输出正确选项的字母（A、B、C 或 D），不要输出任何其它文字、标点或解释。"
)
_JUDGE_SYS = (
    "你是严谨的答题助手。下面给你一道判断题，请判断它是对还是错。"
    "只输出「对」或「错」两个字之一，不要输出任何其它文字、标点或解释。"
)


def _build_prompt(question: str, options: list[tuple[str, str]], qtype: str) -> str:
    if qtype == "judge":
        return f"题目：{question}"
    lines = [f"题目：{question}", "选项："]
    for label, content in options:
        lines.append(f"{label}. {content}")
    return "\n".join(lines)


def _extract_letter(text: str) -> str:
    m = re.search(r"[A-Da-d]", text or "")
    return m.group(0).upper() if m else ""


def _extract_judge(text: str) -> str:
    t = text or ""
    if "对" in t or "正确" in t or "true" in t.lower():
        return "对"
    if "错" in t or "false" in t.lower():
        return "错"
    return ""


async def ask_answer(ctx, cfg: dict, question: str, options: list[tuple[str, str]],
                     qtype: str, log=None) -> tuple[str, str]:
    """
    让大模型作答（优先平台统一 AI，回退插件自带配置）。返回 (answer, err)：
      - 单选：answer 为字母 A-D
      - 判断：answer 为 '对' / '错'
      - 失败：answer 为 ''，err 为原因
    """
    system = _JUDGE_SYS if qtype == "judge" else _SINGLE_SYS
    prompt = _build_prompt(question, options, qtype)

    # 优先平台统一 AI
    if ctx.ai.is_available("text"):
        try:
            content = await ctx.ai.chat(prompt=prompt, system=system, temperature=0)
            if qtype == "judge":
                ans = _extract_judge(content)
            else:
                ans = _extract_letter(content)
            if not ans:
                if log:
                    log.warning("[影巢答题] 平台 AI 返回无法解析: %r", content)
                return ("", f"平台 AI 返回无法解析: {content!r}")
            return (ans, "")
        except Exception as e:  # noqa: BLE001
            if log:
                log.warning("[影巢答题] 平台 AI 调用失败，回退自带配置: %r", e)

    # 回退插件自带 OpenAI 配置
    api_key = (cfg.get("llm_api_key") or "").strip()
    if not api_key:
        return ("", "平台 AI 不可用且未配置插件 API Key")
    try:
        import openai  # 惰性导入
    except Exception:  # noqa: BLE001
        return ("", "平台 AI 不可用且 openai 库未安装")

    base_url = (cfg.get("llm_base_url") or "").strip() or None
    model = (cfg.get("llm_model") or "gpt-4o-mini").strip()

    try:
        client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": prompt}],
            temperature=0,
        )
        content = resp.choices[0].message.content if resp.choices else ""
    except Exception as e:  # noqa: BLE001
        if log:
            log.warning("[影巢答题] 自带配置调用失败: %r", e)
        return ("", f"大模型调用失败: {e}")

    if qtype == "judge":
        ans = _extract_judge(content)
    else:
        ans = _extract_letter(content)
    if not ans:
        return ("", f"大模型返回无法解析: {content!r}")
    return (ans, "")
