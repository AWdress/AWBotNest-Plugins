"""Bundled manual and local, source-linked excerpt search, with no network I/O.

Nothing here uses an AI service or executes instructions/code from the wiki.
Only Markdown shipped in this plugin's fixed wiki_docs directory is read.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import math
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit


WIKI = "https://github.com/AWdress/AWBotNest/wiki"
DOCS_DIR = Path(__file__).with_name("wiki_docs")
MAX_PAGES = 64
MAX_PAGE_BYTES = 96 * 1024
MAX_TOTAL_BYTES = 1024 * 1024
MAX_REPLY_UNITS = 700
_QUESTION = re.compile(r"[?？]|怎么|怎样|如何|咋|为啥|为什么|能否|能不能|是否|有没有|会不会|要不要|在哪|支持|求助|请问|哪里|区别|干什么|不懂|不回|没反应|没跑|没执行|没运行|不跑|不执行|不生效|失败|错误|报错|无效|收不到|打不开|timeout|invalid|error|\bis required\b|\brequired for\b", re.I)
_TOPICS = ("awbotnest", "cookie", "cookiecloud", "telegram", "bot", "docker", "compose", "arm", "ai", "api", "cron", "cloakbrowser", "geoip", "oom",
           "插件", "企微", "企业微信", "机器人", "账号", "定时", "备份", "日志", "管理员", "浏览器", "代理", "通知", "验证码", "模型", "密钥")


def _units(text):
    return len(text.encode("utf-16-le")) // 2


def _cut(text, limit):
    result, count = [], 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if count + width > limit:
            break
        result.append(char)
        count += width
    return "".join(result)


def _normal(text):
    return unicodedata.normalize("NFKC", text).lower()


def _slug(link):
    """Resolve a wiki link without ever allowing another repository or host."""
    value = html.unescape(str(link)).strip().strip("<>")
    if not value or value.startswith(("#", "//")):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            return None
        path = parsed.path
    elif value.startswith("/"):
        path = parsed.path
    else:
        path = parsed.path
        if path.startswith("./"):
            path = path[2:]
        if "/" in path:
            return None
    prefix = "/AWdress/AWBotNest/wiki/"
    if path.lower().startswith(prefix.lower()):
        path = path[len(prefix):]
    elif path.startswith("/"):
        return None
    slug = unquote(path)
    if slug.endswith(".md"):
        slug = slug[:-3]
    slug = slug.replace(" ", "-")
    if not re.fullmatch(r"[A-Za-z0-9\u0080-\uffff][A-Za-z0-9_\-\u0080-\uffff]{0,159}", slug):
        return None
    if any(unicodedata.category(c).startswith("C") for c in slug):
        return None
    if slug.lower().endswith((".png", ".jpg", ".svg", ".gif", ".webp")):
        return None
    return slug


def _links(markdown):
    return {slug for value in re.findall(r"(?<!!)\[[^\]\n]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", markdown)
            if (slug := _slug(value))}


def _readable_tables(markdown):
    """Flatten Markdown tables to original header/value pairs, outside code."""
    lines = markdown.splitlines()
    result, cursor, in_code = [], 0, False

    def cells(line):
        return [value.strip().replace(r"\|", "|") for value in re.split(r"(?<!\\)\|", line.strip().strip("|"))]

    while cursor < len(lines):
        line = lines[cursor]
        if line.lstrip().startswith("```"):
            in_code = not in_code
        if not in_code and "|" in line and cursor + 1 < len(lines):
            headers = cells(line)
            separator = cells(lines[cursor + 1])
            if len(headers) >= 2 and len(separator) == len(headers) and all(re.fullmatch(r":?-{3,}:?", value) for value in separator):
                rows, end = [], cursor + 2
                while end < len(lines) and "|" in lines[end]:
                    values = cells(lines[end])
                    if len(values) != len(headers):
                        break
                    rows.append("• " + "；".join(header + "：" + value for header, value in zip(headers, values)))
                    end += 1
                if rows:
                    result.extend(rows)
                    cursor = end
                    continue
        result.append(line)
        cursor += 1
    return "\n".join(result)


def _plain(markdown):
    output, in_code = [], False
    for line in _readable_tables(markdown).splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            output.append("")
            continue
        if not in_code:
            line = re.sub(r"!\[([^\]]*)\]\([^)]*\)", "", line)
            line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
            line = re.sub(r"\*\*([^*]+)\*\*|__([^_]+)__", lambda m: m[1] or m[2], line)
            line = re.sub(r"`([^`]+)`", r"\1", line)
            line = re.sub(r"^\s*#{1,6}\s+", "", line)
            line = re.sub(r"^\s*[-*+]\s+", "• ", line)
        output.append(line)
    text = "\n".join(output)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_FILLERS = ("请问", "想问", "一下", "怎么", "如何", "为什么", "为何", "什么", "是否", "能不能", "可不可以",
            "怎么办", "帮我", "平台", "awbotnest", "没有", "不了", "可以", "这个", "那个", "请", "吗", "呢", "啊", "的", "了")
_ALIASES = (("企微", "企业微信"), ("tg", "telegram"), ("忘记密码", "管理员 密码"),
            ("定时没运行", "插件 定时"), ("docker安装", "docker 安装 部署"),
            ("ai设置", "ai 配置 模型"), ("cookie同步", "cookie 同步 cookiecloud"))


def _query_tokens(question):
    normalized = _normal(question)
    for source, target in _ALIASES:
        if source in normalized:
            normalized += " " + target
    for word in _FILLERS:
        normalized = normalized.replace(word, " ")
    tokens = set(re.findall(r"[a-z0-9]+(?:[_-][a-z0-9]+)*", normalized))
    for word in re.findall(r"[\u3400-\u9fff]+", normalized):
        if len(word) == 1:
            continue
        if len(word) <= 6:
            tokens.add(word)
        tokens.update(word[i:i + 2] for i in range(len(word) - 1))
    return {token for token in tokens if len(token) >= 2}, normalized.strip()


def _sections(pages):
    result = []
    for slug, doc in sorted(pages.items()):
        text = doc["text"]
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")), slug)
        parents, body, heading, in_code = {}, [], title, False

        def emit():
            plain = _plain("\n".join(body))
            if not plain:
                return
            # Paragraph windows keep a large table/code section from dominating answers.
            paragraphs = re.split(r"\n\s*\n", plain)
            chunk = ""
            for paragraph in paragraphs:
                if chunk and len(chunk) + len(paragraph) > 1800:
                    result.append({"slug": slug, "title": title, "heading": heading, "text": chunk})
                    chunk = ""
                while len(paragraph) > 1800:
                    if chunk:
                        result.append({"slug": slug, "title": title, "heading": heading, "text": chunk})
                        chunk = ""
                    result.append({"slug": slug, "title": title, "heading": heading, "text": paragraph[:1800]})
                    paragraph = paragraph[1800:]
                if paragraph:
                    chunk += ("\n\n" if chunk else "") + paragraph
            if chunk:
                result.append({"slug": slug, "title": title, "heading": heading, "text": chunk})

        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                in_code = not in_code
            match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line) if not in_code else None
            if match:
                emit()
                body = []
                level = len(match[1])
                parents = {key: value for key, value in parents.items() if key < level}
                parents[level] = match[2]
                heading = " / ".join(value for key, value in sorted(parents.items()) if key > 1) or title
            else:
                body.append(line)
        emit()
        # Keep a concise parent procedure too: an installation answer must not
        # stop at "open a terminal" merely because the next instruction is H3.
        for match in re.finditer(r"^##\s+(.+)\n([\s\S]*?)(?=^##\s|\Z)", text, re.M):
            if not re.search(r"^###\s", match[2], re.M):
                continue
            plain = _plain(match[2])
            if plain:
                result.append({"slug": slug, "title": title, "heading": match[1].strip(),
                               "text": plain[:1800], "overview": True})
    return result


class WikiLibrary:
    def __init__(self, ctx, reader=None):
        self.ctx = ctx
        # Kept for existing callers only; never invoked, even on a cache miss.
        self.reader = reader
        self.state = None
        self.lock = asyncio.Lock()
        self.index = []
        self.faqs = []
        self.last_refresh_error = False
        self.status_text = "尚未载入内置手册"
        self.load_attempted = False

    async def load(self):
        if self.load_attempted:
            return
        await self.refresh(force=True)

    def _reindex(self):
        self.index = _sections({slug: self.state["documents"][slug] for slug in self.state["pages"]})

    @staticmethod
    def _read_faqs(documents, version):
        path = Path(__file__).with_name("wiki_faq.json")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024:
            raise ValueError("内置问答文件无效")
        with path.open("rb") as stream:
            data = stream.read(128 * 1024 + 1)
        if len(data) > 128 * 1024:
            raise ValueError("内置问答超过大小限制")
        source = json.loads(data)
        if not isinstance(source, dict) or source.get("schema") != 1 or source.get("platform_version") != version:
            raise ValueError("内置问答版本无效")
        entries = source.get("entries")
        if not isinstance(entries, list) or not 1 <= len(entries) <= 120:
            raise ValueError("内置问答数量无效")
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or entry["id"] in seen:
                raise ValueError("内置问答标识无效")
            seen.add(entry["id"])
            if entry.get("page") not in documents or not isinstance(entry.get("question"), str) or len(entry["question"]) > 100:
                raise ValueError("内置问答来源或标题无效")
            for key, low, high, max_chars in (("aliases", 1, 30, 120), ("points", 2, 4, 240), ("evidence", 1, 8, 240)):
                values = entry.get(key)
                if not isinstance(values, list) or not low <= len(values) <= high or any(not isinstance(v, str) or not v.strip() or len(v) > max_chars for v in values):
                    raise ValueError("内置问答字段无效")
            section = entry.get("section")
            if not isinstance(section, str):
                raise ValueError("内置问答章节无效")
            page = documents[entry["page"]]["text"]
            heading = re.search(r"^(#{1,6})\s+" + re.escape(section) + r"\s*$", page, re.M)
            if heading is None:
                raise ValueError("内置问答章节不存在：" + entry["id"])
            rest = page[heading.end():]
            end = next((match.start() for match in re.finditer(r"^(#{1,6})\s+", rest, re.M) if len(match[1]) <= len(heading[1])), len(rest))
            original = _normal(_plain(rest[:end]))
            if any(_normal(evidence) not in original for evidence in entry["evidence"]):
                raise ValueError("内置问答原文依据未匹配：" + entry["id"])
        return entries

    @staticmethod
    def _read_builtin():
        root = DOCS_DIR.resolve(strict=True)

        def read_file(name, limit):
            original = root / name
            target = original.resolve(strict=True)
            if original.is_symlink() or target.parent != root or not target.is_file():
                raise ValueError("内置手册文件位置无效")
            if target.stat().st_size > limit:
                raise ValueError("内置手册文件超过大小限制")
            with target.open("rb") as stream:
                data = stream.read(limit + 1)
            if not data or len(data) > limit:
                raise ValueError("内置手册为空或超过大小限制")
            return data

        source = json.loads(read_file("source.json", 32 * 1024))
        if not isinstance(source, dict) or type(source.get("schema")) is not int or source["schema"] != 1 or source.get("source") != WIKI:
            raise ValueError("内置手册来源清单无效")
        if source.get("hash_normalization") != "utf8-lf-no-bom":
            raise ValueError("内置手册校验规范无效")
        version = source.get("platform_version")
        snapshot = source.get("snapshot_date")
        if not isinstance(version, str) or not re.fullmatch(r"v\d+(?:\.\d+){1,5}", version):
            raise ValueError("内置手册适用版本无效")
        if not isinstance(snapshot, str) or date.fromisoformat(snapshot).isoformat() != snapshot:
            raise ValueError("内置手册快照日期无效")
        entries = source.get("pages")
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_PAGES:
            raise ValueError("内置手册篇数无效")
        documents, total = {}, 0
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("内置手册篇目无效")
            slug = entry.get("slug")
            if not isinstance(slug, str) or _slug(slug) != slug or slug in documents or entry.get("file") != slug + ".md":
                raise ValueError("内置手册文件名无效")
            checksum = entry.get("sha256")
            if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
                raise ValueError("内置手册校验值无效")
            data = read_file(slug + ".md", MAX_PAGE_BYTES)
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("内置手册总量超过安全限制")
            text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != checksum:
                raise ValueError("内置手册完整性校验未通过")
            if not text.startswith("# ") or text.splitlines()[0][2:].strip() != entry.get("title"):
                raise ValueError("内置手册标题与来源清单不一致")
            documents[slug] = {"text": text}
        if "Home" not in documents:
            raise ValueError("内置手册缺少首页")
        state = {"schema": 1, "documents": documents, "pages": sorted(documents),
                 "platform_version": version, "snapshot_date": snapshot}
        state["faq"] = WikiLibrary._read_faqs(documents, version)
        return state, _sections(documents)

    async def refresh(self, force=False):
        async with self.lock:
            if self.load_attempted and not force:
                return {"ok": not self.last_refresh_error, "message": self.status_text}
            self.load_attempted = True
            try:
                candidate, index = await asyncio.to_thread(self._read_builtin)
                self.state, self.index = candidate, index
                self.faqs = candidate["faq"]
                self.last_refresh_error = False
                self.status_text = "内置手册 %s · %s 篇 · 快照 %s（离线检索）" % (
                    candidate["platform_version"], len(candidate["pages"]), candidate["snapshot_date"])
                return {"ok": True, "message": self.status_text}
            except Exception as exc:
                self.last_refresh_error = True
                if self.state:
                    self.status_text = "内置手册重新读取失败（%s），继续使用已加载的 %s 手册" % (type(exc).__name__, self.state["platform_version"])
                else:
                    self.status_text = "内置手册读取失败（%s），请重新安装插件；未请求网络文档" % type(exc).__name__
                return {"ok": False, "message": self.status_text}

    def search(self, question):
        """Return relevant verbatim sections, or an empty list for no evidence."""
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            return []
        tokens, _ = _query_tokens(question)
        if not tokens or not self.index:
            return []
        # Normalize each cached section once per question, not once per token.
        # A pasted log should never turn hundreds of token normalizations into
        # an event-loop stall; overly broad requests need a more focused question.
        if len(tokens) > 96:
            return []
        indexed = [(item, _normal(item["title"]), _normal(item["heading"]), _normal(item["text"]))
                   for item in self.index]
        counts = {token: sum(token in (title + " " + heading + " " + body)
                             for _, title, heading, body in indexed) for token in tokens}
        scored = []
        question_normal = _normal(question)
        is_problem = bool(re.search(r"失败|出错|报错|错误|无法|不到|没|不运行|不生效|异常|为什么|为何", question_normal))
        wants_steps = not is_problem and bool(re.search(r"安装|同步|配置|设置|部署|备份", question_normal))
        for item, title, heading, body in indexed:
            matches = [token for token in tokens if token in title or token in heading or token in body]
            if not matches:
                continue
            score = 0.0
            for token in matches:
                weight = 1 + math.log((len(self.index) + 1) / (counts[token] + 1))
                score += weight * ((2.5 if token in title else 0) + (4 if token in heading else 0)
                                   + min(2, body.count(token)))
            meaningful = [token for token in matches if re.search(r"[a-z0-9]", token)
                          or token in title or token in heading or counts[token] < len(self.index) * 0.45]
            if not meaningful:
                continue
            coverage = len(matches) / max(1, len(tokens))
            required_codes = {token for token in tokens if re.fullmatch(r"\d{3,}", token)}
            if required_codes and not required_codes.issubset(matches):
                continue
            if len(tokens) >= 5 and not any(re.search(r"[a-z0-9]", token) for token in tokens) and coverage < 0.4:
                continue
            if len(matches) == 1 and len(tokens) >= 5 and coverage < 0.25:
                continue
            if score < 5:
                continue
            score *= 0.55 + coverage
            # A section's topic matters more than accidental mention in a giant table.
            if any(token in heading for token in meaningful):
                score *= 1.2
            if wants_steps:
                if re.search(r"为什么|不到|失败|排查|错误|注意什么|常见问题", heading):
                    score *= 0.25
                if item["heading"] == item["title"]:
                    score *= 0.6
                if item.get("overview"):
                    score *= 1.25
                    if "推荐" in heading and not re.search(r"远程|已有|手动|compose", question_normal):
                        score *= 1.7
                if re.search(r"安装", question_normal) and re.search(r"安装前|更新|前准备", heading):
                    score *= 0.4
                if re.search(r"设置|配置", question_normal) and "插件" not in question_normal and "插件" in heading:
                    score *= 0.6
            scored.append((score, item))
        scored.sort(key=lambda row: (-row[0], row[1]["slug"], row[1]["heading"]))
        return [{**item, "score": round(score, 3)} for score, item in scored[:3]]

    @staticmethod
    def _compact(text):
        return re.sub(r"[\W_]+", "", _normal(text))

    def _best_faq(self, question):
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            return None
        text = _normal(question)
        compact = self._compact(text)
        # Fillers may separate topic and action in ordinary Chinese questions.
        spoken = re.sub(r"为什么|怎么|怎样|如何|为啥|请问|一直|突然|已经|还是|我的|这个|那个|咋|啊|呢|呀", "", compact)
        found = []
        for entry in self.faqs:
            # A plugin's lifecycle is not an instruction to redeploy the platform.
            if "插件" in compact and entry["id"] in {"install", "update"}:
                continue
            for alias in entry["aliases"] + [entry["question"]]:
                needle = self._compact(alias)
                exact = compact == needle
                if re.fullmatch(r"[a-z0-9_]+", alias, re.I):
                    present = bool(re.search(r"(?<![a-z0-9_])" + re.escape(_normal(alias)) + r"(?![a-z0-9_])", text))
                else:
                    present = len(needle) >= 3 and (needle in compact or needle in spoken)
                if exact or present:
                    found.append((250 + len(needle) if exact else 100 + min(40, len(needle)), exact, entry))
        if not found:
            return None
        found.sort(key=lambda item: (-item[0], item[2]["id"]))
        score, exact, entry = found[0]
        return {"entry": entry, "score": score, "exact": exact}

    def should_answer(self, text):
        """Recognize supported short topics/questions, without answering group chat."""
        if not isinstance(text, str) or not text.strip() or len(text) > 2000 or not self.index:
            return False
        match = self._best_faq(text)
        if match and match["exact"]:
            return True  # e.g. "CookieCloud", "ARM", "企微回调".
        question = bool(_QUESTION.search(text))
        if not question:
            return False
        if match:
            return True
        normalized = _normal(text)
        if not any(re.search(r"(?<![a-z0-9_])" + re.escape(topic) + r"(?![a-z0-9_])", normalized)
                   if re.fullmatch(r"[a-z0-9]+", topic) else topic in normalized for topic in _TOPICS):
            return False
        results = self.search(text)
        return bool(results and results[0]["score"] >= 25)

    def _render_short(self, title, points, page, *, excerpt=False):
        url = WIKI + "/" + quote(page, safe="")
        prefix = "<b>" + html.escape(_cut(title, 70)) + "</b>\n"
        version = html.escape(self.state["platform_version"])
        footer = '\n\n<i>内置手册 ' + version + '</i> · <a href="' + url + '">Wiki 原文</a>'
        if self.last_refresh_error:
            footer += "\n<i>重读失败，使用已加载手册。</i>"
        output = []
        for point in points[:4]:
            rendered = "• " + html.escape(point)
            if _units(prefix + "\n".join(output + [rendered]) + footer) <= MAX_REPLY_UNITS:
                output.append(rendered)
                continue
            budget = MAX_REPLY_UNITS - _units(prefix + "\n".join(output) + footer) - 5
            if budget >= 25:
                # Escape one character at a time to keep entities and Unicode whole.
                fragment, units = [], 0
                for char in point:
                    escaped = html.escape(char)
                    if units + _units(escaped) > budget:
                        break
                    fragment.append(escaped)
                    units += _units(escaped)
                output.append("• " + "".join(fragment).rstrip() + "…")
            break
        return prefix + "\n".join(output) + footer

    async def answer(self, question):
        await self.refresh()
        if not self.index:
            return '<b>内置手册暂不可用</b>\n请重新载入手册或重新安装插件。\n<a href="' + WIKI + '">打开官方 Wiki</a>'
        matched = self._best_faq(question)
        if matched:
            entry = matched["entry"]
            return self._render_short(entry["question"], entry["points"], entry["page"])
        results = self.search(question)
        if not results or results[0]["score"] < 25:
            return '<b>手册里暂未找到明确答案</b>\n请补充功能名称或完整报错，我不会猜测。\n<i>内置手册 ' + html.escape(self.state["platform_version"]) + '</i> · <a href="' + WIKI + '">查看 Wiki</a>'
        item = results[0]
        tokens, _ = _query_tokens(question)
        sentences = [part.strip(" •\t") for part in re.split(r"\n+|(?<=[。！？])", item["text"]) if part.strip(" •\t")]
        ranked = sorted(enumerate(sentences), key=lambda pair: (-sum(token in _normal(pair[1]) for token in tokens), pair[0]))
        selected = sorted(ranked[:3], key=lambda pair: pair[0])
        points = [_cut(value, 140) + ("…" if _units(value) > 140 else "") for _, value in selected]
        return self._render_short(item["heading"], points, item["slug"], excerpt=True)
