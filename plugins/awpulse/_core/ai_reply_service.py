#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI智能回复服务
支持多种AI接口（OpenAI, Claude, 国产AI等）
"""

import requests
import json
import logging
import os
import hashlib
import re
from typing import Optional
from .stats_manager import StatsManager

class AIReplyService:
    """AI回复服务类"""

    _REPLY_REJECT_MARKERS = (
        '抱歉', '对不起',
        '我无法协助', '我不能协助', '无法协助', '不能协助',
        '我无法帮助', '我不能帮助', '无法帮助', '不能帮助',
        '我无法提供', '我不能提供', '无法提供', '不能提供',
        '我无法参与', '我不能参与', '无法参与', '不能参与',
        '我无法生成', '我不能生成', '无法生成', '不能生成',
        '违反政策', '违反规定', '不符合政策', '不符合规定',
        'sorry', "can't help", 'cannot help', 'unable to', 'i refuse',
    )
    _REPLY_META_MARKERS = (
        '论坛通用回复', '通用回复可用', '建议回复', '替代回复',
        '可以改为回复', '可以使用以下', '可使用以下', '作为替代',
        '我可以帮你', '若你需要', '如果你需要',
    )
    
    def __init__(self, config: dict):
        """
        初始化AI服务
        
        Args:
            config: AI配置字典
        """
        self.enabled = config.get('enable_ai_reply', False)
        self.api_type = config.get('ai_api_type', 'openai')  # openai, claude, custom
        self.api_url = config.get('ai_api_url', '')
        self.api_key = config.get('ai_api_key', '')
        self.model = config.get('ai_model', 'gpt-3.5-turbo')
        self.temperature = config.get('ai_temperature', 0.8)
        self.max_tokens = config.get('ai_max_tokens', 200)
        self.timeout = config.get('ai_timeout', 10)
        
        # 系统提示词
        self.system_prompt = config.get('ai_system_prompt', 
            '你是一个论坛用户，需要根据帖子标题和内容生成简短的回复。'
            '回复要自然、友好、简洁，不超过50字。'
            '不要使用敏感词汇，保持礼貌和正能量。'
        )
        
        self.logger = logging.getLogger(__name__)
        
        # 代理设置
        proxy_config = config.get('proxy', {})
        self.proxies = None
        if proxy_config.get('enabled', False) and proxy_config.get('use_for_ai', True):
            self.proxies = {
                'http': proxy_config.get('http_proxy', ''),
                'https': proxy_config.get('https_proxy', '')
            }
            self.logger.info(f"AI接口将使用代理: {self.proxies.get('https', self.proxies.get('http', 'N/A'))}")

        # 帖子类型识别缓存（持久化，跨会话生效）
        base_dir = os.environ.get('AWPULSE_BASE', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._type_cache_file = os.path.join(base_dir, 'data', 'post_type_cache.json')
        self._type_cache = self._load_type_cache()

    def _load_type_cache(self) -> dict:
        try:
            if os.path.exists(self._type_cache_file):
                with open(self._type_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_type_cache(self):
        try:
            os.makedirs(os.path.dirname(self._type_cache_file), exist_ok=True)
            # 最多保留 2000 条，超出时丢弃最早的
            if len(self._type_cache) > 2000:
                items = list(self._type_cache.items())[-2000:]
                self._type_cache = dict(items)
            with open(self._type_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._type_cache, f, ensure_ascii=False)
        except Exception:
            pass

    def _cache_key(self, title: str) -> str:
        # 判定规则升级时改前缀，避免历史误判（尤其是旧提示词产生的大量 SKIP）继续生效。
        return "v2_" + hashlib.md5(title.strip().encode('utf-8')).hexdigest()

    @staticmethod
    def _has_resource_link(content: str = "") -> bool:
        """首楼必须存在实际资源地址或论坛附件；只有标题关键词不算资源帖。"""
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
        """识别无需 AI 即可确认的资源帖，避免模型安全策略造成全量误杀。"""
        text = f"{title} {content[:500]}"
        upper = text.upper()
        resource_words = (
            "ED2K", "MAGNET", "115", "自抓", "原档", "压缩包", "合集",
            "配额", "下载", "网盘", "磁力", "种子", "写真", "资源",
            "在线预览", "新片预览",
        )
        if any(word in upper for word in resource_words):
            return True
        # 常见标题规格：306G / 59.8GB / 1.73T / 127V 等。
        return bool(re.search(
            r"(?:\d+(?:\.\d+)?\s*(?:KB|MB|GB|TB|G|T)\b|\d+\s*[Vv]\b)",
            text,
            re.IGNORECASE,
        ))
    
    def is_enabled(self) -> bool:
        """检查AI回复是否启用"""
        return self.enabled and bool(self.api_key)

    def _validate_generated_reply(self, reply) -> Optional[str]:
        """发送前审核 AI 文本；拒答、元话术或超长内容一律视为生成失败。"""
        if not isinstance(reply, str):
            return None
        cleaned = reply.strip().strip('"“”')
        if not cleaned:
            return None

        lowered = cleaned.lower()
        reason = None
        if len(cleaned) > 50:
            reason = f'超过50字（{len(cleaned)}字）'
        elif any(marker in lowered for marker in self._REPLY_REJECT_MARKERS):
            reason = '包含拒答/免责声明'
        elif any(marker in lowered for marker in self._REPLY_META_MARKERS):
            reason = '包含提示词或替代模板话术'

        if reason:
            preview = cleaned.replace('\n', ' ')[:100]
            self.logger.warning(f"AI回复审核未通过，按生成失败处理: {reason}; 内容={preview}")
            return None
        return cleaned
    
    def _detect_post_type(self, title: str, content: str = "") -> str:
        """
        使用AI检测帖子类型
        
        Args:
            title: 帖子标题
            content: 帖子内容
        
        Returns:
            'NORMAL' - 正常帖子，可以回复
            'FISHING' - 钓鱼帖，不要回复
            'ADMIN' - 管理帖/公告帖，不要回复
            'SKIP' - 其他不适合回复的帖子
        """
        # 明确危险内容先拦截。首楼没有实际链接时，无论标题多像资源帖都跳过。
        keyword_type = self._detect_by_keywords(title, content)
        if keyword_type != 'NORMAL':
            return keyword_type
        if not self._has_resource_link(content):
            self.logger.info("结构特征判断: 首楼无资源链接，跳过")
            return 'SKIP'

        # 有链接且资源特征明确则直接放行；AI 只处理剩余模糊标题。
        if self._has_strong_resource_signals(title, content):
            self.logger.info("结构特征判断: 有资源链接的正常资源帖")
            return 'NORMAL'

        # 再查新版缓存
        cache_key = self._cache_key(title)
        if cache_key in self._type_cache:
            cached_type = self._type_cache[cache_key]
            self.logger.info(f"命中缓存: {cached_type} ({title[:30]})")
            return cached_type

        try:
            # 构建检测提示词
            detect_prompt = f"""请判断以下论坛帖子是否属于“可下载内容分享帖”。只判断帖子结构和用途，不评价内容题材。

