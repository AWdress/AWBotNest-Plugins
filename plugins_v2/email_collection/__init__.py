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
    "version": "0.0.12",
    "author": "AWdress",
    "description": "近实时轮询多个 IMAP 邮箱，支持已读回查、验证码识别、关键词过滤和 AI 邮件概要。",
    "icon": "https://raw.githubusercontent.com/EWEDLCM/MoviePilot-Plugins/main/icons/yjj.png",
    "changelog": "v0.0.10 修复验证码误判与立即检查超时\n- 验证码改为结合验证语义提取，不再把年份、账单日期等普通数字当作验证码\n- AI 未确认验证码时撤销误识别，仅因验证码候选命中的邮件会直接跳过\n- 立即检查默认回查 10 封，并为 AI 处理预留接口超时安全余量\n- 推送所有新邮件开关会忽略关键词和验证码筛选\n\nv0.0.9 修复通知投递与轮询日志\n- 统一使用平台富文本通知，并兼容新旧平台的投递返回值\n- Bot 通知不可用时明确记录已回退到主账号收藏夹，不再误报已通知\n- 自动轮询在无新邮件且无错误时保持静默，手动检查仍保留完整日志\n- 清理重复的插件名日志前缀\n\nv0.0.8 修复立即检查无响应\n- 立即检查不再先保存并触发插件重载，避免旧配置页请求被中断\n- 收到检查请求、任务占用、配置缺失和扫描完成均输出明确日志\n- 配置有未保存修改时明确提示先保存，避免误用旧配置\n\nv0.0.7 改进多邮箱配置\n- 邮箱改为逐个添加和删除，每行可选择 QQ、163、126、Gmail、Outlook 或新浪邮箱\n- 每个授权码默认隐藏并可独立显示，旧单行和多行配置自动迁移且不丢失账号\n- 自定义配置页保留立即检查，可回查近期已读和未读邮件\n\nv0.0.6 新增立即检查\n- 配置页新增立即检查按钮，可回查近期已读和未读邮件\n- 手动检查与后台轮询共用处理逻辑和互斥锁，避免并发重复推送\n- 使用稳定 IMAP UID 并以 PEEK 方式读取，不会把后台检查的未读邮件标为已读\n\nv0.0.5 适配平台敏感配置规范\n- 邮箱授权码改为受控显示的 password 字段，公开配置接口不再泄露\n- 多邮箱改用“ & ”分隔的单行格式，并自动迁移旧换行配置\n\nv0.0.4 修复配置显示与 AI 识图\n- 邮箱地址和授权码配置改为直接显示，避免整段掩码后无法检查\n- 首次启用自动写入 schema 默认值\n- 图片验证码正确检查平台视觉能力，不再误用生图能力状态\n\nv0.0.3 修正独立运行与配置保存\n- 调整为独立插件，IMAP 监控只运行一份，避免重复连接和重复通知\n- 按平台 schema 规范修正邮箱配置、AI 提示词与超时字段，解决保存失败\n\nv0.0.2 接入平台统一 AI\n- 新增 AI 验证码识别，支持邮件正文和首张图片附件\n- 新增 AI 邮件概要和自定义提示词\n- AI 不可用或调用失败时自动使用原邮件，不中断监控与通知\n\nv0.0.1 首次发布\n- 使用 AWBotNest V2 原生可取消后台任务、异步存储和平台通知接口\n- 支持多邮箱、验证码提取、关键词过滤、全部推送和历史去重",
    "scope": "standalone",
    "plugin_api_version": 2,
    "tags": ["邮件监控", "验证码", "通知推送"],
    "default_enabled": False,
    "render_mode": "vue",
    "requirements": [],
    "config_schema": {
        "enabled": {"type": "boolean", "default": False, "label": "启用邮件监控", "section": "功能开关", "order": 1},
        "push_all": {
            "type": "boolean", "default": False, "label": "推送所有新邮件（忽略筛选）",
            "help": "开启后普通邮件也会推送；关闭后只推送命中关键词或验证码的邮件。",
            "section": "功能开关", "order": 2,
        },
        "ai_verification": {"type": "boolean", "default": False, "label": "AI 验证码识别", "help": "通过平台统一 AI 识别邮件正文或图片中的验证码。", "section": "AI 功能", "order": 30},
        "ai_summary_enabled": {"type": "boolean", "default": False, "label": "AI 邮件概要", "help": "仅对符合推送条件的邮件生成简洁中文概要。", "section": "AI 功能", "order": 31},
        "verification_prompt": {"type": "text", "default": "", "label": "验证码提示词", "help": "留空使用内置提示词。", "section": "AI 功能", "cols": 12, "order": 32},
        "summary_prompt": {"type": "text", "default": "", "label": "概要提示词", "help": "留空使用内置提示词。", "section": "AI 功能", "cols": 12, "order": 33},
        "ai_timeout": {"type": "number", "default": 60, "min": 10, "max": 180, "step": 1, "label": "AI 超时（秒）", "section": "AI 功能", "order": 34},
        "mailboxes": {
            "type": "list", "default": [], "label": "邮箱账号", "item_label": "邮箱",
            "secret": True, "help": "逐个添加邮箱，授权码默认隐藏并由平台受控保存。",
            "section": "邮箱", "cols": 12, "order": 10,
            "fields": {
                "provider": {
                    "type": "select", "label": "邮箱类型",
                    "options": [
                        {"value": "qq", "label": "QQ 邮箱"},
                        {"value": "163", "label": "163 邮箱"},
                        {"value": "126", "label": "126 邮箱"},
                        {"value": "gmail", "label": "Gmail"},
                        {"value": "outlook", "label": "Outlook"},
                        {"value": "sina", "label": "新浪邮箱"},
                    ],
                },
                "email": {"type": "string", "label": "邮箱地址"},
                "password": {"type": "password", "label": "授权码或应用密码"},
            },
        },
        "keywords": {"type": "string", "default": "验证码|重要通知|账单|订单", "label": "关键词（用 | 分隔）", "section": "过滤", "order": 20},
        "poll_seconds": {"type": "number", "default": 30, "min": 10, "max": 300, "label": "轮询间隔（秒）", "section": "运行设置", "order": 21},
        "manual_check_limit": {"type": "number", "default": 10, "min": 1, "max": 500, "step": 1, "label": "立即检查回查数量", "help": "点击立即检查时，每个邮箱回查最近多少封邮件；包含已读和未读邮件。", "section": "运行设置", "order": 22},
        "check_now": {"type": "action", "label": "立即检查", "action": "check_now", "help": "立即回查近期已读和未读邮件，已处理邮件不会重复推送。", "section": "操作", "cols": 6, "order": 40},
    },
}

