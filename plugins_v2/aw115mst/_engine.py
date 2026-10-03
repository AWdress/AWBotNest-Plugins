"""Serial, resumable file workflow. Network access uses the platform adapter."""
from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
import time

from . import _files
from ._config import normalize
from ._store import Store, file_key, settled


class Engine:
    def __init__(self, ctx, adapter_factory=None):
        self.ctx = ctx
        self.store = Store(ctx.data_dir)
        self.adapter_factory = adapter_factory
        self.task = None
        self.lock = asyncio.Lock()
        self.closed = False
        self.progress = 0
        self.current = ""
        self.message = "尚未运行"
        self.last_result = {}
        self.observed = {}

    @property
    def running(self):
        return self.task is not None and not self.task.done()

    @staticmethod
    def _cancel_point():
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError

    async def recover(self):
        for record in await self.store.all():
            if record["state"] in {"checking", "uploading"}:
                record.update(state="cloud_unknown", message="上次任务中断，网盘结果待核对；不自动重复上传")
                await self.store.put(record)

    async def adapter(self, config):
        cookie = config["cookie"]
        if not cookie:
            cookie = await self.ctx.cookies.header("115.com")
        if not cookie:
            raise ValueError("请保存 115 Cookie、扫码登录，或在平台同步 115 Cookie")
        factory = self.adapter_factory
        if factory is None:
            from ._p115 import P115Adapter
            factory = P115Adapter
        return factory(self.ctx, cookie, timeout=config["request_timeout"])

    async def start(self, mode="scan", source="手动"):
        if mode not in {"scan", "recheck", "all"}:
            return {"ok": False, "message": "运行模式无效"}
        async with self.lock:
            if self.closed:
                return {"ok": False, "message": "插件已停用"}
            if self.running:
                return {"ok": False, "message": "任务正在运行，请先停止或等待完成"}
            try:
                config = normalize(self.ctx.config)
                roots = _files.validate_roots(self.ctx.data_dir, config)
                adapter = await self.adapter(config)
            except (ValueError, RuntimeError) as exc:
                return {"ok": False, "message": str(exc)}
            self.progress, self.current, self.message = 0, "", "准备运行"
            self.task = self.ctx.create_task(self._run(mode, source, config, roots, adapter), name="aw115mst-run")
            return {"ok": True, "message": "任务已开始"}

    async def stop(self):
        async with self.lock:
            task = self.task
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                self.message = "任务已停止，处理记录已保留"
            return {"ok": True, "message": self.message}

    async def close(self):
        self.closed = True
        await self.stop()

    async def status(self):
        records = await self.store.all()
        counts = {}
        for record in records:
            counts[record["state"]] = counts.get(record["state"], 0) + 1
        try:
            roots = _files.validate_roots(self.ctx.data_dir, normalize(self.ctx.config))
            directories = {key: str(getattr(roots, key)) for key in ("input_dir", "rapid_dir", "non_rapid_dir")}
        except ValueError:
            directories = {}
        return {"ok": True, "running": self.running, "progress": self.progress,
                "current": self.current, "message": self.message, "roots": directories,
                "last_result": self.last_result, "counts": counts,
                "records": [{**{key: item.get(key, "") for key in ("name", "state", "checks", "updated", "message", "path")},
                             "size": item.get("snapshot", {}).get("size", 0)}
                            for item in records[:100]]}

    async def clear(self):
        async with self.lock:
            if self.running:
                return {"ok": False, "message": "运行中不能清空记录"}
            await self.store.clear()
            self.observed.clear()
            return {"ok": True, "message": "处理记录已清空，没有删除任何文件"}

    def _stable(self, path, root, config):
        snap = _files.signature(path, root)
        if config["stable_seconds"] == 0:
            return True
        now = time.monotonic()
        key = str(path)
        previous = self.observed.get(key)
        if previous is None or previous[0] != snap:
            self.observed[key] = (snap, now)
        # Manual scans can use modification time; watch also waits through its own observations.
        return time.time() - snap.mtime_ns / 1e9 >= config["stable_seconds"]

    async def watch(self):
        if self.closed or self.running:
            return
        config = normalize(self.ctx.config)
        roots = _files.validate_roots(self.ctx.data_dir, config)
        paths = await settled(asyncio.to_thread(_files.scan_candidates, roots.input_dir, config))
        now = time.monotonic()
        found = False
        live = set()
        for path in paths:
            key = str(path)
            live.add(key)
            snap = _files.signature(path, roots.input_dir)
            old = self.observed.get(key)
            if not old or old[0] != snap:
                self.observed[key] = (snap, now)
                continue
            if now - old[1] < config["stable_seconds"]:
                continue
            previous = await self.store.get(file_key(path))
            if not previous or previous.get("snapshot") != snap.to_dict():
                # Stored snapshots include sha1, compare filesystem identity separately.
                if not previous or not self._unchanged(previous, snap):
                    found = True
                    break
        self.observed = {key: value for key, value in self.observed.items() if key in live}
        if found:
            await self.start("scan", "目录巡检")

    @staticmethod
    def _unchanged(record, snap):
        before = dict(record.get("snapshot", {}))
        before["sha1"] = ""
        return before == snap.to_dict()

    async def _collect(self, mode, roots, config, watch_only=False):
        jobs = []
        if mode in {"scan", "all"}:
            for path in await settled(asyncio.to_thread(_files.scan_candidates, roots.input_dir, config)):
                try:
                    if not self._stable(path, roots.input_dir, config):
                        continue
                    if watch_only:
                        observed = self.observed.get(str(path))
                        if not observed or time.monotonic() - observed[1] < config["stable_seconds"]:
                            continue
                    snap = _files.signature(path, roots.input_dir)
                    old = await self.store.get(file_key(path))
                    if old and self._unchanged(old, snap):
                        if old["state"] in {"local_pending", "dispatch_pending"}:
                            jobs.append((path, roots.input_dir, old, False))
                        elif old["state"] == "failed":
                            jobs.append((path, roots.input_dir, old, False))
                        continue
                    jobs.append((path, roots.input_dir, old, False))
                except (OSError, ValueError):
                    continue
        seen = {str(job[0]) for job in jobs}
        for record in await self.store.all():
            # A completed move/delete may have removed the processing path while
            # source cleanup still needs retrying. Do not upload or copy it again.
            if record["state"] == "local_pending" and record.get("local_action_done") and record["path"] not in seen:
                root = Path(record["root"])
                if root in {roots.input_dir, roots.non_rapid_dir}:
                    jobs.append((Path(record["path"]), root, record, True))
                    seen.add(record["path"])
            if mode in {"recheck", "all"}:
                if record["state"] not in {"non_rapid", "local_pending", "failed"} or record["path"] in seen:
                    continue
                path, root = Path(record["path"]), Path(record["root"])
                if root not in {roots.input_dir, roots.non_rapid_dir}:
                    continue
                if not path.exists():
                    record.update(state="missing", message="本地文件不存在，未重检")
                    await self.store.put(record)
                    continue
                jobs.append((path, root, record, True))
                seen.add(str(path))
        return jobs

    async def _run(self, mode, source, config, roots, adapter):
        stats = {"total": 0, "rapid": 0, "non_rapid": 0, "uploaded": 0, "failed": 0, "skipped": 0}
        expired = False
        try:
            info = await adapter.login_info()
            if not info.get("ok", info.get("success", info.get("state", False))):
                raise ValueError("115 登录已失效，请重新扫码或同步 Cookie")
            config["_account_id"] = str(info.get("user_id", ""))
            jobs = await self._collect(mode, roots, config, watch_only=source == "目录巡检")
            stats["total"] = len(jobs)
            if jobs or source != "目录巡检":
                self.ctx.log.info("%s：待处理 %s 个文件", source, len(jobs))
            for index, (path, root, record, recheck) in enumerate(jobs):
                self.current = path.name
                try:
                    outcome = await self._process(path, root, record, recheck, roots, config, adapter)
                    stats[outcome] += 1
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    stats["failed"] += 1
                    # Adapter and path exceptions deliberately never include credentials or response bodies.
                    from ._p115 import SessionExpiredError
                    self.ctx.log.warning("%s：处理失败（%s）", path.name, type(exc).__name__)
                    if isinstance(exc, SessionExpiredError):
                        self.message = "115 登录已失效，本轮已停止"
                        expired = True
                        break
                self.progress = int((index + 1) / max(1, len(jobs)) * 100)
            summary = f"完成：秒传 {stats['rapid']}，待秒传 {stats['non_rapid']}，上传 {stats['uploaded']}，失败 {stats['failed']}"
            self.message = ("115 登录已失效，本轮已停止；" if expired else "") + summary
            self.progress = 100
            if jobs or source != "目录巡检":
                self.ctx.log.info(self.message)
            if config["notify"] and (jobs or source != "目录巡检"):
                try:
                    await asyncio.wait_for(self.ctx.notify("AW115MST " + self.message), timeout=30)
                except Exception:
                    self.ctx.log.warning("结果通知发送失败")
        except asyncio.CancelledError:
            self.message = "任务已停止，处理记录已保留"
            raise
        except Exception as exc:
            self.message = str(exc) if isinstance(exc, ValueError) else f"任务失败（{type(exc).__name__}），请检查账号与网络"
            self.ctx.log.warning(self.message)
        finally:
            self.current = ""
            self.last_result = stats
            await settled(adapter.close())

    async def _process(self, path, root, record, recheck, roots, config, adapter):
        if (record and record.get("remote_confirmed") and record.get("remote_account") and
                record["remote_account"] != config.get("_account_id", "")):
            record.update(state="cloud_unknown", message="入库回执属于其他 115 账号，本地文件已保留；请核对后清记录")
            await self.store.put(record)
            return "skipped"
        if record and record["state"] == "local_pending" and record.get("local_action_done"):
            return await self._finish_rapid(record, path, root,
                                           _files.FileSnapshot(**record["snapshot"]), roots, config)
        sha1, snap = await _files.hash_file(path, root, chunk_size=config["hash_chunk_mb"] * 1024 ** 2)
        if record and record.get("sha1") != sha1:
            # Recheck changed files as new contents, without trusting an old cloud receipt.
            record = None
        if record is None:
            record = {"key": file_key(path), "path": str(path), "root": str(root), "name": path.name,
                      "snapshot": snap.to_dict(), "sha1": sha1, "checks": 0, "state": "new",
                      "origin_key": "", "remote_confirmed": False, "message": ""}
        else:
            record["snapshot"] = snap.to_dict()
        if record["state"] in {"done", "dispatched", "cloud_unknown"}:
            await self.store.put(record)
            return "skipped"
        if record["state"] == "local_pending" and record.get("remote_confirmed"):
            return await self._finish_rapid(record, path, root, snap, roots, config)
        if record["state"] == "dispatch_pending":
            await self._dispatch(record, path, root, snap, roots, config)
            return "non_rapid"
        if recheck and config["max_recheck_times"] > 0 and record["checks"] >= config["max_recheck_times"]:
            if not config["upload_enabled"]:
                record["message"] = "已到重检上限，真实上传未开启"
                await self.store.put(record)
                return "skipped"
            full_upload = True
        else:
            full_upload = False
        record.update(state="failed", message="尚未取得秒传检测回执，本地文件已保留")
        await self.store.put(record)
        parts = list(path.relative_to(root).parts[:-1]) if config["keep_structure"] else []
        if ("remote_pid" not in record or record.get("target_pid") != config["target_pid"] or
                record.get("remote_parts") != parts or record.get("remote_account") != config.get("_account_id", "")):
            record["remote_pid"] = await adapter.ensure_remote_path(parts, pid=int(config["target_pid"]))
            record["target_pid"] = config["target_pid"]
            record["remote_parts"] = parts
            record["remote_account"] = config.get("_account_id", "")
        # Validate again immediately before the irreversible cloud operation.
        if snap.size:
            await _files.read_range(path, root, snap, "0-0")
        record.update(state="uploading" if full_upload else "checking", message="等待网盘回执")
        await self.store.put(record)
        try:
            if full_upload:
                result = await adapter.full_upload(path, pid=record["remote_pid"], root=root, expected=snap)
            else:
                result = await adapter.check_rapid_upload(path.name, snap.size, sha1, path,
                                                          pid=record["remote_pid"], root=root, expected=snap)
        except BaseException:
            record.update(state="cloud_unknown", message="网盘请求未取得确定回执，请核对后再清记录；本地文件已保留")
            await settled(self.store.put(record))
            raise
        if full_upload or result.get("can_rapid"):
            if not result.get("success") or not result.get("pickcode"):
                record.update(state="cloud_unknown", message="网盘未返回可核验的入库回执，本地文件已保留")
                await self.store.put(record)
                return "failed"
            record.update(state="local_pending", remote_confirmed=True, pickcode=result["pickcode"],
                          uploaded=full_upload, message="网盘已确认，等待本地处理")
            await self.store.put(record)
            return await self._finish_rapid(record, path, root, snap, roots, config)
        if not result.get("success"):
            record.update(state="failed", message="秒传检测失败；本地文件已保留")
            await self.store.put(record)
            return "failed"
        if recheck:
            record["checks"] += 1
        record.update(state="non_rapid", message="暂不可秒传")
        await self.store.put(record)
        if root == roots.input_dir and not config["check_only"]:
            record["state"] = "dispatch_pending"
            await self.store.put(record)
            await self._dispatch(record, path, root, snap, roots, config)
        return "non_rapid"

    async def _dispatch(self, record, path, root, snap, roots, config):
        target = await _files.safe_transfer(path, root, roots.non_rapid_dir, snap,
                                             use_copy=config["use_copy"], keep_structure=config["keep_structure"])
        child = dict(record)
        child.update(key=file_key(target), path=str(target), root=str(roots.non_rapid_dir), name=target.name,
                     state="non_rapid", message="暂不可秒传，等待重检",
                     snapshot=replace(_files.signature(target, roots.non_rapid_dir), sha1=snap.sha1).to_dict(),
                     origin_key=record["key"], source_snapshot=record["snapshot"], source_path=record["path"])
        record.update(state="dispatched", message="已复制到待秒传目录" if config["use_copy"] else "已移动到待秒传目录")
        await self.store.put_many([child, record])
        self._cancel_point()

    async def _finish_rapid(self, record, path, root, snap, roots, config):
        outcome = "uploaded" if record.get("uploaded") else "rapid"
        delete = config["delete_after_upload"] if record.get("uploaded") else config["delete_after_rapid"]
        try:
            if not record.get("local_action_done"):
                if not config["check_only"]:
                    if delete:
                        await _files.remove_file(path, root, snap)
                    else:
                        target = await _files.safe_transfer(path, root, roots.rapid_dir, snap,
                                                             use_copy=config["use_copy"], keep_structure=config["keep_structure"])
                        record["output_path"] = str(target)
                record["local_action_done"] = True
                await self.store.put(record)
            self._cancel_point()
            if not config["check_only"]:
                if config["delete_source_after_rapid"] and record.get("origin_key"):
                    original = await self.store.get(record["origin_key"])
                    if self._same_origin(record, original) and Path(original["path"]).exists():
                        try:
                            await _files.remove_file(original["path"], roots.input_dir, record["source_snapshot"])
                        except _files.FileChangedError:
                            self.ctx.log.warning("%s：输入源文件已改变，保留新文件", record["name"])
            record.update(state="done", message="上传成功" if record.get("uploaded") else "秒传成功")
            updates = [record]
            if record.get("origin_key"):
                original = await self.store.get(record["origin_key"])
                if self._same_origin(record, original):
                    original.update(state="done", message=record["message"])
                    updates.append(original)
            await self.store.put_many(updates)
            self._cancel_point()
            self.ctx.log.info("%s：%s", path.name, record["message"])
            return outcome
        except Exception:
            record.update(state="local_pending", message="网盘已确认，本地处理失败；下次只重试本地处理")
            await self.store.put(record)
            raise

    @staticmethod
    def _same_origin(record, original):
        return bool(original and original.get("sha1") == record.get("sha1") and
                    original.get("snapshot") == record.get("source_snapshot"))
