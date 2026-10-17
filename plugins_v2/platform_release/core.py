"""Latest-release announcements, delivered exclusively by the platform Telegram Bot.

Read layout: version first, Beijing publication time, separated changelog paragraphs,
then the original release link. Telegram owns typography and light/dark styling.
No history replay, user-account fallback, or AI-generated changelog summaries.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import html
import json
import re
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit


API = "https://api.github.com/repos/AWdress/AWBotNest/releases/latest"
LIST_API = "https://api.github.com/repos/AWdress/AWBotNest/releases"
RELEASES = "https://github.com/AWdress/AWBotNest/releases"
STATE_KEY = "release_publisher_v1"
TZ = timezone(timedelta(hours=8))
MESSAGE_LIMIT = 3900
MESSAGE_BUDGET = 12


class PublishError(ValueError):
    """An error safe to display without credentials or request URLs."""


class BotError(PublishError):
    def __init__(self, message, *, uncertain=False, retry_after=0):
        super().__init__(message)
        self.uncertain = uncertain
        self.retry_after = retry_after


def _stamp():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def _units(text):
    return len(text.encode("utf-16-le")) // 2


def _visible_units(markup):
    class TextReader(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data)

    reader = TextReader()
    reader.feed(markup)
    return _units("".join(reader.parts))


def _pieces(text, limit):
    chunk, size = [], 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if size + width > limit:
            yield "".join(chunk)
            chunk, size = [], 0
        chunk.append(char)
        size += width
    if chunk:
        yield "".join(chunk)


def parse_targets(raw):
    if not isinstance(raw, str):
        raise PublishError("请在目标群组或频道中每行填写一个 ID 或 @用户名")
    result = []
    for value in re.split(r"[\s,，;；]+", raw.strip()):
        if not value:
            continue
        if re.fullmatch(r"-\d{1,20}", value) and int(value) < 0:
            value = str(int(value))
        elif re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{3,31}", value):
            value = value.lower()
        else:
            raise PublishError("目标格式不正确：请填写负数群组/频道 ID 或 @用户名，不支持用户私聊")
        if value not in result:
            result.append(value)
    if not result:
        raise PublishError("请先填写目标群组或频道，保存配置后再发布")
    if len(result) > 20:
        raise PublishError("一次最多配置 20 个群组或频道")
    return result


def normalize_release(data, *, allow_prereleases=False):
    if not isinstance(data, dict) or data.get("draft") or (data.get("prerelease") and not allow_prereleases):
        raise PublishError("GitHub 没有返回符合所选类型的已发布版本")
    release_id = data.get("id")
    tag = data.get("tag_name")
    published = data.get("published_at")
    if isinstance(release_id, bool) or not isinstance(release_id, int) or release_id <= 0:
        raise PublishError("GitHub 版本 ID 无效，已停止发布")
    if not isinstance(tag, str) or not tag.strip() or len(tag) > 200:
        raise PublishError("GitHub 版本号无效，已停止发布")
    try:
        date = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
        if date.tzinfo is None:
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise PublishError("GitHub 发布时间无效，已停止发布") from None
    body = data.get("body") or ""
    if not isinstance(body, str) or len(body) > 160000:
        raise PublishError("GitHub 更新内容格式或长度异常，已停止发布")
    name = data.get("name") or tag
    if not isinstance(name, str) or len(name) > 300:
        name = tag
    return {"id": release_id, "tag": tag.strip(), "name": name.strip(),
            "published_at": date.isoformat(), "timestamp": date.timestamp(),
            "prerelease": bool(data.get("prerelease")),
            "body": body.replace("\r\n", "\n").replace("\r", "\n"),
            "url": RELEASES + "/tag/" + quote(tag.strip(), safe="")}


def _version(tag):
    match = re.fullmatch(r"[vV]?(\d+(?:\.\d+)+)", tag)
    if not match:
        return None
    numbers = [int(n) for n in match[1].split(".")]
    while numbers and numbers[-1] == 0:
        numbers.pop()
    return tuple(numbers)


def _inline(text):
    """Small safe GitHub-Markdown subset; never pass upstream HTML to Telegram."""
    pattern = r"`([^`]+)`|\*\*([^*]+)\*\*|__([^_]+)__|!?\[([^\]]+)\]\(([^\s)]+)\)"
    out, start = [], 0
    for match in re.finditer(pattern, text):
        out.append(html.escape(text[start:match.start()]))
        code, bold, underline_bold, label, url = match.groups()
        if code is not None:
            out.append("<code>" + html.escape(code) + "</code>")
        elif bold is not None or underline_bold is not None:
            out.append("<b>" + html.escape(bold or underline_bold) + "</b>")
        else:
            try:
                parts = urlsplit(url)
                safe = parts.scheme in {"https", "http"} and parts.netloc and not parts.username and not parts.password
            except ValueError:
                safe = False
            if safe:
                out.append('<a href="' + html.escape(url, quote=True) + '">' + html.escape(label) + "</a>")
            else:
                out.append(html.escape(label + " (" + url + ")"))
        start = match.end()
    out.append(html.escape(text[start:]))
    return "".join(out)


def render_messages(release):
    """Chunk source lines before HTML formatting, keeping every output tag balanced."""
    title = "AWBotNest " + release["tag"] + (" · 预发行版" if release.get("prerelease") else " 发布")
    date = datetime.fromisoformat(release["published_at"]).astimezone(TZ).strftime("%Y-%m-%d %H:%M")
    header = "<b>" + html.escape(title) + "</b>\n发布时间：" + date + "（北京时间）"
    if release["name"] not in {release["tag"], title}:
        header += "\n" + html.escape(release["name"])
    blocks = []
    in_code = False
    for line in (release["body"].strip() or "此版本未填写更新说明，请查看原始发布页面。").split("\n"):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        heading = re.match(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$", line) if not in_code else None
        if heading:
            line = heading[1]
        if not in_code:
            line = re.sub(r"^(\s*)[-*+]\s+", r"\1• ", line)
            if re.fullmatch(r"\s*[-*_]{3,}\s*", line):
                line = ""
        for piece in _pieces(line, 2400) if line else [""]:
            rendered = "<code>" + html.escape(piece) + "</code>" if in_code else _inline(piece)
            if heading:
                rendered = "<b>" + html.escape(piece) + "</b>"
            blocks.append(rendered)
    footer = '\n\n<a href="' + html.escape(release["url"], quote=True) + '">查看 GitHub 发布详情</a>'
    chunks, current = [], header + "\n\n<b>更新内容</b>\n"
    for block in blocks:
        if _visible_units(current + block + "\n" + footer) > MESSAGE_LIMIT:
            chunks.append(current.rstrip())
            current = "<b>AWBotNest " + html.escape(release["tag"]) + " · 更新内容（续）</b>\n\n"
        current += block + "\n"
    chunks.append(current.rstrip() + footer)
    return chunks


def _selected_token(ctx):
    settings = ctx.settings
    specs = {str(spec.id): str(spec.token or "").strip() for spec in settings.bot_specs()}
    routes = getattr(settings, "bot_routing", {}) or {}
    route = str(routes.get(ctx.plugin_id, "") or "").strip()
    if route:
        for candidate in route.split(","):
            if specs.get(candidate.strip()):
                return specs[candidate.strip()]
        raise PublishError("插件指定的渠道没有可用 Telegram Bot，请在平台选择 Bot")
    selected = str(getattr(ctx, "bot_id", "") or getattr(settings, "default_bot_id", "default") or "default")
    token = specs.get(selected, "")
    if not token:
        raise PublishError("平台尚未配置当前 Telegram Bot，请先在平台添加 Bot")
    return token


class ReleasePublisher:
    def __init__(self, ctx):
        self.ctx = ctx
        self.lock = asyncio.Lock()
        self.state = None
        self.identity = None
        self.identity_key = ""

    async def load(self):
        if self.state is not None:
            return
        state = await self.ctx.storage.get(STATE_KEY, None)
        if state is not None and (not isinstance(state, dict) or state.get("schema") != 1):
            raise PublishError("版本缓存格式异常，已停止发布；请保留数据并检查插件存储")
        candidate = state or {"schema": 1, "latest": None, "etag": "", "targets": {}, "aliases": {}}
        if not isinstance(candidate.get("targets"), dict) or not isinstance(candidate.get("aliases"), dict):
            raise PublishError("发送记录格式异常，已停止发布，避免重复发送")
        def restore_release(latest):
            try:
                original = {**latest, "prerelease": latest.get("prerelease", False)}
                checked = normalize_release({"id": latest["id"], "tag_name": latest["tag"],
                                             "published_at": latest["published_at"],
                                             "name": latest["name"], "body": latest["body"],
                                             "prerelease": original["prerelease"]}, allow_prereleases=True)
                if checked != original:
                    raise ValueError
                return checked
            except (AttributeError, KeyError, TypeError, ValueError):
                raise PublishError("最新版本缓存异常，已停止发布，避免误发旧版") from None
        if candidate.get("latest") is not None:
            candidate["latest"] = restore_release(candidate["latest"])
        pages = candidate.get("list_pages", {})
        if not isinstance(pages, dict):
            raise PublishError("预发行列表缓存异常，已停止发布")
        for page in pages.values():
            if not isinstance(page, dict) or not isinstance(page.get("has_next"), bool):
                raise PublishError("预发行分页缓存异常，已停止发布")
            if page.get("candidate") is not None:
                page["candidate"] = restore_release(page["candidate"])
        for record in candidate["targets"].values():
            if not isinstance(record, dict) or not isinstance(record.get("message_ids"), list) or not isinstance(record.get("parts"), list):
                raise PublishError("发送记录异常，已停止发布，避免重复发送")
            if len(record["message_ids"]) > len(record["parts"]) or not record["parts"]:
                raise PublishError("发送进度异常，已停止发布，避免重复发送")
        self.state = candidate

    async def _save(self):
        await self.ctx.storage.set(STATE_KEY, copy.deepcopy(self.state))

    async def _read(self, method, url, *, limit, **kwargs):
        async with self.ctx.http.stream(method, url, timeout=20, follow_redirects=False, **kwargs) as response:
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > limit:
                    raise PublishError("接口响应过大，已停止处理")
            return response.status_code, dict(response.headers), bytes(body)

    async def _github_page(self, url, etag=""):
        if time.time() < self.state.get("github_retry_at", 0):
            raise PublishError("GitHub 请求限流，等待冷却后再检查；不会发布旧缓存")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "AWBotNest-platform-release/0.0.2",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if etag:
            headers["If-None-Match"] = etag
        try:
            status, response_headers, body = await self._read("GET", url, limit=2 * 1024 * 1024, headers=headers)
        except PublishError:
            raise
        except Exception as exc:
            raise PublishError("GitHub 请求失败（%s），请检查平台代理和网络；不会发布旧缓存" % type(exc).__name__) from None
        response_headers = {k.lower(): v for k, v in response_headers.items()}
        self.state["checked_at"] = _stamp()
        if status == 304:
            if not etag:
                raise PublishError("GitHub 返回 304 但没有对应类型的缓存，已停止发布")
            return status, response_headers, None
        if status in {403, 429}:
            try:
                reset = float(response_headers.get("x-ratelimit-reset", 0))
                retry = float(response_headers.get("retry-after", 900))
            except (ValueError, TypeError):
                reset, retry = 0, 900
            self.state["github_retry_at"] = max(time.time() + max(300, retry), reset)
            await self._save()
            raise PublishError("GitHub 返回 HTTP %s，可能请求限流；冷却后再检查，不会发布旧缓存" % status)
        if status != 200:
            raise PublishError("GitHub 版本接口返回 HTTP %s，已停止发布" % status)
        try:
            return status, response_headers, json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise PublishError("GitHub 返回的内容不是有效版本 JSON，已停止发布") from None

    async def _fetch_latest(self):
        include = bool(self.ctx.config.get("include_prereleases", False))
        if include:
            previous_pages, pages, candidates = self.state.get("list_pages", {}), {}, []
            for number in range(1, 11):
                key = str(number)
                cached = previous_pages.get(key, {})
                status, headers, data = await self._github_page(
                    LIST_API + f"?per_page=100&page={number}", cached.get("etag", ""))
                if status == 304:
                    if not cached:
                        raise PublishError("GitHub 预发行列表缺少对应分页缓存，已停止发布")
                    page = copy.deepcopy(cached)
                    if re.search(r'rel="next"', headers.get("link", "")):
                        page["has_next"] = True
                else:
                    if not isinstance(data, list):
                        raise PublishError("GitHub 发布列表格式异常，已停止发布")
                    eligible = [normalize_release(item, allow_prereleases=True) for item in data
                                if not isinstance(item, dict) or not item.get("draft")]
                    page = {"etag": headers.get("etag", ""),
                            "has_next": len(data) == 100 or bool(re.search(r'rel="next"', headers.get("link", ""))),
                            "candidate": max(eligible, key=lambda item: (item["timestamp"], item["id"])) if eligible else None}
                pages[key] = page
                if page["candidate"] is not None:
                    candidates.append(page["candidate"])
                if not page["has_next"]:
                    break
            else:
                raise PublishError("GitHub 发布列表已达到 1000 条扫描上限，无法确认完整性；已停止发布而非发送不完整结果")
            if not candidates:
                raise PublishError("GitHub 暂无可发布版本（草稿不会发送）")
            release = max(candidates, key=lambda item: (item["timestamp"], item["id"]))
            self.state["list_pages"] = pages
        else:
            matching_cache = self.state.get("etag_mode", "stable") == "stable" and self.state.get("latest") and not self.state["latest"].get("prerelease")
            status, headers, data = await self._github_page(API, self.state.get("etag", "") if matching_cache else "")
            release = self.state["latest"] if status == 304 else normalize_release(data)
        previous = self.state.get("latest")
        if previous:
            before, after = _version(previous["tag"]), _version(release["tag"])
            older_number = before is not None and after is not None and after < before
            repeated_tag = release["id"] != previous["id"] and release["tag"] == previous["tag"]
            renamed_release = release["id"] == previous["id"] and release["tag"] != previous["tag"]
            older_publication = (release["timestamp"], release["id"]) < (previous["timestamp"], previous["id"])
            if older_publication or older_number or repeated_tag or renamed_release:
                raise PublishError("GitHub 最新版本比本地记录更旧或版本号重复，已阻止回退发布（缓存 %s，接口 %s）" % (previous["tag"], release["tag"]))
        self.state.update(latest=release, etag_mode="all" if include else "stable", github_retry_at=0)
        if not include and status != 304:
            self.state["etag"] = headers.get("etag", "")
        await self._save()
        return release

    async def _bot(self, token, method, payload):
        try:
            status, _, body = await self._read("POST", "https://api.telegram.org/bot" + token + "/" + method,
                                             limit=256 * 1024, json=payload)
        except Exception as exc:
            raise BotError("Telegram %s 请求中断（%s）" % (method, type(exc).__name__),
                           uncertain=method == "sendMessage") from None
        try:
            data = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise BotError("Telegram %s 返回非 JSON（HTTP %s）" % (method, status), uncertain=method == "sendMessage") from None
        if not isinstance(data, dict) or data.get("ok") is not True or status != 200:
            description = str(data.get("description") or "响应异常") if isinstance(data, dict) else "响应异常"
            description = description.replace(token, "***")[:220]
            parameters = data.get("parameters", {}) if isinstance(data, dict) else {}
            try:
                retry = int(parameters.get("retry_after", 0)) if isinstance(parameters, dict) else 0
            except (ValueError, TypeError):
                retry = 0
            explicit_rejection = isinstance(data, dict) and data.get("ok") is False and status < 500
            raise BotError("Telegram %s：%s" % (method, description),
                           uncertain=method == "sendMessage" and not explicit_rejection, retry_after=retry)
        return data.get("result")

    async def _bot_id(self, token):
        key = hashlib.sha256(token.encode()).hexdigest()
        if key != self.identity_key:
            me = await self._bot(token, "getMe", {})
            if not isinstance(me, dict) or me.get("is_bot") is not True or not isinstance(me.get("id"), int):
                raise PublishError("平台凭据不是有效 Telegram Bot，禁止使用用户账号发布")
            self.identity, self.identity_key = me["id"], key
        return self.identity

    async def _destination(self, token, bot_id, target):
        chat = await self._bot(token, "getChat", {"chat_id": int(target) if target.startswith("-") else target})
        if not isinstance(chat, dict) or chat.get("type") not in {"group", "supergroup", "channel"}:
            raise PublishError("目标不是群组或频道，不支持向用户私聊发布")
        chat_id = chat.get("id")
        if not isinstance(chat_id, int) or chat_id >= 0:
            raise PublishError("Telegram 返回的群组或频道 ID 无效")
        member = await self._bot(token, "getChatMember", {"chat_id": chat_id, "user_id": bot_id})
        if not isinstance(member, dict):
            raise PublishError("无法确认 Bot 的管理员权限")
        if member.get("status") != "creator":
            if member.get("status") != "administrator":
                raise PublishError("请将平台 Bot 设为目标群组或频道的管理员，并授予发消息和置顶权限")
            if chat["type"] == "channel":
                if not member.get("can_post_messages") or not member.get("can_edit_messages"):
                    raise PublishError("频道 Bot 缺少发布消息或编辑消息（置顶）权限")
            elif not member.get("can_pin_messages"):
                raise PublishError("群组 Bot 缺少置顶消息权限")
        key = f"{bot_id}:{chat_id}"
        self.state["aliases"][f"{bot_id}:{target}"] = key
        return key, chat_id, str(chat.get("title") or target)

    async def _outcome(self, ok, message):
        self.state["last_result"] = message
        await self._save()
        if self.ctx.config.get("last_result") != message:
            self.ctx.update_config({"last_result": message})
        return {"ok": ok, "message": message}

    async def check(self):
        if self.lock.locked():
            return {"ok": False, "message": "正在检查或发布，请稍候；不会并行重复发送"}
        async with self.lock:
            try:
                await self.load()
                return await self._check_locked()
            except Exception as exc:
                message = str(exc) if isinstance(exc, PublishError) else "检查失败（%s），请检查网络或插件存储" % type(exc).__name__
                self.ctx.log.warning(message)
                if self.state is None:
                    return {"ok": False, "message": message}
                return await self._outcome(False, message)

    async def _check_locked(self):
        targets = parse_targets(self.ctx.config.get("targets", ""))
        release = await self._fetch_latest()
        if time.time() < self.state.get("telegram_retry_at", 0):
            return await self._outcome(False, "Telegram 正在限流，冷却后再继续最新版本；不会重复已发送内容")
        token = _selected_token(self.ctx)
        bot_id = await self._bot_id(token)
        completed, errors, seen, used = 0, [], set(), 0
        for target in targets:
            known = self.state["aliases"].get(f"{bot_id}:{target}")
            previous = self.state["targets"].get(known, {})
            if target.startswith("-") and known in seen:
                continue
            if target.startswith("-") and previous.get("release_id") == release["id"] and previous.get("pinned"):
                seen.add(known)
                completed += 1
                continue
            try:
                key, chat_id, title = await self._destination(token, bot_id, target)
                if key in seen:
                    continue
                seen.add(key)
                record = self.state["targets"].get(key)
                if not record or record.get("release_id") != release["id"]:
                    record = {"release_id": release["id"], "tag": release["tag"], "title": title,
                              "parts": render_messages(release), "message_ids": [], "inflight": None,
                              "pinned": False, "error": ""}
                    self.state["targets"][key] = record
                    await self._save()
                if record.get("pinned"):
                    completed += 1
                    continue
                if record.get("inflight") is not None:
                    raise PublishError("上一条发送结果不明确，已暂停此目标以防重复；请先在群/频道核对")
                record["error"] = ""
                for part_index in range(len(record["message_ids"]), len(record["parts"])):
                    if used >= MESSAGE_BUDGET:
                        break
                    record["inflight"] = part_index
                    await self._save()  # Write ahead: a restart must not blindly resend this part.
                    try:
                        sent = await self._bot(token, "sendMessage", {
                            "chat_id": chat_id, "text": record["parts"][part_index], "parse_mode": "HTML",
                            "link_preview_options": {"is_disabled": True},
                        })
                        if not isinstance(sent, dict) or not isinstance(sent.get("message_id"), int) or sent["message_id"] <= 0:
                            raise BotError("Telegram 未返回有效消息 ID，发送结果需要核对", uncertain=True)
                    except BotError as exc:
                        if not exc.uncertain:
                            record["inflight"] = None
                        if exc.retry_after:
                            self.state["telegram_retry_at"] = time.time() + max(1, exc.retry_after)
                        await self._save()
                        raise
                    record["message_ids"].append(sent["message_id"])
                    record["inflight"] = None
                    record["updated_at"] = _stamp()
                    used += 1
                    await self._save()
                    await asyncio.sleep(0.4)
                if len(record["message_ids"]) != len(record["parts"]):
                    raise PublishError("更新内容较长，本轮已达发送上限；下次只继续未发送部分")
                if not record["pinned"]:
                    pinned = await self._bot(token, "pinChatMessage", {
                        "chat_id": chat_id, "message_id": record["message_ids"][0], "disable_notification": True,
                    })
                    if pinned is not True:
                        raise PublishError("置顶未获确认；下次只重试置顶，不重发正文")
                    record["pinned"] = True
                    record["updated_at"] = _stamp()
                    await self._save()
                    self.ctx.log.info("%s 已发布并置顶：%s", title, release["tag"])
                completed += 1
            except (PublishError, BotError) as exc:
                safe = str(exc)
                errors.append(target + "：" + safe)
                known = self.state["aliases"].get(f"{bot_id}:{target}")
                record = self.state["targets"].get(known)
                if record and record.get("release_id") == release["id"]:
                    record["error"] = safe
                    await self._save()
                self.ctx.log.warning("%s：%s", target, safe)
                if isinstance(exc, BotError) and exc.retry_after:
                    self.state["telegram_retry_at"] = time.time() + max(1, exc.retry_after)
                    await self._save()
                    break
        message = "最新%s %s：已发布并置顶 %s 个目标%s" % (
            "预发行版" if release.get("prerelease") else "正式版", release["tag"],
            completed, "（本轮未重复发送）" if not used else "")
        if errors:
            message += "\n" + "\n".join(errors)
        return await self._outcome(not errors, message)

    async def status(self):
        await self.load()
        latest = self.state.get("latest")
        lines = ["尚未检查 GitHub 最新版本" if not latest else "缓存最新%s：%s" % ("预发行版" if latest.get("prerelease") else "正式版", latest["tag"]),
                 "最近检查：" + self.state.get("checked_at", "尚未检查")]
        for record in self.state["targets"].values():
            if record.get("inflight") is not None:
                state = "发送结果待核对，已暂停"
            elif record.get("pinned"):
                state = "已发送并置顶"
            elif len(record.get("message_ids", [])) == len(record.get("parts", [])):
                state = "已发送，等待置顶"
            else:
                state = "已发送 %d/%d 段" % (len(record.get("message_ids", [])), len(record.get("parts", [])))
            lines.append("%s · %s · %s%s" % (record.get("title", "-"), record.get("tag", "-"), state,
                         " · " + record["error"] if record.get("error") else ""))
        message = "\n".join(lines)
        if self.ctx.config.get("last_result") != message:
            self.ctx.update_config({"last_result": message})
        return {"ok": True, "message": message}

    async def retry_uncertain(self):
        if self.lock.locked():
            return {"ok": False, "message": "正在发布，请稍候再恢复"}
        async with self.lock:
            await self.load()
            targets = parse_targets(self.ctx.config.get("targets", ""))
            bot_id = await self._bot_id(_selected_token(self.ctx))
            latest = self.state.get("latest") or {}
            count = 0
            for target in targets:
                key = self.state["aliases"].get(f"{bot_id}:{target}")
                record = self.state["targets"].get(key, {})
                if record.get("release_id") == latest.get("id") and record.get("inflight") is not None:
                    record.update(inflight=None, error="")
                    count += 1
            await self._save()
        if not count:
            return await self._outcome(True, "没有需要恢复的异常发送记录；成功记录未清除")
        return await self.check()  # Always refresh latest before any resumed send.


async def setup(ctx):
    defaults = {"auto_check": False, "include_prereleases": False, "targets": "", "check_interval": 15, "last_result": "尚未检查"}
    missing = {k: v for k, v in defaults.items() if k not in ctx.config or ctx.config[k] is None}
    if missing:
        ctx.update_config(missing)
    publisher = ReleasePublisher(ctx)
    await publisher.load()
    ctx.action("run_now", publisher.check)
    ctx.action("show_status", publisher.status)
    ctx.action("retry_uncertain", publisher.retry_uncertain)
    if ctx.config.get("auto_check", False):
        try:
            minutes = max(5, min(1440, int(ctx.config.get("check_interval", 15))))
        except (ValueError, TypeError):
            minutes = 15
        ctx.schedule_interval("平台发布通知·检查最新版本", publisher.check, seconds=minutes * 60)
        ctx.log.info("已启用最新版本检查：每 %s 分钟；仅通过平台 Bot 发布并置顶", minutes)