__plugin__["changelog"] = (
    "v0.0.12 适配平台正式 AI 能力接口\n"
    "- 验证码识别与邮件概要直接使用平台 is_available 能力判断\n"
    "- 不再探测旧 AI 可用状态字段\n\n"
    "v0.0.11 复核授权码独立显隐\n"
    "- 多邮箱授权码继续逐行默认隐藏，每行提供独立眼睛按钮\n"
    "- 邮箱列表由平台受控读取真实值，避免显示脱敏占位符\n\n"
    + __plugin__["changelog"]
)

PROVIDER_HOSTS = {
    "qq": "imap.qq.com",
    "163": "imap.163.com",
    "126": "imap.126.com",
    "gmail": "imap.gmail.com",
    "outlook": "outlook.office365.com",
    "sina": "imap.sina.com",
}
DOMAIN_PROVIDERS = {
    "qq.com": "qq",
    "163.com": "163",
    "126.com": "126",
    "gmail.com": "gmail",
    "outlook.com": "outlook",
    "hotmail.com": "outlook",
    "live.com": "outlook",
    "sina.com": "sina",
    "sina.cn": "sina",
}
OTP_RE = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")
VERIFICATION_HINT_RE = re.compile(
    r"验证码|校验码|动态码|安全码|一次性(?:密码|代码)|"
    r"verification(?:\s+code)?|security\s+code|one[-\s]?time(?:\s+password|\s+code)?|\botp\b",
    re.IGNORECASE,
)
OTP_AFTER_HINT_RE = re.compile(
    r"(?:" + VERIFICATION_HINT_RE.pattern + r")[^\d]{0,32}(?<!\d)(\d{4,8})(?!\d)",
    re.IGNORECASE,
)
OTP_BEFORE_HINT_RE = re.compile(
    r"(?<!\d)(\d{4,8})(?!\d)[^\d]{0,20}(?:" + VERIFICATION_HINT_RE.pattern + r")",
    re.IGNORECASE,
)


def _has_verification_hint(text: str) -> bool:
    return bool(VERIFICATION_HINT_RE.search(str(text or "")))


def _extract_otp(subject: str, body: str) -> str:
    """只在验证语义附近提取数字，避免将年份、日期、金额误当验证码。"""
    content = f"{subject or ''}\n{body or ''}"
    matched = OTP_AFTER_HINT_RE.search(content) or OTP_BEFORE_HINT_RE.search(content)
    return matched.group(1) if matched else ""


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