帖子标题：{title}

帖子内容：
{content[:800] if content else '(无内容)'}

判断标准：

1. 可下载内容分享帖（NORMAL），必须满足：
   - 正文中存在实际下载链接、网盘链接、磁力/ED2K 地址或论坛附件链接；没有链接必须判为 SKIP
   - 分享视频、小说、图片、音频或资料合集
   - 标题或正文出现作品名、合集、文件大小、文件数量、下载方式、网盘、磁力或 ED2K 等资源信息
   - 预览、整理、自抓、归档类内容，只要提供或介绍具体作品资源，也属于 NORMAL

2. 非正常帖（SKIP）—— 以下任何一条即判定：
   - 钓鱼帖：提示回复会封号、测试帖、陷阱帖
   - 管理帖：公告、通知、版规、规则
   - 广告帖：招聘、高薪、兼职、推广、加群、联系方式
   - 讨论帖：求助、提问、投票、闲聊、吐槽
   - 没有实际资源链接，只有预览、介绍、标题或讨论的帖子
   - 任何不在分享具体可下载内容的帖子

请只回复以下两个选项之一：
- NORMAL（可下载内容分享帖，可以回复）
- SKIP（非资源帖，不要回复）

你的判断："""

            # 调用AI接口
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你只根据论坛帖子的结构和用途进行分类。忽略内容题材，仅输出 NORMAL 或 SKIP。"},
                    {"role": "user", "content": detect_prompt}
                ],
                "temperature": 0.3,  # 降低温度，提高判断准确性
                "max_tokens": 50
            }
            
            url = self.api_url or "https://api.openai.com/v1/chat/completions"
            
            self.logger.info(f"AI检测帖子类型...")
            
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout,
                    proxies=self.proxies
                )
            except requests.exceptions.Timeout:
                self.logger.warning(f"AI检测超时（{self.timeout}秒）")
                return 'ERROR'
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"AI检测请求失败: {str(e)[:100]}")
                return 'ERROR'
            
            if response.status_code == 200:
                result = response.json()
                raw_type = result['choices'][0]['message']['content'].strip()
                post_type = raw_type.upper()
                self.logger.info(f"AI原始判断: {raw_type[:80]}")
                
                # 解析AI返回的类型
                token_match = re.search(r"\b(NORMAL|SKIP)\b", post_type)
                if token_match and token_match.group(1) == 'NORMAL':
                    self.logger.info(f"AI判断: 正常资源帖")
                    result_type = 'NORMAL'
                else:
                    self.logger.info(f"AI判断: 非资源帖，跳过")
                    result_type = 'SKIP'
                # 写入缓存
                self._type_cache[cache_key] = result_type
                self._save_type_cache()
                return result_type
            else:
                self.logger.error(f"AI检测失败: {response.status_code}")
                return 'ERROR'
                
        except Exception as e:
            self.logger.error(f"AI检测帖子类型失败: {e}")
            return 'ERROR'
    
    def _detect_by_keywords(self, title: str, content: str = "") -> str:
        """
        使用关键词检测帖子类型（降级方案）
        """
        full_text = f"{title} {content}".lower()
        
        # 钓鱼帖关键词
        fishing_keywords = [
            '钓鱼帖', '钓鱼贴', '钓鱼', 
            '永久封号', '全永久封号', '封号',
            '别回复', '不要回复', '禁止回复',
            '回复本帖', '编辑回复',
            '你号就没了', '号就没了',
            '测试帖', '测试贴'
        ]
        
        # 管理帖关键词
        admin_keywords = [
            '版规', '公告', '通知', '规则',
            '管理员', '版主', '禁止', '违规',
            '【公告】', '【通知】', '【规则】'
        ]

        # 广告/垃圾帖关键词
        spam_keywords = [
            '招聘', '高薪', '兼职', '日结', '日薪',
            '月入', '代理', '加盟', '推广',
            '联系方式', '加微信', '加QQ', 'telegram',
            '破解', '外挂', '刷单', '赌博', '彩票'
        ]
        
        for keyword in fishing_keywords:
            if keyword in full_text:
                self.logger.info(f"关键词检测: 钓鱼帖 (关键词: {keyword})")
                return 'FISHING'
        
        for keyword in admin_keywords:
            if keyword in full_text:
                self.logger.info(f"关键词检测: 管理帖 (关键词: {keyword})")
                return 'ADMIN'

        for keyword in spam_keywords:
            if keyword in full_text:
                self.logger.info(f"关键词检测: 广告/垃圾帖 (关键词: {keyword})")
                return 'SPAM'

        return 'NORMAL'
    
    def generate_reply(self, title: str, content: str = "") -> Optional[str]:
        """
        调用AI生成回复
        
        Args:
            title: 帖子标题
            content: 帖子内容（可选）
        
        Returns:
            生成的回复内容，失败返回None，钓鱼帖/管理帖返回'SKIP_FISHING_POST'或'SKIP_ADMIN_POST'
        """
        if not self.is_enabled():
            self.logger.warning("AI回复未启用或API Key未配置")
            return None
        
        try:
            # 第一步：使用AI判断帖子类型
            post_type = self._detect_post_type(title, content)
            
            if post_type == 'ERROR':
                return 'SKIP_POST'
            elif post_type != 'NORMAL':
                return 'SKIP_POST'
            
            # 第二步：如果是正常帖子，生成回复
            # 构建提示词
            user_prompt = f"帖子标题：{title}"
            if content:
                # 限制内容长度，避免token过多
                content_preview = content[:500] if len(content) > 500 else content
                user_prompt += f"\n帖子内容：{content_preview}"
            user_prompt += "\n\n请生成一条简短的回复（不超过50字）："
            
            # 根据API类型调用不同接口
            if self.api_type == 'openai':
                reply = self._call_openai_api(user_prompt)
            elif self.api_type == 'claude':
                reply = self._call_claude_api(user_prompt)
            elif self.api_type == 'custom':
                reply = self._call_custom_api(user_prompt)
            else:
                self.logger.error(f"不支持的API类型: {self.api_type}")
                return None
            return self._validate_generated_reply(reply)
                
        except Exception as e:
            self.logger.error(f"AI生成回复失败: {str(e)}")
            return None
    
    def _call_openai_api(self, prompt: str) -> Optional[str]:
        """调用OpenAI兼容接口"""
        try:
            url = self.api_url or "https://api.openai.com/v1/chat/completions"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            
            self.logger.info(f"调用AI接口: {url} (model: {self.model})")
            
            try:
                response = requests.post(
                    url, 
                    headers=headers, 
                    json=data, 
                    timeout=self.timeout,
                    proxies=self.proxies
                )
            except requests.exceptions.Timeout:
                self.logger.error(f"AI接口请求超时（{self.timeout}秒）")
                try:
                    StatsManager().record_ai_error()
                except:
                    pass
                return None
            except requests.exceptions.RequestException as e:
                self.logger.error(f"AI接口请求失败: {str(e)[:100]}")
                try:
                    StatsManager().record_ai_error()
                except:
                    pass
                return None
            
            if response.status_code == 200:
                result = response.json()
                reply = result['choices'][0]['message']['content'].strip()
                self.logger.info(f"AI生成回复: {reply}")
                return reply
            else:
                self.logger.error(f"AI接口返回错误: {response.status_code} - {response.text}")
                # 记录AI调用失败统计
                try:
                    StatsManager().record_ai_error()
                except:
                    pass
                return None
                
        except requests.exceptions.Timeout:
            self.logger.error("AI接口请求超时")
            # 记录AI调用失败统计
            try:
                StatsManager().record_ai_error()
            except:
                pass
            return None
        except Exception as e:
            self.logger.error(f"OpenAI API调用失败: {str(e)}")
            # 记录AI调用失败统计
            try:
                StatsManager().record_ai_error()
            except:
                pass
            return None
    
    def _call_claude_api(self, prompt: str) -> Optional[str]:
        """调用Claude API"""
        try:
            url = self.api_url or "https://api.anthropic.com/v1/messages"
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            data = {
                "model": self.model or "claude-3-haiku-20240307",
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "system": self.system_prompt,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            self.logger.info(f"调用Claude接口: {url}")
            
            response = requests.post(
                url, 
                headers=headers, 
                json=data, 
                timeout=self.timeout,
                proxies=self.proxies
            )
            
            if response.status_code == 200:
                result = response.json()
                reply = result['content'][0]['text'].strip()
                self.logger.info(f"AI生成回复: {reply}")
                return reply
            else:
                self.logger.error(f"Claude接口返回错误: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Claude API调用失败: {str(e)}")
            return None
    
    def _call_custom_api(self, prompt: str) -> Optional[str]:
        """
        调用自定义API接口
        
        自定义接口需要返回以下JSON格式：
        {
            "reply": "生成的回复内容"
        }
        或者OpenAI兼容格式
        """
        try:
            if not self.api_url:
                self.logger.error("自定义API URL未配置")
                return None
            
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            # 尝试通用格式
            data = {
                "prompt": prompt,
                "system_prompt": self.system_prompt,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            
            self.logger.info(f"调用自定义接口: {self.api_url}")
            
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=data, 
                timeout=self.timeout,
                proxies=self.proxies
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 尝试多种响应格式
                reply = None
                if 'reply' in result:
                    reply = result['reply']
                elif 'response' in result:
                    reply = result['response']
                elif 'choices' in result:
                    # OpenAI格式
                    reply = result['choices'][0]['message']['content']
                elif 'content' in result:
                    # Claude格式
                    if isinstance(result['content'], list):
                        reply = result['content'][0]['text']
                    else:
                        reply = result['content']
                
                if reply:
                    reply = reply.strip()
                    self.logger.info(f"AI生成回复: {reply}")
                    return reply
                else:
                    self.logger.error(f"无法解析自定义API响应: {result}")
                    return None
            else:
                self.logger.error(f"自定义接口返回错误: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"自定义API调用失败: {str(e)}")
            return None
    
    def test_connection(self) -> dict:
        """
        测试AI接口连接
        
        Returns:
            {"success": bool, "message": str}
        """
        if not self.is_enabled():
            return {
                "success": False,
                "message": "AI回复未启用或API Key未配置"
            }
        
        try:
            test_reply = self.generate_reply("测试帖子标题", "这是一个测试内容")
            
            if test_reply:
                return {
                    "success": True,
                    "message": f"连接成功！测试回复: {test_reply}"
                }
            else:
                return {
                    "success": False,
                    "message": "API调用失败，请检查配置"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"测试失败: {str(e)}"
            }
