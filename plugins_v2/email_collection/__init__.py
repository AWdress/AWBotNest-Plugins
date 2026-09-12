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
    "version": "0.0.1",
    "author": "AWdress",
    "description": "实时监控多个 IMAP 邮箱，按验证码和关键词过滤后通过平台通知。",
    "icon": "https://raw.githubusercontent.com/EWEDLCM/MoviePilot-Plugins/main/icons/yjj.png",
    "changelog": "v0.0.1 首次发布\n- 使用 AWBotNest V2 原生可取消后台任务、异步存储和平台通知接口\n- 支持多邮箱、验证码提取、关键词过滤、全部推送和历史去重",
    "scope": "user",
    "plugin_api_version": 2,
    "default_enabled": False,
    "requirements": [],
    "config_schema": {
        "enabled": {"type": "boolean", "default": False, "label": "启用邮件监控", "section": "功能开关", "order": 1},
        "push_all": {"type": "boolean", "default": False, "label": "全部推送", "section": "功能开关", "order": 2},
        "mailboxes": {"type": "textarea", "default": "", "label": "邮箱配置", "help": "每行：邮箱地址|授权码；支持 QQ/163/126/Gmail/Outlook。", "section": "邮箱", "order": 10, "secret": True},
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


def _poll(box: Dict[str, str], seen: set[str]) -> List[Dict[str, str]]:
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
        found.append({"邮箱":box["email"],"发件人":sender[:120],"标题":subject[:200],"内容":body[:3000],"验证码":otp.group(1) if otp else "", "_key":key})
    try: mail.logout()
    except Exception: pass
    return found


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
                    seen.add(msg.pop("_key")); subject=msg["标题"]; body=msg["内容"]
                    is_verification=bool(msg.get("验证码")) or any(k in (subject+" "+body).lower() for k in ("验证码","verification","otp","verify"))
                    if not cfg.get("push_all", False) and not is_verification and not any(k in (subject+" "+body).lower() for k in keywords): continue
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