def _parse_boxes(raw: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            addr = str(item.get("email") or "").strip()
            password = str(item.get("password") or "").strip()
            provider = str(item.get("provider") or "").strip().lower()
            if not provider and "@" in addr:
                provider = DOMAIN_PROVIDERS.get(addr.rsplit("@", 1)[-1].lower(), "")
            host = PROVIDER_HOSTS.get(provider)
            if addr and password and host:
                out.append({
                    "provider": provider,
                    "email": addr,
                    "password": password,
                    "host": host,
                })
        return out
    for line in re.split(r"(?:\r?\n|\s+&\s+)", str(raw or "")):
        if "|" not in line: continue
        addr, password = line.split("|", 1); addr=addr.strip(); password=password.strip()
        provider = DOMAIN_PROVIDERS.get(addr.rsplit("@", 1)[-1].lower()) if "@" in addr else None
        host = PROVIDER_HOSTS.get(provider or "")
        if addr and password and host:
            out.append({"provider": provider or "", "email": addr, "password": password, "host": host})
    return out


def _poll(
    box: Dict[str, str],
    seen: set[str],
    *,
    include_read: bool = False,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    """读取一批邮件；后台只查未读，手动检查可查已读和未读。"""
    found: List[Dict[str, Any]] = []
    mail = imaplib.IMAP4_SSL(box["host"], 993, timeout=30)
    try:
        mail.login(box["email"], box["password"])
        status, _ = mail.select("INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError("无法打开收件箱")
        criteria = "ALL" if include_read else "UNSEEN"
        status, data = mail.uid("search", None, criteria)
        if status != "OK":
            raise RuntimeError(f"IMAP 搜索失败：{criteria}")
        raw_ids = (data[0] if data else b"").split()
        for raw_uid in raw_ids[-max(1, int(limit or 1)):]:
            uid = raw_uid.decode(errors="replace")
            key = f"{box['email']}:{uid}"
            if key in seen:
                continue
            # BODY.PEEK[] 配合只读收件箱，检查不会把未读邮件改为已读。
            status, msgdata = mail.uid("fetch", raw_uid, "(BODY.PEEK[])")
            if status != "OK":
                continue
            payload = next((item[1] for item in msgdata if isinstance(item, tuple)), b"")
            if not payload:
                continue
            msg = email.message_from_bytes(payload)
            subject = _decode(msg.get("Subject", ""))
            sender = _decode(msg.get("From", ""))
            body = _body(msg)
            otp = _extract_otp(subject, body)
            images = []
            for part in msg.walk() if msg.is_multipart() else [msg]:
                if part.get_content_maintype() != "image":
                    continue
                image = part.get_payload(decode=True) or b""
                if image and len(image) <= 5 * 1024 * 1024:
                    images.append(image)
                    break
            found.append({
                "邮箱": box["email"],
                "发件人": sender[:120],
                "标题": subject[:200],
                "内容": body[:3000],
                "验证码": otp,
                "_key": key,
                "_images": images,
            })
    finally:
        try:
            mail.logout()
        except Exception:
            pass
    return found


def _ai_available(ctx, capability: str) -> bool:
    try:
        return bool(ctx.ai.is_available(capability))
    except Exception:
        return False


async def _ai_code(ctx, msg: Dict[str, Any], images: List[bytes], cfg: Dict[str, Any]) -> str:
    custom = str(cfg.get("verification_prompt") or "").strip()
    prompt = custom or "请找出这封邮件中的一次性验证码。只输出 4至8 位验证码；若没有，只输出“无验证码”。"
    context = f"\n\n邮件标题：{msg.get('标题', '')}\n发件人：{msg.get('发件人', '')}\n邮件内容：\n{str(msg.get('内容', ''))[:8000]}"
    timeout = max(10, min(180, int(cfg.get("ai_timeout", 60) or 60)))
    if images and _ai_available(ctx, "vision"):
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
    defaults = {
        key: spec["default"]
        for key, spec in __plugin__["config_schema"].items()
        if "default" in spec and spec.get("type") != "action" and key not in ctx.config
    }
    if defaults:
        ctx.update_config(defaults)
    migration_key = "manual_check_limit_default_v0010"
    if not await ctx.storage.get(migration_key, False):
        if ctx.config.get("manual_check_limit") == 100:
            ctx.update_config({"manual_check_limit": 10})
        await ctx.storage.set(migration_key, True)
    raw_mailboxes = ctx.config.get("mailboxes")
    if isinstance(raw_mailboxes, str) and raw_mailboxes.strip() and raw_mailboxes != "********":
        normalized = [
            {
                "provider": item["provider"],
                "email": item["email"],
                "password": item["password"],
            }
            for item in _parse_boxes(raw_mailboxes)
        ]
        if normalized:
            ctx.update_config({"mailboxes": normalized})
            ctx.log.info("已将旧邮箱配置迁移为逐账号列表")
    task = None
    seen = set(str(x) for x in (await ctx.storage.get("seen", []) or []))
    check_lock = asyncio.Lock()
    ctx.log.info(
        "插件已加载：已配置 %d 个邮箱，后台监控=%s，通知渠道由配置页底部的平台通知选择决定",
        len(_parse_boxes(ctx.config.get("mailboxes", ""))),
        "开启" if (ctx.config or {}).get("enabled") else "关闭",
    )

    async def check_once(source: str, *, include_read: bool, limit: int) -> Dict[str, Any]:
        nonlocal seen
        automatic = source == "自动轮询"
        manual_deadline = (
            asyncio.get_running_loop().time() + 90
            if source == "立即检查"
            else None
        )
        ai_budget_notice = False

        def bounded_ai_config() -> Dict[str, Any] | None:
            nonlocal ai_budget_notice
            if manual_deadline is None:
                return cfg
            remaining = manual_deadline - asyncio.get_running_loop().time()
            if remaining <= 12:
                if not ai_budget_notice:
                    ctx.log.warning("立即检查接近平台超时限制，剩余邮件跳过 AI 处理")
                    ai_budget_notice = True
                return None
            bounded = dict(cfg)
            configured = max(10, min(180, int(cfg.get("ai_timeout", 60) or 60)))
            bounded["ai_timeout"] = min(configured, max(10, int(remaining) - 2))
            return bounded

        if not automatic:
            ctx.log.info(
                "收到%s请求：范围=%s，每箱最多 %d 封",
                source,
                "已读和未读" if include_read else "未读",
                limit,
            )
        if check_lock.locked():
            if not automatic:
                ctx.log.warning("%s请求被忽略：另一项邮件检查仍在运行", source)
            return {"ok": False, "busy": True, "message": "邮件检查正在运行，请稍后再试。"}

        async with check_lock:
            cfg = dict(ctx.config or {})
            boxes = _parse_boxes(cfg.get("mailboxes", ""))
            if not boxes:
                ctx.log.warning("%s无法执行：没有可用的邮箱配置", source)
                return {"ok": False, "message": "请先填写有效的邮箱和授权码。"}
            keywords = [
                item.strip().lower()
                for item in str(cfg.get("keywords", "") or "").split("|")
                if item.strip()
            ]
            stats = {
                "mailboxes": len(boxes),
                "checked": 0,
                "messages": 0,
                "pushed": 0,
                "skipped": 0,
                "failed": 0,
                "fallback": 0,
            }
            if not automatic:
                ctx.log.info(
                    "开始%s：%d 个邮箱，范围=%s，每箱最多 %d 封",
                    source,
                    len(boxes),
                    "已读和未读" if include_read else "未读",
                    limit,
                )
            for box in boxes:
                try:
                    messages = await asyncio.to_thread(
                        _poll,
                        box,
                        seen,
                        include_read=include_read,
                        limit=limit,
                    )
                    stats["checked"] += 1
                    stats["messages"] += len(messages)
                except Exception as exc:
                    stats["failed"] += 1
                    ctx.log.error(f"{box['email']} {source}失败：{exc}")
                    continue

                for raw_msg in messages:
                    msg = dict(raw_msg)
                    key = str(msg.pop("_key"))
                    images = msg.pop("_images", [])
                    subject = str(msg.get("标题") or "")
                    body = str(msg.get("内容") or "")
                    searchable = (subject + " " + body).lower()
                    is_verification = _has_verification_hint(searchable)
                    push_all = bool(cfg.get("push_all", False))
                    matched_keywords = [
                        keyword for keyword in keywords if keyword in searchable
                    ]
                    keyword_match = bool(matched_keywords)
                    non_verification_keyword_match = any(
                        not _has_verification_hint(keyword)
                        for keyword in matched_keywords
                    )
                    should_push = (
                        push_all
                        or is_verification
                        or keyword_match
                    )
                    if not should_push:
                        seen.add(key)
                        stats["skipped"] += 1
                        continue

                    if cfg.get("ai_verification", False) and is_verification:
                        call_cfg = bounded_ai_config()
                        if call_cfg is not None:
                            try:
                                code = await _ai_code(ctx, msg, images, call_cfg)
                                if code:
                                    msg["验证码"] = code
                                    msg["AI 识别"] = "已确认验证码"
                                    ctx.log.info(f"AI 验证码识别成功：{box['email']} / {subject}")
                                else:
                                    msg.pop("验证码", None)
                            except Exception as exc:
                                ctx.log.warning(f"AI 验证码识别失败，使用本地结果：{exc}")
                        if (
                            not msg.get("验证码")
                            and not push_all
                            and not non_verification_keyword_match
                        ):
                            seen.add(key)
                            stats["skipped"] += 1
                            ctx.log.info(f"AI 未确认验证码，已跳过：{box['email']} / {subject}")
                            continue
                    if cfg.get("ai_summary_enabled", False):
                        call_cfg = bounded_ai_config()
                        if call_cfg is not None:
                            try:
                                summary = await _ai_summary(ctx, msg, call_cfg)
                                if summary:
                                    msg["AI 概要"] = summary
                                    msg.pop("内容", None)
                                    ctx.log.info(f"AI 概要生成成功：{box['email']} / {subject}")
                            except Exception as exc:
                                ctx.log.warning(f"AI 概要生成失败，推送原邮件：{exc}")
                    rows = [{"项目": key_name, "内容": str(value)} for key_name, value in msg.items() if value]
                    try:
                        delivery = await ctx.notify(rows, category="邮件集", format="rich")
                        if delivery is None or delivery is False or (
                            isinstance(delivery, list) and not delivery
                        ):
                            raise RuntimeError("平台通知渠道未返回投递结果")
                    except Exception as exc:
                        stats["failed"] += 1
                        ctx.log.error(f"通知失败 {box['email']} / {subject}：{exc}")
                        continue
                    seen.add(key)
                    stats["pushed"] += 1
                    # 新平台 Bot 投递返回 True，旧平台返回非空结果列表。
                    # 两代平台回退到主账号收藏夹时都直接返回 Telegram Message。
                    if delivery is True or (isinstance(delivery, list) and delivery):
                        ctx.log.info(f"通知渠道已投递 {box['email']}：{subject}")
                    else:
                        stats["fallback"] += 1
                        ctx.log.warning(
                            "Bot 通知渠道未成功投递，平台已回退到主账号收藏夹：%s / %s；"
                            "请在插件配置窗口底部选择可用的通知 Bot",
                            box["email"], subject,
                        )

            if len(seen) > 2000:
                seen = set(list(seen)[-1000:])
            await ctx.storage.set("seen", list(seen)[-2000:])
            stats["ok"] = stats["failed"] == 0
            stats["message"] = (
                f"{source}完成：邮箱 {stats['checked']}/{stats['mailboxes']}，"
                f"发现 {stats['messages']} 封，推送 {stats['pushed']} 封，"
                f"过滤 {stats['skipped']} 封，失败 {stats['failed']} 项。"
            )
            if stats["fallback"]:
                stats["message"] += f"其中 {stats['fallback']} 封回退到主账号收藏夹。"
            if not automatic or stats["messages"] or stats["failed"]:
                ctx.log.info("%s", stats["message"])
            return stats

    async def monitor():
        while True:
            cfg = dict(ctx.config or {})
            await check_once("自动轮询", include_read=False, limit=30)
            await asyncio.sleep(max(10, int(cfg.get("poll_seconds", 30) or 30)))

    @ctx.action("check_now")
    async def check_now():
        cfg = dict(ctx.config or {})
        try:
            limit = max(1, min(500, int(cfg.get("manual_check_limit", 10) or 10)))
        except (TypeError, ValueError):
            limit = 10
        return await check_once("立即检查", include_read=True, limit=limit)

    @ctx.on_api("/check", methods=["POST"])
    async def api_check(request):
        ctx.log.info("配置页已触发立即检查")
        return await check_now()

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(request):
        return {"running": check_lock.locked()}

    if (ctx.config or {}).get("enabled"):
        task=ctx.create_task(monitor(), name="邮件集·IMAP监控"); ctx.log.info("IMAP 监控已启动")
    async def cleanup():
        if task and not task.done(): task.cancel(); await asyncio.gather(task, return_exceptions=True)
    ctx.add_cleanup(cleanup)


async def teardown(ctx):
    ctx.log.info("插件已停用")
