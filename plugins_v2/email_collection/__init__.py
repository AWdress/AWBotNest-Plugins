"""邮件集：AWBotNest V2 原生 IMAP 实时监控插件。"""
from __future__ import annotations

import asyncio
import email
import email.header
import email.message
import html
import imaplib
import re
from email.header import decode_header
from html.parser import HTMLParser
from typing import Any, Dict, List

__plugin__ = {
    "name": "邮件集",
    "id": "email_collection",
    "version": "0.0.3",
    "author": "AWdress",
    "description": "实时监控多个 IMAP 邮箱，支持验证码识别、关键词过滤、AI 验证码提取和 AI 邮件概要。",
    "icon": "https://raw.githubusercontent.com/EWEDLCM/MoviePilot-Plugins/main/icons/yjj.png",
    "changelog": "v0.0.3 修正独立运行与配置保存\n- 调整为独立插件，IMAP 监控只运行一份，避免重复连接和重复通知\n- 按平台 schema 规范修正邮箱配置、AI 提示词与超时字段，解决保存失败\n\nv0.0.2 接入平台统一 AI\n- 新增 AI 验证码识别，支持邮件正文和首张图片附件\n- 新增 AI 邮件概要和自定义提示词\n- AI 不可用或调用失败时自动使用原邮件，不中断监控与通知\n\nv0.0.1 首次发布\n- 使用 AWBotNest V2 原生可取消后台任务、异步存储和平台通知接口\n- 支持多邮箱、验证码提取、关键词过滤、全部推送和历史去重",
    "scope": "standalone",
    "plugin_api_version": 2,
    "tags": ["邮件监控", "验证码", "通知推送"],
    "default_enabled": False,
    "requirements": [],
    "config_schema": {
        "enabled": {"type": "boolean", "default": False, "label": "启用邮件监控", "section": "功能开关", "order": 1},
        "push_all": {"type": "boolean", "default": False, "label": "全部推送", "section": "功能开关", "order": 2},
        "ai_verification": {"type": "boolean", "default": False, "label": "AI 验证码识别", "help": "通过平台统一 AI 识别邮件正文或图片中的验证码。", "section": "AI 功能", "order": 30},
        "ai_summary_enabled": {"type": "boolean", "default": False, "label": "AI 邮件概要", "help": "仅对符合推送条件的邮件生成简洁中文概要。", "section": "AI 功能", "order": 31},
        "verification_prompt": {"type": "text", "default": "", "label": "验证码提示词", "help": "留空使用内置提示词。", "section": "AI 功能", "cols": 12, "order": 32},
        "summary_prompt": {"type": "text", "default": "", "label": "概要提示词", "help": "留空使用内置提示词。", "section": "AI 功能", "cols": 12, "order": 33},
        "ai_timeout": {"type": "number", "default": 60, "min": 10, "max": 180, "step": 1, "label": "AI 超时（秒）", "section": "AI 功能", "order": 34},
        "mailboxes": {"type": "text", "default": "", "label": "邮箱配置", "help": "每行：邮箱地址|授权码；支持 QQ/163/126/Gmail/Outlook。", "section": "邮箱", "cols": 12, "order": 10, "secret": True},
        "keywords": {"type": "string", "default": "验证码|重要通知|账单|订单", "label": "关键词（用 | 分隔）", "section": "过滤", "order": 20},
        "poll_seconds": {"type": "number", "default": 30, "min": 10, "max": 300, "label": "轮询间隔（秒）", "section": "运行设置", "order": 21},
    },
}

IMAP_HOSTS = {"qq.com": "imap.qq.com", "163.com": "imap.163.com", "126.com": "imap.126.com", "gmail.com": "imap.gmail.com", "outlook.com": "outlook.office365.com", "sina.com": "imap.sina.com"}
OTP_RE = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "head"}: self.skip += 1
        elif not self.skip and tag.lower() in {"p", "div", "br", "li", "tr"}: self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "head"} and self.skip: self.skip -= 1
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def _decode(value: str) -> str:
    out=[]
    for part, enc in decode_header(value or ""):
        if isinstance(part, bytes):
            try: out.append(part.decode(enc or "utf-8", errors="replace"))
            except Exception: out.append(part.decode("utf-8", errors="replace"))
        else: out.append(str(part))
    return "".join(out).strip()


