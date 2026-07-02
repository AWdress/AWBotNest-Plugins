# =============================================================================
# 影巢答题红包插件 - 题库同步 / 查询（私有辅助）
#
# 从社区共建题库仓库（默认 https://github.com/my-name-is-alan/hdhive-red-questions）
# 拉取 questions/ 下所有 *.json，解析成「归一化题干 → 答案记录」索引，供答题时查。
#
#   - 同步：下载仓库 tar.gz（GitHub codeload/api），解压取 questions/*.json。
#     用 urllib + asyncio.to_thread，零第三方依赖。
#   - 索引：normalize(题干) → {question_text, options, answer, question_type}。
#   - 缓存：解析结果落 data_dir/bank_index.json，重启即用；上次同步时间存 kv。
# =============================================================================
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import tarfile
import urllib.request

from ._quiz import normalize

_UA = "AWBotNest-hdhive_quiz/1.0"
_KV_LAST_SYNC = "bank_last_sync"


def _parse_owner_repo(url: str) -> tuple[str, str] | None:
    """从 github 仓库 URL 解析 (owner, repo)。"""
    if not url:
        return None
    m = re.search(r"github\.com[/:]+([^/]+)/([^/#?]+?)(?:\.git)?/?$", url.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def _infer_type(rec: dict) -> str:
    qt = (rec.get("question_type") or "").strip()
    if qt in ("single_choice", "true_false"):
        return qt
    opts = rec.get("options") or []
    if len(opts) == 2:
        return "true_false"
    return "single_choice"


def _iter_questions(obj) -> list[dict]:
    """一个 JSON 文件可为题目数组，或含 questions 数组的对象。"""
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict) and isinstance(obj.get("questions"), list):
        return [x for x in obj["questions"] if isinstance(x, dict)]
    return []


def _download_and_parse(repo_url: str, branch: str, subdir: str) -> dict:
    """（阻塞）下载题库 tar.gz 并解析出索引。异常向上抛。"""
    pr = _parse_owner_repo(repo_url)
    if not pr:
        raise ValueError(f"无法解析仓库地址: {repo_url!r}")
    owner, repo = pr
    tar_url = f"https://codeload.github.com/{owner}/{repo}/tar.gz/refs/heads/{branch}"

    req = urllib.request.Request(tar_url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()

    subdir = (subdir or "questions").strip("/")
    index: dict[str, dict] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile() or not member.name.endswith(".json"):
                continue
            # 归档路径形如 repo-branch/questions/xxx.json
            parts = member.name.split("/", 1)
            rel = parts[1] if len(parts) == 2 else member.name
            if not rel.startswith(subdir + "/"):
                continue
            f = tf.extractfile(member)
            if not f:
                continue
            try:
                obj = json.loads(f.read().decode("utf-8"))
            except Exception:
                continue
            for q in _iter_questions(obj):
                text = (q.get("question_text") or q.get("title") or "").strip()
                answer = q.get("answer")
                if not text or answer in (None, ""):
                    continue
                if q.get("is_active") is False:
                    continue
                key = normalize(text)
                if not key:
                    continue
                index[key] = {
                    "question_text": text,
                    "options": [str(o) for o in (q.get("options") or [])],
                    "answer": str(answer).strip(),
                    "question_type": _infer_type(q),
                }
    return index


class Bank:
    """题库索引：内存 + data_dir 缓存。"""

    def __init__(self, ctx):
        self._ctx = ctx
        self._log = ctx.log
        self._index: dict[str, dict] = {}
        self._cache_path = os.path.join(ctx.data_dir, "bank_index.json")
        self._load_cache()

    @property
    def size(self) -> int:
        return len(self._index)

    def last_sync(self) -> float:
        try:
            return float(self._ctx.kv.get(_KV_LAST_SYNC, 0) or 0)
        except Exception:
            return 0.0

    def _load_cache(self) -> None:
        try:
            if os.path.exists(self._cache_path):
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._index = data
                    self._log.info("[影巢答题] 题库缓存载入 %d 条", len(self._index))
        except Exception as e:  # noqa: BLE001
            self._log.debug("[影巢答题] 载入题库缓存失败: %r", e)

    def _save_cache(self) -> None:
        try:
            tmp = self._cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False)
            os.replace(tmp, self._cache_path)
        except Exception as e:  # noqa: BLE001
            self._log.debug("[影巢答题] 写题库缓存失败: %r", e)

    async def sync(self, repo_url: str, branch: str, subdir: str) -> tuple[int, str]:
        """拉取并重建索引。返回 (题目数, 错误信息)；成功错误信息为空。"""
        try:
            index = await asyncio.to_thread(_download_and_parse, repo_url, branch or "main", subdir or "questions")
        except Exception as e:  # noqa: BLE001
            self._log.warning("[影巢答题] 题库同步失败: %r", e)
            return (self.size, str(e))
        self._index = index
        self._save_cache()
        try:
            import time as _t
            self._ctx.kv.set(_KV_LAST_SYNC, _t.time())
        except Exception:
            pass
        self._log.info("[影巢答题] 题库同步完成，共 %d 题", len(index))
        return (len(index), "")

    def lookup(self, question_text: str) -> dict | None:
        """按题干查题库。精确归一匹配优先，再退回子串双向匹配。"""
        if not self._index:
            return None
        key = normalize(question_text)
        if not key:
            return None
        rec = self._index.get(key)
        if rec:
            return rec
        # 题面可能被截断/加了前后缀 → 子串匹配（取最长命中，减少误匹配）
        best = None
        best_len = 0
        for k, v in self._index.items():
            if len(k) < 6:
                continue
            if (k in key or key in k) and len(k) > best_len:
                best, best_len = v, len(k)
        return best
