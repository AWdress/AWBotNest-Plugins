#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AWPulse AI 回复与帖子分类；AI 能力统一由平台 ctx.ai 提供。"""

import hashlib
import json
import logging
import os
import re
from typing import Optional

from .stats_manager import StatsManager


class AIReplyService:
    """同步浏览器线程使用的 AI 服务，底层由入口注入的平台 AI 代理执行。"""

    _REPLY_REJECT_MARKERS = (
        "抱歉", "对不起", "我无法协助", "我不能协助", "无法协助", "不能协助",
        "我无法帮助", "我不能帮助", "无法帮助", "不能帮助",
        "我无法提供", "我不能提供", "无法提供", "不能提供",
        "我无法参与", "我不能参与", "无法参与", "不能参与",
        "我无法生成", "我不能生成", "无法生成", "不能生成",
        "违反政策", "违反规定", "不符合政策", "不符合规定",
        "sorry", "can't help", "cannot help", "unable to", "i refuse",
    )
    _REPLY_META_MARKERS = (
        "论坛通用回复", "通用回复可用", "建议回复", "替代回复",
        "可以改为回复", "可以使用以下", "可使用以下", "作为替代",
        "我可以帮你", "若你需要", "如果你需要",
    )

    def __init__(self, config: dict):
        self.enabled = bool(config.get("enable_ai_reply", False))
        self.enable_post_filter = bool(config.get("enable_ai_post_filter", True))
        self.platform_ai = config.get("_platform_ai")
        self.system_prompt = config.get(
            "ai_system_prompt",
            "你是一个论坛用户，需要根据帖子标题和内容生成简短的回复。"
            "回复要自然、友好、简洁，不超过50字。",
        )
        self.logger = logging.getLogger(__name__)
        base_dir = os.environ.get(
            "AWPULSE_BASE",
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        self._type_cache_file = os.path.join(base_dir, "data", "post_type_cache.json")
        self._type_cache = self._load_type_cache()

    def is_enabled(self) -> bool:
        return bool(
            self.enabled
            and self.platform_ai
            and self.platform_ai.is_available("text")
        )

    def _chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        if not self.platform_ai or not self.platform_ai.is_available("text"):
            raise RuntimeError("平台未配置可用的 AI 文本模型")
        return self.platform_ai.chat(
            prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _load_type_cache(self) -> dict:
        try:
            if os.path.exists(self._type_cache_file):
                with open(self._type_cache_file, "r", encoding="utf-8") as file:
                    return json.load(file)
        except Exception:
            pass
        return {}

    def _save_type_cache(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._type_cache_file), exist_ok=True)
            if len(self._type_cache) > 2000:
                self._type_cache = dict(list(self._type_cache.items())[-2000:])
            with open(self._type_cache_file, "w", encoding="utf-8") as file:
                json.dump(self._type_cache, file, ensure_ascii=False)
        except Exception:
            pass

    @staticmethod
    def _cache_key(title: str) -> str:
        return "v3_" + hashlib.md5(title.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def _has_resource_link(content: str = "") -> bool:
        text = str(content or "")
        patterns = (
            r"(?:https?:)?//\S+",
            r"(?:magnet|ed2k|thunder)://\S+",
            r"forum\.php\?mod=attachment[^\s\]]*",
            r"attachment\.php\?[^\s\]]+",
        )
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _has_strong_resource_signals(title: str, content: str = "") -> bool:
        text = f"{title} {content[:500]}"
        upper = text.upper()
        words = (
            "ED2K", "MAGNET", "115", "自抓", "原档", "压缩包", "合集",
            "配额", "下载", "网盘", "磁力", "种子", "写真", "资源",
            "在线预览", "新片预览",
        )
        if any(word in upper for word in words):
            return True
        return bool(re.search(
            r"(?:\d+(?:\.\d+)?\s*(?:KB|MB|GB|TB|G|T)\b|\d+\s*[Vv]\b)",
            text,
            re.IGNORECASE,
        ))

    def _validate_generated_reply(self, reply) -> Optional[str]:
        if not isinstance(reply, str):
            return None
        cleaned = reply.strip().strip('"“”')
        if not cleaned:
            return None
        lowered = cleaned.lower()
        reason = None
        if len(cleaned) > 50:
            reason = f"超过50字（{len(cleaned)}字）"
        elif any(marker in lowered for marker in self._REPLY_REJECT_MARKERS):
            reason = "包含拒答/免责声明"
        elif any(marker in lowered for marker in self._REPLY_META_MARKERS):
            reason = "包含提示词或替代模板话术"
        if reason:
            self.logger.warning(
                "AI回复审核未通过，按生成失败处理: %s; 内容=%s",
                reason,
                cleaned.replace("\n", " ")[:100],
            )
            return None
        return cleaned

    def _detect_by_keywords(self, title: str, content: str = "") -> str:
        full_text = f"{title} {content}".lower()
        groups = (
            ("FISHING", (
                "钓鱼帖", "钓鱼贴", "钓鱼", "永久封号", "全永久封号", "封号",
                "别回复", "不要回复", "禁止回复", "回复本帖", "编辑回复",
                "你号就没了", "号就没了", "测试帖", "测试贴",
            )),
            ("ADMIN", (
                "版规", "公告", "通知", "规则", "管理员", "版主",
                "禁止", "违规", "【公告】", "【通知】", "【规则】",
            )),
            ("SPAM", (
                "招聘", "高薪", "兼职", "日结", "日薪", "月入", "代理",
                "加盟", "推广", "联系方式", "加微信", "加qq", "telegram",
                "破解", "外挂", "刷单", "赌博", "彩票",
            )),
        )
        for result, keywords in groups:
            for keyword in keywords:
                if keyword in full_text:
                    self.logger.info("关键词检测: %s (关键词: %s)", result, keyword)
                    return result
        return "NORMAL"

    def _detect_post_type(self, title: str, content: str = "") -> str:
        keyword_type = self._detect_by_keywords(title, content)
        if keyword_type != "NORMAL":
            return keyword_type
        if not self._has_resource_link(content):
            self.logger.info("结构特征判断: 首楼无资源链接，跳过")
            return "SKIP"
        if self._has_strong_resource_signals(title, content):
            self.logger.info("结构特征判断: 有资源链接的正常资源帖")
            return "NORMAL"
        if not self.enable_post_filter:
            return "NORMAL"

        cache_key = self._cache_key(title)
        if cache_key in self._type_cache:
            cached = self._type_cache[cache_key]
            self.logger.info("命中缓存: %s (%s)", cached, title[:30])
            return cached

        prompt = f"""请判断以下论坛帖子是否属于“可下载内容分享帖”。只判断帖子结构和用途，不评价内容题材。

帖子标题：{title}

帖子内容：
{content[:800] if content else '(无内容)'}

NORMAL 必须包含实际下载链接、网盘链接、磁力/ED2K 地址或论坛附件，并分享具体资源。
公告、广告、求助、讨论、投票、闲聊，以及没有实际资源链接的帖子必须判为 SKIP。
只回复 NORMAL 或 SKIP。"""
        try:
            self.logger.info("AI检测帖子类型...")
            raw = self._chat(
                prompt,
                system="你只根据论坛帖子的结构和用途分类，仅输出 NORMAL 或 SKIP。",
                temperature=0.3,
                max_tokens=50,
            )
            match = re.search(r"\b(NORMAL|SKIP)\b", raw.upper())
            result = "NORMAL" if match and match.group(1) == "NORMAL" else "SKIP"
            self.logger.info("AI判断: %s", "正常资源帖" if result == "NORMAL" else "非资源帖，跳过")
            self._type_cache[cache_key] = result
            self._save_type_cache()
            return result
        except Exception as exc:
            self.logger.warning("平台 AI 检测帖子类型失败: %s", exc)
            self._record_error()
            return "ERROR"

    @staticmethod
    def _record_error() -> None:
        try:
            StatsManager().record_ai_error()
        except Exception:
            pass

    def generate_reply(self, title: str, content: str = "") -> Optional[str]:
        if not self.is_enabled():
            self.logger.warning("AI回复未启用或平台 AI 文本模型不可用")
            return None
        try:
            if self._detect_post_type(title, content) != "NORMAL":
                return "SKIP_POST"
            preview = content[:500] if content else ""
            prompt = f"帖子标题：{title}"
            if preview:
                prompt += f"\n帖子内容：{preview}"
            prompt += "\n\n请生成一条自然、简短的论坛回复，不超过50字。"
            reply = self._chat(
                prompt,
                system=self.system_prompt,
                temperature=0.8,
                max_tokens=200,
            )
            self.logger.info("平台 AI 生成回复: %s", reply)
            return self._validate_generated_reply(reply)
        except Exception as exc:
            self.logger.warning("平台 AI 生成回复失败: %s", exc)
            self._record_error()
            return None