def _body(msg: email.message.Message) -> str:
    plain=[]; html_parts=[]
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_maintype() == "multipart": continue
        data = part.get_payload(decode=True) or b""
        text = data.decode(part.get_content_charset() or "utf-8", errors="replace")
        if part.get_content_type() == "text/plain": plain.append(text)
        elif part.get_content_type() == "text/html": html_parts.append(text)
    if plain: return "\n".join(plain).strip()
    parser=_Text(); parser.feed("\n".join(html_parts)); return html.unescape("".join(parser.parts)).strip()


def _parse_boxes(raw: str) -> List[Dict[str, str]]:
    out=[]
    for line in str(raw or "").splitlines():
        if "|" not in line: continue
        addr, password = line.split("|", 1); addr=addr.strip(); password=password.strip()
        host=IMAP_HOSTS.get(addr.rsplit("@",1)[-1].lower())
        if addr and password and host: out.append({"email":addr,"password":password,"host":host})
    return out


def _poll(box: Dict[str, str], seen: set[str]) -> List[Dict[str, Any]]:
    found=[]; mail=imaplib.IMAP4_SSL(box["host"], 993); mail.login(box["email"],box["password"]); mail.select("INBOX")
    status,data=mail.search(None,"UNSEEN")
    if status != "OK": mail.logout(); return found
    for raw_id in data[0].split()[-30:]:
        uid=raw_id.decode(); key=f"{box['email']}:{uid}"
        if key in seen: continue
        status,msgdata=mail.fetch(raw_id,"(RFC822)")
        if status != "OK": continue
        msg=email.message_from_bytes(next((x[1] for x in msgdata if isinstance(x,tuple)),b""))
        subject=_decode(msg.get("Subject","")); sender=_decode(msg.get("From","")); body=_body(msg); otp=OTP_RE.search(body)
        images = []
        for part in msg.walk() if msg.is_multipart() else [msg]:
            if part.get_content_maintype() != "image":
                continue
            payload = part.get_payload(decode=True) or b""
            if payload and len(payload) <= 5 * 1024 * 1024:
                images.append(payload)
                break
        found.append({"邮箱":box["email"],"发件人":sender[:120],"标题":subject[:200],"内容":body[:3000],"验证码":otp.group(1) if otp else "", "_key":key, "_images": images})
    try: mail.logout()
    except Exception: pass
    return found


def _ai_available(ctx, capability: str) -> bool:
    ai = getattr(ctx, "ai", None)
    if not ai:
        return False
    checker = getattr(ai, "is_available", None)
    if callable(checker):
        try:
            return bool(checker(capability))
        except Exception:
            return False
    return bool(getattr(ai, "available", False))


async def _ai_code(ctx, msg: Dict[str, Any], images: List[bytes], cfg: Dict[str, Any]) -> str:
    custom = str(cfg.get("verification_prompt") or "").strip()
    prompt = custom or "请找出这封邮件中的一次性验证码。只输出 4至8 位验证码；若没有，只输出“无验证码”。"
    context = f"\n\n邮件标题：{msg.get('标题', '')}\n发件人：{msg.get('发件人', '')}\n邮件内容：\n{str(msg.get('内容', ''))[:8000]}"
    timeout = max(10, min(180, int(cfg.get("ai_timeout", 60) or 60)))
    if images and _ai_available(ctx, "image"):
        response = await asyncio.wait_for(ctx.ai.vision(image=images[0], prompt=prompt + context), timeout=timeout)
    elif _ai_available(ctx, "text"):
        response = await asyncio.wait_for(ctx.ai.chat(prompt=prompt + context, temperature=0), timeout=timeout)
    else:
        raise RuntimeError("平台 AI 验证码能力不可用")
    matched = OTP_RE.search(str(response or ""))
    return matched.group(1) if matched else ""


