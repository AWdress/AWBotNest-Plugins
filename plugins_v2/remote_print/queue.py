"""单实例持久打印队列：只重领未开始的任务，不重试可能已经出纸的任务。"""
from __future__ import annotations

import asyncio
import copy
import hmac
import hashlib
import inspect
import json
import re
import secrets
import time
from pathlib import Path


ACTIVE = {"receiving", "pending", "queued", "leased", "started"}
TERMINAL = {"submitted", "failed", "unknown", "cancelled", "archived"}
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
        self.state = {"jobs": {}, "seen": {}}
        self.device = {}
        self.faulted = False
        self.process_lock = None

    async def open(self):
        await asyncio.to_thread(self.root.mkdir, parents=True, exist_ok=True)
        self.process_lock = await asyncio.to_thread(instance_lock, self.root.parent / "print_server.lock")
        self.ctx.add_cleanup(self.close)
        state = await self.ctx.storage.get("print_queue_v1", {"jobs": {}, "seen": {}})
        if not isinstance(state, dict) or not isinstance(state.get("jobs"), dict) or not isinstance(state.get("seen"), dict):
            raise RuntimeError("打印队列数据损坏，未重建或自动重打，请先备份并检查")
        self.state = state
        async with self.lock:
            snapshot = copy.deepcopy(state)
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
        await asyncio.to_thread(self._remove_orphans, known)
        await self.cleanup()

    def close(self):
        if self.process_lock is not None:
            self.process_lock.close()
            self.process_lock = None

    def _remove_orphans(self, known):
        for path in self.root.iterdir():
            scratch = re.fullmatch(r"\.ipp-[a-z0-9_]{8}\.jpg", path.name)
            orphan = re.fullmatch(r"[a-f0-9]{16}\.(?:bin|part|ipp\.jpg)", path.name) and path.name not in known
            if path.is_file() and (scratch or orphan):
                path.unlink(missing_ok=True)

    def file(self, job_id):
        if not re.fullmatch(r"[a-f0-9]{16}", str(job_id)):
            raise ValueError("任务 ID 无效")
        return self.root / f"{job_id}.bin"

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

    def _find(self, state, job_id, owner=None, *, source_channel=None):
        job = state["jobs"].get(str(job_id))
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

    async def get_job(self, job_id, owner, *, source_channel, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            return copy.deepcopy(self._find(self.state, job_id, owner, source_channel=source_channel))

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
            total = sum(job.get("size", 0) for job in snapshot["jobs"].values() if job.get("file_present"))
            disk_sizes = await asyncio.to_thread(self._disk_sizes)
            reserved_extra = sum(max(0, job.get("size", 0) - disk_sizes.get(f"{job['id']}.part", 0) - disk_sizes.get(f"{job['id']}.bin", 0))
                                 for job in snapshot["jobs"].values() if job["status"] == "receiving")
            total = max(total, sum(disk_sizes.values()) + reserved_extra)
            if active >= cfg["max_queue"]:
                raise ValueError("打印队列已满，请处理现有任务后重试")
            if total + allocation > cfg["max_storage_mb"] * 1024 * 1024:
                raise ValueError("文件存储空间达到上限，请清理已结束任务")
            job_id = secrets.token_hex(8)
            snapshot["jobs"][job_id] = {"id": job_id, "owner": owner, "source": source, "source_channel": str(source_channel),
                "filename": filename, "status": "receiving", "created": now, "updated": now,
                "copies": min(cfg["default_copies"], cfg["max_copies"]), "printer": "IPP" if cfg.get("print_mode") == "ipp" else cfg["printer_name"],
                "device_id": cfg["device_id"], "size": allocation, "file_present": True,
                "claim_token": "", "message": "", "backend": cfg.get("print_mode", "agent"),
                "ipp_target": self.target_key(cfg) if cfg.get("print_mode") == "ipp" else ""}
            snapshot["seen"][source_key] = now
            # 去重缓存有硬上限；满额时拒绝而非移除仍可能被重放的记录。
            if len(snapshot["seen"]) > 2000:
                raise ValueError("今日收件数量达到上限")
            await self._commit(snapshot)
            return copy.deepcopy(snapshot["jobs"][job_id])

    async def finish(self, job_id, metadata, *, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            job = self._find(snapshot, job_id)
            if job["status"] != "receiving":
                raise ValueError("任务已取消或已过期")
            job.update(metadata)
            job.update(status="queued" if self.config()["auto_print"] else "pending", updated=time.time())
            await self._commit(snapshot)
            return copy.deepcopy(job)

    async def fail_receive(self, job_id, message):
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            job = self._find(snapshot, job_id)
            if job["status"] != "receiving":
                return
            job.update(status="failed", file_present=False, message=message, updated=time.time())
            await self._commit(snapshot)
        await self._unlink(self.file(job_id))

    def _disk_sizes(self):
        return {path.name: path.stat().st_size for path in self.root.iterdir() if path.is_file()}

    async def _unlink(self, path):
        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except BaseException:
            # 清账后文件删除有歧义，停止收件，重载会重新核对孤立文件。
            self.faulted = True
            raise

    def _confirm(self, job, copies=None, printer=None):
        if job["status"] != "pending":
            raise ValueError(f"任务当前为：{LABELS[job['status']]}，不会重复打印")
        cfg = self.config()
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
        job.update(status="queued", copies=value, printer=target, updated=time.time())

    async def confirm(self, job_id, owner, copies=None, printer=None, *, source_channel=None, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            job = self._find(snapshot, job_id, owner, source_channel=source_channel)
            self._confirm(job, copies, printer)
            await self._commit(snapshot)
            return copy.deepcopy(job)

    async def confirm_single(self, owner, source_channel, copies=None, printer=None, *, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            jobs = self._owned_jobs(snapshot, owner, source_channel)
            candidates = [job for job in jobs if job["status"] in ACTIVE | {"unknown"}]
            if len(candidates) > 1:
                raise ValueError("有多个文件，请按对应文件的按钮或任务编号选择，不会自动选一个打印。")
            if not candidates:
                return copy.deepcopy(self._latest_job(jobs))
            job = candidates[0]
            if job["status"] == "receiving":
                raise ValueError("文件还在接收，请等收到文件的提示后再打印。")
            if job["status"] != "pending":
                return copy.deepcopy(job)
            self._confirm(job, copies, printer)
            await self._commit(snapshot)
            return copy.deepcopy(job)

    @staticmethod
    def _cancel(job):
        if job["status"] not in {"receiving", "pending", "queued", "leased"}:
            raise ValueError("任务已开始或已结束，不能保证取消；请在打印机或系统打印队列中查看")
        job.update(status="cancelled", updated=time.time())

    async def cancel(self, job_id, owner, *, source_channel=None, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            job = self._find(snapshot, job_id, owner, source_channel=source_channel)
            self._cancel(job)
            await self._commit(snapshot)
            return copy.deepcopy(job)

    async def cancel_single(self, owner, source_channel, *, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            self._check()
            snapshot = copy.deepcopy(self.state)
            jobs = self._owned_jobs(snapshot, owner, source_channel)
            candidates = [job for job in jobs if job["status"] in ACTIVE | {"unknown"}]
            if len(candidates) > 1:
                raise ValueError("有多个文件，请按对应文件的按钮或任务编号选择，不会自动选一个取消。")
            if not candidates:
                return copy.deepcopy(self._latest_job(jobs))
            job = candidates[0]
            if job["status"] not in {"receiving", "pending", "queued", "leased"}:
                return copy.deepcopy(job)
            self._cancel(job)
            await self._commit(snapshot)
            return copy.deepcopy(job)

    async def status_single(self, owner, source_channel, *, permission_check=None):
        async with self.lock:
            self._permission(permission_check)
            jobs = self._owned_jobs(self.state, owner, source_channel)
            candidates = [job for job in jobs if job["status"] in ACTIVE | {"unknown"}]
            if len(candidates) > 1:
                raise ValueError("有多个文件，请按对应文件的按钮或任务编号查看进度。")
            return copy.deepcopy(candidates[0] if candidates else self._latest_job(jobs))

    async def jobs(self, owner=None):
        async with self.lock:
            return [self.public(job) for job in sorted(self.state["jobs"].values(), key=lambda j: j["created"], reverse=True)
                    if owner is None or self._same_owner(job["owner"], owner)][:20]

    @staticmethod
    def public(job):
        result = {key: job.get(key) for key in ("id", "filename", "status", "copies", "printer", "pages", "created", "updated", "message")}
        result["backend"] = job.get("backend", "agent")
        return result

    async def hello(self, payload):
        printers = payload.get("printers", [])
        formats = payload.get("formats", [])
        if not isinstance(printers, list) or not isinstance(formats, list) or len(printers) > 100 or len(formats) > 10:
            raise ValueError("电脑端信息无效")
        printers = [value for value in printers if isinstance(value, str) and 0 < len(value) <= 200 and not any(ord(c) < 32 for c in value)]
        self.device = {"printers": list(dict.fromkeys(printers)), "formats": [f for f in formats if isinstance(f, str) and f in {"pdf", "png", "jpg", "jpeg", "webp", "bmp"}],
                       "default_printer": str(payload.get("default_printer", ""))[:200], "last_seen": time.time()}
        return {"ok": True}

    async def poll(self, backend="agent"):
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            cfg, now = self.config(), time.time()
            if backend != cfg.get("print_mode", "agent"):
                return {"ok": True, "job": None}
            if backend == "agent":
                self.device["last_seen"] = now
            # 一台电脑只处理一个任务；未确认是否已提交时不领取其他任务。
            if any(job["status"] in {"leased", "started"} for job in snapshot["jobs"].values()):
                return {"ok": True, "job": None}
            for job in snapshot["jobs"].values():
                if job["status"] != "queued" or not self.route_matches(job):
                    continue
                if backend == "agent" and job.get("format") not in self.device.get("formats", []):
                    continue
                job.update(status="leased", claim_token=secrets.token_urlsafe(32), lease_until=now + 300, updated=now)
                await self._commit(snapshot)
                result = {key: job[key] for key in ("id", "claim_token", "filename", "size", "sha256", "format", "printer", "copies")}
                result["max_pages"] = cfg["max_pages"]
                return {"ok": True, "job": result}
            return {"ok": True, "job": None}

    def _claim(self, snapshot, job_id, token, check_route=True):
        job = self._find(snapshot, job_id)
        if ((check_route and not self.route_matches(job)) or not isinstance(token, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token)
                or not hmac.compare_digest(str(job.get("claim_token", "")), token)):
            raise ValueError("任务领取凭据无效")
        return job

    async def downloadable(self, job_id, token):
        async with self.lock:
            self._check()
            job = self._claim(self.state, job_id, token)
            if job["status"] != "leased" or time.time() > job.get("lease_until", 0) or not job.get("file_present"):
                raise ValueError("任务已过期或不在准备阶段")
            return self.file(job_id)

    async def start(self, job_id, token):
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            job = self._claim(snapshot, job_id, token)
            if job["status"] != "leased" or time.time() > job.get("lease_until", 0):
                return {"ok": True, "proceed": False}
            job.update(status="started", updated=time.time())
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
            job.update(status=status, message=message, spool_id=str(spool_id)[:64], updated=time.time())
            await self._commit(snapshot)
            return copy.deepcopy(job)

    async def archive_unknown(self):
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            count = 0
            for job in snapshot["jobs"].values():
                if job["status"] == "unknown":
                    job.update(status="archived", message="管理员确认已核查并归档；未重新打印", updated=time.time())
                    count += 1
            if count:
                await self._commit(snapshot)
            return count

    async def cleanup(self, completed_only=False):
        async with self.lock:
            self._check()
            snapshot = copy.deepcopy(self.state)
            now, horizon = time.time(), self.config()["retention_hours"] * 3600
            paths, notifications = [], []
            for job in snapshot["jobs"].values():
                status = job["status"]
                if status == "leased" and now > job.get("lease_until", 0):
                    job.update(status="failed", message="打印准备超时，未自动重新打印；请检查后重发", updated=now)
                    notifications.append(copy.deepcopy(job))
                elif status == "started" and now - job["updated"] > 600:
                    job.update(status="unknown", message="未收到打印结果，需核查打印队列", updated=now)
                    notifications.append(copy.deepcopy(job))
                if job["status"] in {"pending", "queued"} and now - job["created"] > horizon:
                    job.update(status="cancelled", message="未及时打印，任务已过期", updated=now)
                    notifications.append(copy.deepcopy(job))
                status = job["status"]
                if status in {"pending", "queued"} and not self.route_matches(job):
                    job.update(status="failed", message="打印方式或目标已更改，旧任务未转发；请重新发送", updated=now)
                    notifications.append(copy.deepcopy(job))
                status = job["status"]
                if job.get("file_present") and status in TERMINAL and (now - job["updated"] > horizon or (completed_only and status != "unknown")):
                    paths.append(self.file(job["id"]))
                    job["file_present"] = False
            # 保留最近 200 个已结束记录；未知结果不自动遗忘。
            terminals = sorted((j for j in snapshot["jobs"].values() if j["status"] in {"submitted", "failed", "cancelled", "archived"} and not j.get("file_present")), key=lambda j: j["updated"], reverse=True)
            for job in terminals[200:]:
                snapshot["jobs"].pop(job["id"], None)
            snapshot["seen"] = {key: stamp for key, stamp in snapshot["seen"].items() if now - stamp < 86400}
            if snapshot != self.state:
                await self._commit(snapshot)
            for path in paths:
                await self._unlink(path)
            return len(paths), notifications
