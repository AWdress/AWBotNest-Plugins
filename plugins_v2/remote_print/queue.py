"""单实例持久打印队列：只重领未开始的任务，不重试可能已经出纸的任务。"""
from __future__ import annotations

import asyncio
import copy
import hmac
import hashlib
import inspect
import json
import math
import re
import secrets
import time
from pathlib import Path

from .chat import normalize_sides
from .files import inspect_file


ACTIVE = {"receiving", "pending", "queued", "leased", "started"}
TERMINAL = {"submitted", "failed", "unknown", "cancelled", "archived"}
MAX_NUMBER = 999_999_999
NUMBER_BATCH_IDLE = 300
IMAGE_FORMATS = {"jpg", "jpeg", "png", "webp", "bmp"}
LABELS = {"receiving": "正在收文件", "pending": "等待确认", "queued": "等待打印",
          "leased": "正在准备打印", "started": "正在提交打印", "submitted": "已提交打印队列",
          "failed": "失败", "unknown": "结果待核查（不会自动重打）", "cancelled": "已取消", "archived": "已核查归档（未重打）"}


def instance_lock(path: Path):
    handle = path.open("a+b")
    try:
        if __import__("os").name == "nt":
            import msvcrt
            if path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError):
        handle.close()
        raise RuntimeError("远程打印数据目录已被其他实例使用，请勿多进程共享队列") from None
    return handle