async def _ai_summary(ctx, msg: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    if not _ai_available(ctx, "text"):
        raise RuntimeError("平台 AI 文本能力不可用")
    custom = str(cfg.get("summary_prompt") or "").strip()
    prompt = custom or "请用简洁中文概括邮件的核心信息、重要数字、截止时间和需要执行的动作。不要编造内容，控制在 180 字内。"
    content = f"\n\n邮件标题：{msg.get('标题', '')}\n发件人：{msg.get('发件人', '')}\n邮件内容：\n{str(msg.get('内容', ''))[:8000]}"
    timeout = max(10, min(180, int(cfg.get("ai_timeout", 60) or 60)))
    result = await asyncio.wait_for(ctx.ai.chat(prompt=prompt + content, temperature=0.2), timeout=timeout)
    return str(result or "").strip()[:1000]


async def setup(ctx):
    task=None; seen=set(str(x) for x in (await ctx.storage.get("seen", []) or []))

    async def monitor():
        nonlocal seen
        while True:
            cfg=dict(ctx.config or {}); boxes=_parse_boxes(cfg.get("mailboxes", "")); keywords=[x.strip().lower() for x in str(cfg.get("keywords", "") or "").split("|") if x.strip()]
            for box in boxes:
                try: messages=await asyncio.to_thread(_poll, box, seen)
                except Exception as exc:
                    ctx.log.error(f"[邮件集] {box['email']} 轮询失败：{exc}"); continue
                for msg in messages:
                    seen.add(msg.pop("_key")); images = msg.pop("_images", []); subject=msg["标题"]; body=msg["内容"]
                    is_verification=bool(msg.get("验证码")) or any(k in (subject+" "+body).lower() for k in ("验证码","verification","otp","verify"))
                    if not cfg.get("push_all", False) and not is_verification and not any(k in (subject+" "+body).lower() for k in keywords): continue
                    if cfg.get("ai_verification", False) and is_verification:
                        try:
                            code = await _ai_code(ctx, msg, images, cfg)
                            if code:
                                msg["验证码"] = code
                                msg["AI 识别"] = "已确认验证码"
                                ctx.log.info(f"[邮件集] AI 验证码识别成功：{box['email']} / {subject}")
                            else:
                                msg["AI 识别"] = "未识别到验证码"
                        except Exception as exc:
                            ctx.log.warning(f"[邮件集] AI 验证码识别失败，使用本地结果：{exc}")
                    if cfg.get("ai_summary_enabled", False):
                        try:
                            summary = await _ai_summary(ctx, msg, cfg)
                            if summary:
                                msg["AI 概要"] = summary
                                msg.pop("内容", None)
                                ctx.log.info(f"[邮件集] AI 概要生成成功：{box['email']} / {subject}")
                        except Exception as exc:
                            ctx.log.warning(f"[邮件集] AI 概要生成失败，推送原邮件：{exc}")
                    rows=[{"项目":k,"内容":str(v)} for k,v in msg.items() if v]
                    await ctx.notify(rows, category="邮件集"); ctx.log.info(f"[邮件集] 已推送 {box['email']}：{subject}")
            if len(seen)>2000: seen=set(list(seen)[-1000:])
            await ctx.storage.set("seen", list(seen)[-2000:]); await asyncio.sleep(max(10,int(cfg.get("poll_seconds",30) or 30)))

    if (ctx.config or {}).get("enabled"):
        task=ctx.create_task(monitor(), name="邮件集·IMAP监控"); ctx.log.info("[邮件集] IMAP 监控已启动")
    async def cleanup():
        if task and not task.done(): task.cancel(); await asyncio.gather(task, return_exceptions=True)
    ctx.add_cleanup(cleanup)


async def teardown(ctx):
    ctx.log.info("[邮件集] 插件已停用")