class PrintQueue:
    def __init__(self, ctx, config):
        self.ctx, self.config = ctx, config
        self.root = Path(ctx.data_dir) / "print_files"
        self.lock = asyncio.Lock()
        self.state = {"jobs": {}, "seen": {}, "number_sessions": {}}
        self.device = {}
        self.faulted = False
        self.process_lock = None
        self.bundle_plans = {}

    async def open(self):
        await asyncio.to_thread(self.root.mkdir, parents=True, exist_ok=True)
        self.process_lock = await asyncio.to_thread(instance_lock, self.root.parent / "print_server.lock")
        self.ctx.add_cleanup(self.close)
        state = await self.ctx.storage.get("print_queue_v1", {"jobs": {}, "seen": {}, "number_sessions": {}})
        if not isinstance(state, dict) or not isinstance(state.get("jobs"), dict) or not isinstance(state.get("seen"), dict):
            raise RuntimeError("打印队列数据损坏，未重建或自动重打，请先备份并检查")
        async with self.lock:
            snapshot = copy.deepcopy(state)
            self._migrate_numbers(snapshot)
            self._validate_bundles(snapshot)
            for job in snapshot["jobs"].values():
                if job["status"] == "started":
                    job.update(status="unknown", message="平台重启，需核查打印机队列", updated=time.time())
                elif job["status"] == "leased":
                    job.update(status="failed", message="平台重启中断了打印准备，请重新发送文件", updated=time.time())
                elif job["status"] == "receiving":
                    job.update(status="failed", message="收文件时任务中断", file_present=False, updated=time.time())
            await self._commit(snapshot)
        # 文件名由任务随机 ID 生成，仅清理本插件目录内的未关联文件。
        known = {self.file(job["id"]).name for job in self.state["jobs"].values() if job.get("file_present")}
        known.update(self.bundle_file(job["id"]).name for job in self.state["jobs"].values() if job.get("bundle_file_present"))
        await asyncio.to_thread(self._remove_orphans, known)
        await self.cleanup()

    def close(self):
        if self.process_lock is not None:
            self.process_lock.close()
            self.process_lock = None

    @staticmethod
    def _number_scope(owner, source_channel):
        if not isinstance(owner, str) or not owner or not isinstance(source_channel, str):
            raise RuntimeError("打印编号所属用户或渠道损坏，请先备份并检查")
        normalized = owner.casefold() if owner.startswith("wecom:") else owner
        return json.dumps([normalized, source_channel], ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def _validate_number_sessions(cls, state):
        sessions = state.get("number_sessions")
        if not isinstance(sessions, dict):
            raise RuntimeError("打印批次计数缺失或损坏，未重新编号，请先备份并检查")
        for scope, session in sessions.items():
            try:
                parts = json.loads(scope)
                valid_scope = (isinstance(parts, list) and len(parts) == 2
                               and cls._number_scope(*parts) == scope)
            except (TypeError, ValueError, RuntimeError):
                valid_scope = False
            if not valid_scope or not isinstance(session, dict):
                raise RuntimeError("打印批次计数损坏，未重新编号，请先备份并检查")
            batch, number, stamp = session.get("batch"), session.get("next_number"), session.get("last_received")
            if (type(batch) is not int or not 1 <= batch <= MAX_NUMBER
                    or type(number) is not int or not 1 <= number <= MAX_NUMBER + 1
                    or "last_received" not in session
                    or (stamp is None and batch != 1)
                    or (stamp is not None and (type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp < 0))):
                raise RuntimeError("打印批次计数损坏，未重新编号，请先备份并检查")
        used = set()
        for identity, job in state["jobs"].items():
            if (not isinstance(job, dict) or not isinstance(identity, str)
                    or not re.fullmatch(r"[a-f0-9]{16}", identity) or job.get("id") != identity
                    or "current_number_batch" in job):
                raise RuntimeError("打印队列数据损坏，未分配新编号，请先备份并检查")
            scope = cls._number_scope(job.get("owner"), job.get("source_channel", ""))
            session = sessions.get(scope)
            number, batch = job.get("number"), job.get("number_batch")
            if (type(number) is not int or not 1 <= number <= MAX_NUMBER
                    or type(batch) is not int or not 1 <= batch <= MAX_NUMBER
                    or session is None or batch > session["batch"]
                    or (batch == session["batch"] and number >= session["next_number"])
                    or (scope, batch, number) in used):
                raise RuntimeError("打印任务编号损坏或重复，未分配新编号，请先备份并检查")
            used.add((scope, batch, number))

    @classmethod
    def _migrate_numbers(cls, state):
        """Preserve old displayed numbers; new receipts start a scoped batch."""
        if "number_sessions" in state:
            cls._validate_number_sessions(state)
            return
        if any(isinstance(job, dict) and "number_batch" in job for job in state["jobs"].values()):
            raise RuntimeError("打印批次计数缺失，未重新编号，请先备份并检查")
        used = set()
        missing = []
        for identity, job in state["jobs"].items():
            if (not isinstance(job, dict) or not isinstance(identity, str)
                    or not re.fullmatch(r"[a-f0-9]{16}", identity) or job.get("id") != identity):
                raise RuntimeError("打印队列数据损坏，未分配新编号，请先备份并检查")
            if "number" not in job:
                missing.append(job)
                continue
            number = job["number"]
            if type(number) is not int or not 1 <= number <= MAX_NUMBER or number in used:
                raise RuntimeError("打印任务编号损坏或重复，未分配新编号，请先备份并检查")
            used.add(number)
        if "next_number" not in state:
            if used:
                # A removed highest-number job cannot be reconstructed from the
                # surviving records. Guessing max+1 could reuse an old number.
                raise RuntimeError("打印编号计数缺失，未重新编号，请先备份并检查")
            state["next_number"] = 1
        number = state["next_number"]
        if type(number) is not int or not 1 <= number <= MAX_NUMBER + 1 or (used and number <= max(used)):
            raise RuntimeError("打印编号计数损坏，未重新编号，请先备份并检查")
        if len(missing) > MAX_NUMBER + 1 - number:
            raise RuntimeError("打印任务编号已用尽，旧任务未重新编号，请联系管理员")
        # Old releases never exposed short numbers. This deterministic migration
        # gives old files stable numbers while preserving their opaque IDs.
        for job in missing:
            created = job.get("created")
            if type(created) not in (int, float) or not math.isfinite(created):
                raise RuntimeError("打印队列创建时间损坏，未分配新编号，请先备份并检查")
        for job in sorted(missing, key=lambda item: (item["created"], item["id"])):
            job["number"] = number
            number += 1
        sessions = {}
        for job in state["jobs"].values():
            scope = cls._number_scope(job.get("owner"), job.get("source_channel", ""))
            job["number_batch"] = 1
            session = sessions.setdefault(scope, {"batch": 1, "next_number": 1, "last_received": None})
            session["next_number"] = max(session["next_number"], job["number"] + 1)
        # A legacy timestamp cannot establish the new receive-only window.
        # Keep every exposed short number in batch 1, then start batch 2 at 1.
        state.pop("next_number", None)
        state["number_sessions"] = sessions
        cls._validate_number_sessions(state)

    def _copy_job(self, job):
        result = copy.deepcopy(job)
        scope = self._number_scope(job["owner"], job.get("source_channel", ""))
        session = self.state["number_sessions"].get(scope)
        result["current_number_batch"] = bool(session and session["batch"] == job.get("number_batch"))
        leader = self.state["jobs"].get(job.get("bundle_leader", ""))
        if leader:
            for key in ("bundle_members", "bundle_image_count", "bundle_input_pages"):
                result[key] = copy.deepcopy(leader[key])
            result["bundle_pages"] = leader["bundle_metadata"]["pages"]
        return result

    @classmethod
    def _validate_bundles(cls, state):
        for job in state["jobs"].values():
            leader_id = job.get("bundle_leader")
            if leader_id is None:
                if any(key in job for key in ("bundle_members", "bundle_metadata", "bundle_file_present")):
                    raise RuntimeError("合并打印队列数据损坏，未自动重打，请先备份并检查")
                continue
            leader = state["jobs"].get(leader_id) if isinstance(leader_id, str) else None
            members = leader.get("bundle_members") if leader else None
            metadata = leader.get("bundle_metadata") if leader else None
            if (leader is None or leader.get("bundle_leader") != leader_id
                    or not isinstance(members, list) or not 2 <= len(members) <= 100
                    or any(not isinstance(value, str) for value in members)
                    or len(set(members)) != len(members) or members[0] != leader_id or job["id"] not in members
                    or not isinstance(metadata, dict) or metadata.get("format") != "pdf"
                    or type(metadata.get("size")) is not int or metadata["size"] <= 0
                    or type(metadata.get("pages")) is not int or metadata["pages"] <= 0
                    or not isinstance(metadata.get("filename"), str)
                    or not isinstance(metadata.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", metadata["sha256"])
                    or type(leader.get("bundle_file_present")) is not bool
                    or type(leader.get("copies")) is not int or leader["copies"] < 1
                    or leader.get("bundle_image_count") != len(members)
                    or leader.get("bundle_input_pages") != len(members)
                    or metadata["pages"] != (len(members) + len(members) % 2) * leader["copies"]
                    or leader.get("sides") not in {"two-sided-long-edge", "two-sided-short-edge"}
                    or (leader["status"] in ACTIVE and not leader["bundle_file_present"])):
                raise RuntimeError("合并打印队列数据损坏，未自动重打，请先备份并检查")
            if job["id"] != leader_id:
                if any(key in job for key in ("bundle_members", "bundle_metadata", "bundle_file_present")):
                    raise RuntimeError("合并打印成员数据损坏，未自动重打，请先备份并检查")
                continue
            scope = cls._number_scope(leader["owner"], leader.get("source_channel", ""))
            previous_number = 0
            for identity in members:
                member = state["jobs"].get(identity)
                if (member is None or member.get("bundle_leader") != leader_id
                        or cls._number_scope(member["owner"], member.get("source_channel", "")) != scope
                        or member.get("number_batch") != leader["number_batch"]
                        or member.get("format") not in IMAGE_FORMATS or member.get("pages") != 1
                        or member["number"] <= previous_number
                        or any(member.get(key) != leader.get(key) for key in
                               ("status", "copies", "printer", "sides", "backend", "device_id", "ipp_target"))):
                    raise RuntimeError("合并打印成员数据损坏，未自动重打，请先备份并检查")
                previous_number = member["number"]

    @staticmethod
    def _bundle_leader(state, job):
        return state["jobs"][job["bundle_leader"]] if job.get("bundle_leader") else job

    @classmethod
    def _group_jobs(cls, state, job):
        leader = cls._bundle_leader(state, job)
        return [state["jobs"][identity] for identity in leader.get("bundle_members", [leader["id"]])]

    @classmethod
    def _group_update(cls, state, job, **changes):
        leader = cls._bundle_leader(state, job)
        for member in cls._group_jobs(state, leader):
            member.update({key: value for key, value in changes.items() if key != "claim_token" or member is leader})

    @classmethod
    def _distinct_jobs(cls, state, jobs):
        leaders = {}
        for job in jobs:
            leader = cls._bundle_leader(state, job)
            leaders[leader["id"]] = leader
        return list(leaders.values())

    @staticmethod
    def _accounted_size(state):
        return sum(job.get("size", 0) for job in state["jobs"].values() if job.get("file_present")) + sum(
            job["bundle_metadata"]["size"] for job in state["jobs"].values() if job.get("bundle_file_present"))

    def _remove_orphans(self, known):
        for path in self.root.iterdir():
            scratch = re.fullmatch(r"\.ipp-[a-z0-9_]{8}\.jpg", path.name)
            bundle_scratch = re.fullmatch(r"\.bundle-(?:[a-f0-9]{32}|[a-z0-9_]{8})\.pdf", path.name)
            orphan = re.fullmatch(r"[a-f0-9]{16}\.(?:bin|part|ipp\.jpg|bundle\.pdf)", path.name) and path.name not in known
            if path.is_file() and (scratch or bundle_scratch or orphan):
                path.unlink(missing_ok=True)

    def file(self, job_id):
        if not re.fullmatch(r"[a-f0-9]{16}", str(job_id)):
            raise ValueError("任务 ID 无效")
        return self.root / f"{job_id}.bin"

    def bundle_file(self, job_id):
        return self.file(job_id).with_suffix(".bundle.pdf")

    def print_file(self, job_id):
        job = self._find(self.state, job_id)
        leader = self._bundle_leader(self.state, job)
        return self.bundle_file(leader["id"]) if leader.get("bundle_metadata") else self.file(leader["id"])

    def _check(self):
        if self.faulted:
            raise ValueError("队列存储异常，已停止领取任务，请重载插件后检查")

    @staticmethod
    def target_key(cfg):
        return hashlib.sha256(json.dumps([cfg.get("ipp_url", ""), cfg.get("ipp_printer_uri", "")], ensure_ascii=False).encode()).hexdigest()

    def route_matches(self, job):
        cfg = self.config()
        backend = job.get("backend", "agent")  # 0.0.1 的任务只属于 Windows 打印端。
        if backend != cfg.get("print_mode", "agent"):
            return False
        if backend == "ipp":
            return job.get("ipp_target") == self.target_key(cfg)
        return job["device_id"] == cfg["device_id"]

    async def _commit(self, snapshot):
        # 写入有歧义时停发所有任务，不能用旧内存状态再次返回 proceed。
        cancelled = False
        try:
            operation = self.ctx.storage.set("print_queue_v1", snapshot)
            try:
                task = self.ctx.create_task(operation, name="print_queue_save")
            except BaseException:
                operation.close()
                raise
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    cancelled = True
                    self.faulted = True
            task.result()
            self.state = snapshot
            if cancelled:
                raise asyncio.CancelledError
        except BaseException:
            self.faulted = True
            raise

    @staticmethod
    def _same_owner(actual, requested):
        # WeCom member IDs are case-insensitive. Preserve their original spelling
        # in saved jobs and receipts; Telegram identifiers remain exact matches.
        if (isinstance(actual, str) and isinstance(requested, str)
                and actual.startswith("wecom:") and requested.startswith("wecom:")):
            return actual.casefold() == requested.casefold()
        return actual == requested

    def _find(self, state, job_id, owner=None, *, source_channel=None, number_batch=None):
        identity = str(job_id)
        job = state["jobs"].get(identity)
        if (job is None and owner is not None and source_channel is not None
                and re.fullmatch(r"[1-9][0-9]{0,8}", identity)):
            number = int(identity)
            if number_batch is not None and (type(number_batch) is not int or not 1 <= number_batch <= MAX_NUMBER):
                raise ValueError("文件批次必须是有效的正整数")
            session = state["number_sessions"].get(self._number_scope(owner, source_channel))
            batch = number_batch if number_batch is not None else (session["batch"] if session else None)
            matches = [candidate for candidate in self._owned_jobs(state, owner, source_channel)
                       if candidate.get("number") == number and candidate.get("number_batch") == batch]
            if len(matches) == 1:
                job = matches[0]
        if (job is None or (owner is not None and not self._same_owner(job["owner"], owner))
                or (source_channel is not None and job.get("source_channel", "") != source_channel)):
            raise ValueError("没有找到你的打印任务")
        return job

    @staticmethod
    def _permission(permission_check):
        if permission_check is None:
            return
        if not callable(permission_check):
            raise ValueError("打印权限检查无效")
        result = permission_check()
        if inspect.isawaitable(result):
            # Authorization must be checked without yielding while holding the
            # queue lock; an accidentally async checker is rejected, not skipped.
            if hasattr(result, "close"):
                result.close()
            raise ValueError("打印权限检查必须同步执行")
        if result is False:
            raise ValueError("打印权限或消息渠道已更改，请重新发送文件。")

    async def get_job(self, job_id, owner, *, source_channel, number_batch=None, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            return self._copy_job(self._find(self.state, job_id, owner, source_channel=source_channel, number_batch=number_batch))

    @classmethod
    def _owned_jobs(cls, state, owner, source_channel):
        # Selection must inspect the complete queue, not the recent-20 display.
        # A Telegram user's files from two different Bots are separate sessions.
        return [job for job in state["jobs"].values()
                if cls._same_owner(job["owner"], owner) and job.get("source_channel", "") == source_channel]

    @staticmethod
    def _latest_job(jobs):
        if not jobs:
            raise ValueError("请先发送照片或 PDF。")
        return max(jobs, key=lambda job: (job.get("created", 0), job.get("updated", 0), job["id"]))

    @staticmethod
    def _source_key(source_key):
        if not isinstance(source_key, str) or not source_key or len(source_key) > 2048:
            raise ValueError("消息标识无效")
        parts = source_key.split(":", 3)
        if len(parts) == 4 and parts[0] in {"wecom", "wx-action", "wx-button"}:
            # The user is case-insensitive, but media and event identifiers are
            # opaque case-sensitive values. Never lowercase the entire key.
            parts[2] = parts[2].casefold()
            return ":".join(parts)
        return source_key

    @classmethod
    def _recent_seen(cls, seen, now):
        result = {}
        for key, stamp in seen.items():
            if now - stamp < 86400:
                normalized = cls._source_key(key)
                result[normalized] = max(result.get(normalized, stamp), stamp)
        return result

    async def claim_message(self, source_key):
        """Persist a text-message receipt before any action it could trigger.

        Replayed WeCom callbacks or Telegram events must not confirm a different
        file that arrived after the first copy of the same command was handled.
        Only opaque source identifiers are stored, never the message body.
        """
        source_key = self._source_key(source_key)
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            now = time.time()
            snapshot["seen"] = self._recent_seen(snapshot["seen"], now)
            if source_key in snapshot["seen"]:
                if snapshot != self.state:
                    await self._commit(snapshot)
                return False
            if len(snapshot["seen"]) >= 2000:
                raise ValueError("今日收件数量达到上限")
            snapshot["seen"][source_key] = now
            await self._commit(snapshot)
            return True

    async def reserve(self, source_key, owner, filename, source, allocation, *, source_channel=""):
        source_key = self._source_key(source_key)
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            now, cfg = time.time(), self.config()
            snapshot["seen"] = self._recent_seen(snapshot["seen"], now)
            if source_key in snapshot["seen"]:
                if snapshot != self.state:
                    await self._commit(snapshot)
                return None
            if sum(job["status"] == "receiving" for job in snapshot["jobs"].values()) >= 4:
                raise ValueError("正在收取其他文件，请稍后重发")
            active = sum(job["status"] in ACTIVE | {"unknown"} for job in snapshot["jobs"].values())
            total = self._accounted_size(snapshot)
            disk_sizes = await asyncio.to_thread(self._disk_sizes)
            reserved_extra = sum(max(0, job.get("size", 0) - disk_sizes.get(f"{job['id']}.part", 0) - disk_sizes.get(f"{job['id']}.bin", 0))
                                 for job in snapshot["jobs"].values() if job["status"] == "receiving")
            total = max(total, sum(disk_sizes.values()) + reserved_extra)
            if active >= cfg["max_queue"]:
                raise ValueError("打印队列已满，请处理现有任务后重试")
            if total + allocation > cfg["max_storage_mb"] * 1024 * 1024:
                raise ValueError("文件存储空间达到上限，请清理已结束任务")
            try:
                self._validate_number_sessions(snapshot)
            except RuntimeError as error:
                self.faulted = True
                raise ValueError(str(error)) from None
            # Use the successful reservation time, not the time before waiting
            # for storage inspection or the queue lock. Rejected receipts never
            # extend the user's five-minute file-numbering window.
            now = time.time()
            scope = self._number_scope(owner, str(source_channel))
            session = snapshot["number_sessions"].get(scope)
            if session is None:
                session = {"batch": 1, "next_number": 1, "last_received": now}
            elif session["last_received"] is None or now - session["last_received"] >= NUMBER_BATCH_IDLE:
                if session["batch"] >= MAX_NUMBER:
                    raise ValueError("打印文件批次已用尽，已停止收件，请联系管理员")
                session = {"batch": session["batch"] + 1, "next_number": 1, "last_received": now}
            number = session["next_number"]
            if number > MAX_NUMBER:
                raise ValueError("打印任务编号已用尽，已停止收件，请联系管理员")
            job_id = secrets.token_hex(8)
            if job_id in snapshot["jobs"]:
                raise ValueError("打印任务标识冲突，请稍后重新发送文件")
            snapshot["jobs"][job_id] = {"id": job_id, "number": number, "number_batch": session["batch"], "owner": owner, "source": source, "source_channel": str(source_channel),
                "filename": filename, "status": "receiving", "created": now, "updated": now,
                "copies": min(cfg["default_copies"], cfg["max_copies"]), "sides": "default", "printer": "IPP" if cfg.get("print_mode") == "ipp" else cfg["printer_name"],
                "device_id": cfg["device_id"], "size": allocation, "file_present": True,
                "claim_token": "", "message": "", "backend": cfg.get("print_mode", "agent"),
                "ipp_target": self.target_key(cfg) if cfg.get("print_mode") == "ipp" else ""}
            session.update(next_number=number + 1, last_received=now)
            snapshot["number_sessions"][scope] = session
            snapshot["seen"][source_key] = now
            # 去重缓存有硬上限；满额时拒绝而非移除仍可能被重放的记录。
            if len(snapshot["seen"]) > 2000:
                raise ValueError("今日收件数量达到上限")
            await self._commit(snapshot)
            return self._copy_job(snapshot["jobs"][job_id])

    async def finish(self, job_id, metadata, *, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            job = self._find(snapshot, job_id)
            if job["status"] != "receiving":
                raise ValueError("任务已取消或已过期")
            if any(key in metadata and (type(metadata[key]) is not int or metadata[key] != job[key])
                   for key in ("number", "number_batch")) or "current_number_batch" in metadata:
                raise ValueError("打印任务编号不能更改")
            if any(key in metadata and metadata[key] != job.get(key) for key in ("id", "owner", "source_channel")):
                raise ValueError("打印任务所属用户、渠道或 ID 不能更改")
            job.update(metadata)
            job.update(status="queued" if self.config()["auto_print"] else "pending", updated=time.time())
            await self._commit(snapshot)
            return self._copy_job(job)

    async def fail_receive(self, job_id, message):
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            job = self._find(snapshot, job_id)
            if job["status"] not in {"receiving", "cancelled"}:
                return None
            if job["status"] == "receiving":
                job.update(status="failed", file_present=False, message=message, updated=time.time())
                await self._commit(snapshot)
            elif job.get("file_present"):
                # The downloader is already finished here. Preserve the user's
                # cancellation; only release its retained-file accounting.
                job["file_present"] = False
                await self._commit(snapshot)
            result = self._copy_job(job)
        # Cleanup may have removed a cancelled file before this downloader
        # completed and replaced its .part file. Unlink even when accounting
        # was already clear, without an unnecessary storage write.
        await self._unlink(self.file(job_id))
        return result

    def _disk_sizes(self):
        return {path.name: path.stat().st_size for path in self.root.iterdir() if path.is_file()}

    async def _unlink(self, path):
        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except BaseException:
            # 清账后文件删除有歧义，停止收件，重载会重新核对孤立文件。
            self.faulted = True
            raise

    def _confirm(self, job, copies=None, printer=None, *, sides=None):
        if job.get("bundle_leader"):
            raise ValueError("该文件已合并为双面打印任务，不会单独重复打印")
        if job["status"] != "pending":
            raise ValueError(f"任务当前为：{LABELS[job['status']]}，不会重复打印")
        cfg = self.config()
        if time.time() - job["created"] > cfg["retention_hours"] * 3600:
            raise ValueError("打印任务已过期，请重新发送文件")
        if not self.route_matches(job):
            raise ValueError("打印连接方式或目标已更改，请取消旧任务并重新发送文件")
        value = job["copies"] if copies is None else copies
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= cfg["max_copies"]:
            raise ValueError(f"打印份数必须是 1～{cfg['max_copies']} 的整数")
        target = job["printer"] if printer is None else str(printer).strip()
        if len(target) > 200 or any(ord(char) < 32 for char in target):
            raise ValueError("打印机名称无效")
        if job.get("backend", "agent") == "ipp" and printer is not None:
            raise ValueError("IPP 模式使用配置中的固定打印机，请不要在命令中另指定打印机")
        if job.get("backend", "agent") == "agent" and target and self.device and target not in self.device.get("printers", []):
            raise ValueError("该打印机不在电脑端允许列表内，请先发送 /printers 查看")
        mode = normalize_sides(job.get("sides", "default") if sides is None else sides)
        if job.get("backend", "agent") == "agent" and mode != "default" and "sides-v1" not in self.device.get("capabilities", []):
            raise ValueError("打印电脑端尚未支持指定单双面，请先更新并连接 0.0.15 或更新版本的电脑端。")
        job.update(status="queued", copies=value, printer=target, sides=mode, updated=time.time())

    async def confirm(self, job_id, owner, copies=None, printer=None, *, sides=None, source_channel=None, number_batch=None, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            job = self._find(snapshot, job_id, owner, source_channel=source_channel, number_batch=number_batch)
            self._confirm(job, copies, printer, sides=sides)
            await self._commit(snapshot)
            return self._copy_job(job)

    async def confirm_single(self, owner, source_channel, copies=None, printer=None, *, sides=None, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            jobs = self._owned_jobs(snapshot, owner, source_channel)
            candidates = self._distinct_jobs(snapshot, [job for job in jobs if job["status"] in ACTIVE | {"unknown"}])
            if len(candidates) > 1:
                raise ValueError("有多个文件。一起打印请回复“全部打印”；只选一个请使用收件提示的文件号，例如“打印文件1”。")
            if not candidates:
                return self._copy_job(self._latest_job(jobs))
            job = candidates[0]
            if job["status"] == "receiving":
                raise ValueError("文件还在接收，请等收到文件的提示后再打印。")
            if job["status"] != "pending":
                return self._copy_job(job)
            self._confirm(job, copies, printer, sides=sides)
            await self._commit(snapshot)
            return self._copy_job(job)

    async def confirm_all(self, owner, source_channel, copies=None, printer=None, *, sides=None, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            jobs = self._owned_jobs(snapshot, owner, source_channel)
            if any(job["status"] == "receiving" for job in jobs):
                raise ValueError("文件还在接收，请等所有文件都提示已收到，再回复全部打印。")
            pending = sorted((job for job in jobs if job["status"] == "pending"),
                             key=lambda job: (job["created"], job["id"]))
            if not pending:
                raise ValueError("没有待确认的文件，已排队或已打印的文件不会重复打印。")
            for job in pending:
                self._confirm(job, copies, printer, sides=sides)
            self._permission(permission_check)
            await self._commit(snapshot)
            return [self._copy_job(job) for job in pending]

    async def prepare_bundle(self, owner, source_channel, *, copies=None, printer=None, sides,
                             permission_check=None):
        """Plan all pending files; bundle images only within each receive batch.

        Rendering is performed outside the queue lock into unique scratch paths.
        The opaque plan is in-memory only: no job is queued until commit_bundle
        atomically validates and binds every prepared PDF plus independent files.
        """
        mode = normalize_sides(sides)
        if mode not in {"two-sided-long-edge", "two-sided-short-edge"}:
            return None
        async with self.lock:
            self._permission(permission_check)
            self._check()
            self._validate_bundles(self.state)
            cfg = copy.deepcopy(self.config())
            jobs = self._owned_jobs(self.state, owner, source_channel)
            if any(job["status"] == "receiving" for job in jobs):
                raise ValueError("文件还在接收，请等所有文件都提示已收到，再回复全部双面打印。")
            pending = sorted((job for job in jobs if job["status"] == "pending"),
                             key=lambda job: (job["number_batch"], job["number"]))
            if not pending:
                raise ValueError("没有待确认的文件，已排队或已打印的文件不会重复打印。")
            confirmed = {}
            candidates = {}
            batch_targets = {}
            for job in pending:
                proposed = copy.deepcopy(job)
                self._confirm(proposed, copies, printer, sides=mode)
                confirmed[job["id"]] = proposed
                if job.get("format") in IMAGE_FORMATS and job.get("pages") == 1:
                    # Original per-file choices remain authoritative unless the
                    # command explicitly overrides them. Never mix copy counts
                    # or printer destinations into one physical document.
                    key = (job["number_batch"], proposed["copies"], proposed["printer"])
                    candidates.setdefault(key, []).append(job)
                    batch_targets.setdefault(job["number_batch"], []).append((proposed["copies"], proposed["printer"]))
            if any(len(targets) >= 2 and len(set(targets)) > 1 for targets in batch_targets.values()):
                raise ValueError("同一批图片的打印份数或打印机不同，未提交任何文件；请指定统一份数和打印机后再全部双面打印。")
            groups = []
            for images in candidates.values():
                if len(images) < 2:
                    continue
                leader = images[0]
                requested_copies = confirmed[leader["id"]]["copies"]
                actual_pages = (len(images) + len(images) % 2) * requested_copies
                if actual_pages > cfg["max_pages"]:
                    raise ValueError("合并双面打印的总页数超过上限，请减少图片或打印份数。")
                if any(not job.get("file_present") for job in images):
                    raise ValueError("待打印图片已清理，请重新发送文件。")
                target_path = self.root / f".bundle-{secrets.token_hex(16)}.pdf"
                if target_path.exists():
                    raise ValueError("合并文件标识冲突，请稍后再试。")
                groups.append({"leader_id": leader["id"], "job_ids": [job["id"] for job in images],
                               "number_batch": leader["number_batch"], "requested_copies": requested_copies,
                               "sources": [{"id": job["id"], "path": self.file(job["id"]),
                                            **{key: job[key] for key in ("filename", "sha256", "format", "size")}}
                                           for job in images], "target_path": target_path})
            if not groups:
                return None
            disk_sizes = await asyncio.to_thread(self._disk_sizes)
            reserved_extra = sum(max(0, job.get("size", 0) - disk_sizes.get(f"{job['id']}.part", 0)
                                     - disk_sizes.get(f"{job['id']}.bin", 0))
                                 for job in self.state["jobs"].values() if job["status"] == "receiving")
            used_storage = max(self._accounted_size(self.state), sum(disk_sizes.values()) + reserved_extra)
            remaining_storage = int(cfg["max_storage_mb"] * 1024 * 1024) - used_storage
            if remaining_storage <= 0:
                raise ValueError("合并 PDF 没有可用存储空间，未提交任何文件，请先清理已结束任务。")
            token = secrets.token_hex(32)
            if token in self.bundle_plans:
                raise ValueError("合并准备标识冲突，请稍后再试。")
            grouped = {identity for group in groups for identity in group["job_ids"]}
            plan = {"token": token, "job_ids": [job["id"] for job in pending], "groups": groups,
                    "independent_ids": [job["id"] for job in pending if job["id"] not in grouped],
                    "remaining_storage_bytes": remaining_storage}
            self._permission(permission_check)
            if self.config() != cfg:
                raise ValueError("打印设置已更改，请重新确认打印。")
            self.bundle_plans[token] = {"plan": copy.deepcopy(plan), "jobs": copy.deepcopy(pending),
                                        "config": cfg, "copies": copies, "printer": printer, "sides": mode}
            return copy.deepcopy(plan)

    def _prepared_bundle(self, plan):
        if not isinstance(plan, dict) or not isinstance(plan.get("token"), str):
            raise ValueError("合并打印准备已失效，请重新确认打印。")
        prepared = self.bundle_plans.get(plan["token"])
        if prepared is None or prepared["plan"] != plan:
            raise ValueError("合并打印准备已失效，请重新确认打印。")
        return prepared

    @staticmethod
    async def _inspect_bundle_file(path, max_bytes, max_pages):
        # A cancelled confirmation must finish its read before finally removing
        # scratch files, particularly on Windows where an open PDF cannot be
        # unlinked. The executor future itself is never cancelled by the caller.
        future = asyncio.get_running_loop().run_in_executor(None, inspect_file, path,
                                                            "合并双面打印.pdf", max_bytes, max_pages)
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            while not future.done():
                try:
                    await asyncio.shield(future)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if future.done() and not future.cancelled():
                future.exception()
            raise

    async def commit_bundle(self, plan, metadatas, *, permission_check=None):
        """Publish prepared PDFs and queue the full selection in one commit.

        A storage failure can mean the commit succeeded. Published artifacts are
        then retained and queue issuance is frozen, never deleted or retried.
        """
        async with self.lock:
            self._permission(permission_check)
            self._check()
            prepared = self._prepared_bundle(plan)
            if not isinstance(metadatas, list) or len(metadatas) != len(plan["groups"]):
                raise ValueError("合并打印文件数量不符，未提交任何文件。")
            if self.config() != prepared["config"]:
                raise ValueError("打印设置已更改，未提交任何文件，请重新确认。")
            snapshot = copy.deepcopy(self.state)
            for original in prepared["jobs"]:
                if snapshot["jobs"].get(original["id"]) != original:
                    raise ValueError("待打印文件状态已更改，未提交任何文件，请重新确认。")
            observed = []
            for group, supplied in zip(plan["groups"], metadatas):
                if not isinstance(supplied, dict):
                    raise ValueError("合并 PDF 信息无效，未提交任何文件。")
                actual = await self._inspect_bundle_file(group["target_path"],
                                                        prepared["config"]["max_file_mb"] * 1024 * 1024,
                                                        prepared["config"]["max_pages"])
                expected_pages = (len(group["job_ids"]) + len(group["job_ids"]) % 2) * group["requested_copies"]
                if (actual["format"] != "pdf" or actual["pages"] != expected_pages
                        or any(type(supplied.get(key)) is not type(actual[key]) or supplied[key] != actual[key]
                               for key in ("format", "pages", "size", "sha256"))):
                    raise ValueError("合并 PDF 的页数、大小或校验值不符，未提交任何文件。")
                observed.append(actual)
            self._permission(permission_check)
            if self.config() != prepared["config"]:
                raise ValueError("打印设置已更改，未提交任何文件，请重新确认。")
            for original in prepared["jobs"]:
                self._confirm(snapshot["jobs"][original["id"]], prepared["copies"],
                              prepared["printer"], sides=prepared["sides"])
            disk_sizes = await asyncio.to_thread(self._disk_sizes)
            reserved_extra = sum(max(0, job.get("size", 0) - disk_sizes.get(f"{job['id']}.part", 0)
                                     - disk_sizes.get(f"{job['id']}.bin", 0))
                                 for job in snapshot["jobs"].values() if job["status"] == "receiving")
            total = max(self._accounted_size(snapshot) + sum(item["size"] for item in observed),
                        sum(disk_sizes.values()) + reserved_extra)
            if total > prepared["config"]["max_storage_mb"] * 1024 * 1024:
                raise ValueError("合并 PDF 后的文件存储空间超过上限，未提交任何文件。")
            self._permission(permission_check)
            if self.config() != prepared["config"]:
                raise ValueError("打印设置已更改，未提交任何文件，请重新确认。")
            published = []
            try:
                for group, metadata in zip(plan["groups"], observed):
                    destination = self.bundle_file(group["leader_id"])
                    if destination.exists():
                        raise ValueError("合并 PDF 存储位置已有文件，未覆盖或提交，请重载插件后检查。")
                    # Same-instance queue/file names are owned under this lock.
                    # Rename is synchronous so cancellation cannot leave a
                    # background move racing cleanup or a later reservation.
                    group["target_path"].rename(destination)
                    published.append((destination, group["target_path"]))
                    leader = snapshot["jobs"][group["leader_id"]]
                    for identity in group["job_ids"]:
                        snapshot["jobs"][identity]["bundle_leader"] = leader["id"]
                    leader.update(bundle_members=list(group["job_ids"]), bundle_metadata=metadata,
                                  bundle_file_present=True, bundle_input_pages=len(group["job_ids"]),
                                  bundle_image_count=len(group["job_ids"]))
                self._validate_bundles(snapshot)
                await self._commit(snapshot)
            except BaseException:
                if not self.faulted:
                    try:
                        for destination, scratch in reversed(published):
                            destination.rename(scratch)
                    except BaseException:
                        self.faulted = True
                raise
            return [self._copy_job(self.state["jobs"][identity]) for identity in plan["job_ids"]]

    async def discard_bundle(self, plan):
        """Remove only known unbound scratch files, never a published artifact."""
        async with self.lock:
            prepared = self._prepared_bundle(plan)
            self.bundle_plans.pop(plan["token"], None)
            for group in prepared["plan"]["groups"]:
                await self._unlink(group["target_path"])

    @staticmethod
    def _cancel(job):
        if job["status"] not in {"receiving", "pending", "queued", "leased"}:
            raise ValueError("任务已开始或已结束，不能保证取消；请在打印机或系统打印队列中查看")
        job.update(status="cancelled", updated=time.time())

    def _cancel_group(self, state, job):
        leader = self._bundle_leader(state, job)
        self._cancel(leader)
        self._group_update(state, leader, status="cancelled", updated=leader["updated"])

    async def cancel(self, job_id, owner, *, source_channel=None, number_batch=None, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            job = self._find(snapshot, job_id, owner, source_channel=source_channel, number_batch=number_batch)
            self._cancel_group(snapshot, job)
            await self._commit(snapshot)
            return self._copy_job(job)

    async def cancel_single(self, owner, source_channel, *, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            jobs = self._owned_jobs(snapshot, owner, source_channel)
            candidates = self._distinct_jobs(snapshot, [job for job in jobs if job["status"] in ACTIVE | {"unknown"}])
            if len(candidates) > 1:
                raise ValueError("有多个文件。全部不要请回复“全部取消”；只取消一个请使用收件提示的文件号，例如“取消文件1”。")
            if not candidates:
                return self._copy_job(self._latest_job(jobs))
            job = candidates[0]
            if job["status"] not in {"receiving", "pending", "queued", "leased"}:
                return self._copy_job(job)
            self._cancel_group(snapshot, job)
            await self._commit(snapshot)
            return self._copy_job(job)

    async def cancel_all(self, owner, source_channel, *, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            jobs = self._owned_jobs(snapshot, owner, source_channel)
            cancelled = [job for job in jobs if job["status"] in {"receiving", "pending", "queued", "leased"}]
            untouched = [job for job in jobs if job["status"] in {"started", "unknown"}]
            for job in self._distinct_jobs(snapshot, cancelled):
                self._cancel_group(snapshot, job)
            self._permission(permission_check)
            if cancelled:
                await self._commit(snapshot)
            return {"cancelled": [self._copy_job(job) for job in cancelled],
                    "untouched": [self._copy_job(job) for job in untouched]}

    async def status_single(self, owner, source_channel, *, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            jobs = self._owned_jobs(self.state, owner, source_channel)
            candidates = self._distinct_jobs(self.state, [job for job in jobs if job["status"] in ACTIVE | {"unknown"}])
            if len(candidates) > 1:
                raise ValueError("有多个文件，请回复“任务”查看文件号，再发送对应指令，例如“查看文件1”。")
            return self._copy_job(candidates[0] if candidates else self._latest_job(jobs))

    async def jobs(self, owner=None, *, source_channel=None):
        async with self.lock:
            return [self.public(job) for job in sorted(self.state["jobs"].values(), key=lambda j: j["created"], reverse=True)
                    if (owner is None or self._same_owner(job["owner"], owner))
                    and (source_channel is None or job.get("source_channel", "") == source_channel)][:20]

    def public(self, job):
        copy_job = self._copy_job(job)
        result = {key: copy_job.get(key) for key in ("id", "number", "number_batch", "current_number_batch", "source", "filename", "status", "copies", "printer", "pages", "created", "updated", "message",
                                                  "bundle_leader", "bundle_members", "bundle_image_count", "bundle_input_pages", "bundle_pages")}
        result["backend"] = job.get("backend", "agent")
        result["sides"] = job.get("sides", "default")
        return result

    async def hello(self, payload):
        printers = payload.get("printers", [])
        formats = payload.get("formats", [])
        capabilities = payload.get("capabilities", [])
        if (not isinstance(printers, list) or not isinstance(formats, list) or len(printers) > 100 or len(formats) > 10
                or not isinstance(capabilities, list) or len(capabilities) > 10
                or any(not isinstance(value, str) for value in capabilities)):
            raise ValueError("电脑端信息无效")
        printers = [value for value in printers if isinstance(value, str) and 0 < len(value) <= 200 and not any(ord(c) < 32 for c in value)]
        self.device = {"printers": list(dict.fromkeys(printers)), "formats": [f for f in formats if isinstance(f, str) and f in {"pdf", "png", "jpg", "jpeg", "webp", "bmp"}],
                       "default_printer": str(payload.get("default_printer", ""))[:200], "last_seen": time.time(),
                       "capabilities": [value for value in capabilities if value == "sides-v1"]}
        return {"ok": True}

    async def poll(self, backend="agent", *, agent_capabilities=None):
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            self._validate_bundles(snapshot)
            cfg, now = self.config(), time.time()
            if backend != cfg.get("print_mode", "agent"):
                return {"ok": True, "job": None}
            if backend == "agent":
                self.device["last_seen"] = now
            # 一台电脑只处理一个任务；未确认是否已提交时不领取其他任务。
            if any(job["status"] in {"leased", "started"} for job in snapshot["jobs"].values()):
                return {"ok": True, "job": None}
            for job in snapshot["jobs"].values():
                if job.get("bundle_leader") and job["bundle_leader"] != job["id"]:
                    continue
                if job["status"] != "queued" or not self.route_matches(job):
                    continue
                if now - job["created"] > cfg["retention_hours"] * 3600:
                    continue  # Slow cleanup must not make expired files printable.
                printable = job.get("bundle_metadata", job)
                if backend == "agent" and printable.get("format") not in self.device.get("formats", []):
                    continue
                # Bind this grant to the requesting receiver, not another poll's
                # shared inventory while this call was waiting for the lock.
                capabilities = self.device.get("capabilities", []) if agent_capabilities is None else agent_capabilities
                if backend == "agent" and job.get("sides", "default") != "default" and "sides-v1" not in capabilities:
                    self._group_update(snapshot, job, status="failed", updated=now,
                                       message="打印电脑端未支持指定单双面，未提交打印；请更新电脑端后重新发送文件。")
                    await self._commit(snapshot)
                    return {"ok": True, "job": None, "rejected": self._copy_job(job)}
                self._group_update(snapshot, job, status="leased", claim_token=secrets.token_urlsafe(32), lease_until=now + 300, updated=now)
                await self._commit(snapshot)
                result = {key: job[key] for key in ("id", "claim_token", "printer", "copies")}
                result.update((key, printable[key]) for key in ("filename", "size", "sha256", "format"))
                if "pages" in printable:
                    result["pages"] = printable["pages"]
                result["max_pages"] = cfg["max_pages"]
                result["sides"] = job.get("sides", "default")
                if job.get("bundle_metadata"):
                    result["requested_copies"] = job["copies"]
                    result["copies"] = 1
                    result["bundle_image_count"] = job["bundle_image_count"]
                numbered = self._copy_job(job)
                result.update((key, numbered[key]) for key in ("number", "number_batch", "current_number_batch"))
                return {"ok": True, "job": result}
            return {"ok": True, "job": None}

    def _claim(self, snapshot, job_id, token, check_route=True):
        job = self._find(snapshot, job_id)
        if ((job.get("bundle_leader") and job["bundle_leader"] != job["id"])
                or (check_route and not self.route_matches(job)) or not isinstance(token, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token)
                or not hmac.compare_digest(str(job.get("claim_token", "")), token)):
            raise ValueError("任务领取凭据无效")
        return job

    async def downloadable(self, job_id, token):
        async with self.lock:
            self._check()
            job = self._claim(self.state, job_id, token)
            file_present = job.get("bundle_file_present") if job.get("bundle_metadata") else job.get("file_present")
            if job["status"] != "leased" or time.time() > job.get("lease_until", 0) or not file_present:
                raise ValueError("任务已过期或不在准备阶段")
            return self.print_file(job_id)

    async def start(self, job_id, token):
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            job = self._claim(snapshot, job_id, token)
            if job["status"] != "leased" or time.time() > job.get("lease_until", 0):
                return {"ok": True, "proceed": False}
            if time.time() - job["created"] > self.config()["retention_hours"] * 3600:
                raise ValueError("打印任务已过期，未提交打印，请重新发送文件")
            cfg = self.config()
            if (type(job.get("copies")) is not int or not 1 <= job["copies"] <= cfg["max_copies"]
                    or (job.get("bundle_metadata") and job["bundle_metadata"]["pages"] > cfg["max_pages"])):
                raise ValueError("打印份数或总页数已超过当前限制，未提交打印，请重新发送文件。")
            self._group_update(snapshot, job, status="started", updated=time.time())
            await self._commit(snapshot)
            return {"ok": True, "proceed": True}

    async def result(self, job_id, token, status, spool_id="", message=None):
        if status not in {"submitted", "failed", "unknown"}:
            raise ValueError("打印结果无效")
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            if not re.fullmatch(r"[a-f0-9]{16}", str(job_id)):
                raise ValueError("任务 ID 无效")
            if job_id not in snapshot["jobs"]:
                # 旧记录已按保留策略清理。允许打印端结束补报，不能因此重新打印。
                return None
            job = self._claim(snapshot, job_id, token, check_route=False)
            if job["status"] == status or (job["status"] in {"submitted", "failed", "cancelled", "archived"}):
                return None
            if job["status"] not in {"leased", "started", "unknown"}:
                raise ValueError("任务当前不能接收打印结果")
            if job["status"] == "leased" and status == "submitted":
                raise ValueError("未获得提交许可，不能标记打印已提交")
            message = message or {"submitted": "已提交到打印队列；实际出纸请查看打印机", "failed": "未能完成打印提交，请查看日志",
                       "unknown": "提交结果不确定，请核查打印机队列；不会自动重打"}[status]
            self._group_update(snapshot, job, status=status, message=message, spool_id=str(spool_id)[:64], updated=time.time())
            await self._commit(snapshot)
            return self._copy_job(job)

    async def archive_unknown(self):
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            count = 0
            for job in self._distinct_jobs(snapshot, list(snapshot["jobs"].values())):
                if job["status"] == "unknown":
                    self._group_update(snapshot, job, status="archived", message="管理员确认已核查并归档；未重新打印", updated=time.time())
                    count += len(self._group_jobs(snapshot, job))
            if count:
                await self._commit(snapshot)
            return count

    async def cleanup(self, completed_only=False):
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            self._validate_bundles(snapshot)
            now, horizon = time.time(), self.config()["retention_hours"] * 3600
            paths, notifications = [], []
            for job in self._distinct_jobs(snapshot, list(snapshot["jobs"].values())):
                status = job["status"]
                if status == "leased" and now > job.get("lease_until", 0):
                    self._group_update(snapshot, job, status="failed", message="打印准备超时，未自动重新打印；请检查后重发", updated=now)
                    notifications.append(self._copy_job(job))
                elif status == "started" and now - job["updated"] > 600:
                    self._group_update(snapshot, job, status="unknown", message="未收到打印结果，需核查打印队列", updated=now)
                    notifications.append(self._copy_job(job))
                if job["status"] in {"pending", "queued"} and now - job["created"] > horizon:
                    self._group_update(snapshot, job, status="cancelled", message="未及时打印，任务已过期", updated=now)
                    notifications.append(self._copy_job(job))
                status = job["status"]
                if status in {"pending", "queued"} and not self.route_matches(job):
                    self._group_update(snapshot, job, status="failed", message="打印方式或目标已更改，旧任务未转发；请重新发送", updated=now)
                    notifications.append(self._copy_job(job))
                status = job["status"]
                if status in TERMINAL and (now - job["updated"] > horizon or (completed_only and status != "unknown")):
                    for member in self._group_jobs(snapshot, job):
                        if member.get("file_present"):
                            paths.append(self.file(member["id"]))
                            member["file_present"] = False
                    if job.get("bundle_file_present"):
                        paths.append(self.bundle_file(job["id"]))
                        job["bundle_file_present"] = False
            # Retain recent records by whole physical task. A group must never
            # leave behind orphan members whose leader was dropped at row 200.
            terminals = sorted((job for job in self._distinct_jobs(snapshot, list(snapshot["jobs"].values()))
                                if job["status"] in {"submitted", "failed", "cancelled", "archived"}
                                and not job.get("bundle_file_present")
                                and all(not member.get("file_present") for member in self._group_jobs(snapshot, job))),
                               key=lambda job: job["updated"], reverse=True)
            retained = 0
            for job in terminals:
                members = self._group_jobs(snapshot, job)
                if retained + len(members) <= 200:
                    retained += len(members)
                else:
                    for member in members:
                        snapshot["jobs"].pop(member["id"], None)
            snapshot["seen"] = {key: stamp for key, stamp in snapshot["seen"].items() if now - stamp < 86400}
            if snapshot != self.state:
                await self._commit(snapshot)
            for path in paths:
                await self._unlink(path)
            return len(paths), notifications
