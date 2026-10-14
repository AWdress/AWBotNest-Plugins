"""Owned workers, cancellation and platform transport; no independent bot/server."""
from __future__ import annotations

import asyncio
import contextvars
import inspect
import re
import secrets
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx

_runtime = None
_cancel_scope = contextvars.ContextVar("immortal_cancel_scope", default=None)
MAX_RESPONSE = 8 * 1024 * 1024


class CancelledError(BaseException):
    """Must not be swallowed by the source's general network-error handlers."""


def get_runtime():
    if _runtime is None:
        raise RuntimeError("Immortal 运行环境尚未初始化")
    return _runtime


def bind_runtime(runtime):
    global _runtime
    if runtime is not None and _runtime is not None and _runtime is not runtime:
        raise RuntimeError("不能同时启动多个 Immortal 运行实例")
    _runtime = runtime


def check_cancelled():
    get_runtime().check_cancelled()


def sleep(seconds):
    get_runtime().sleep(seconds)


def require_download():
    get_runtime().require_download()


def safe_error(error):
    text = str(error) or type(error).__name__
    text = re.sub(r"(?i)(authorization|api[_-]?key|token|password|cookie)([=:]\s*)[^\s,;]+", r"\1\2***", text)
    text = re.sub(r"([A-Za-z][A-Za-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@", r"\1***@", text)
    return text[:600]


def result_failure(result):
    """Apply one result contract to live status, task history and notifications."""
    if isinstance(result, (list, tuple)):
        for item in result:
            error = result_failure(item)
            if error:
                return error
    elif isinstance(result, dict):
        if result.get('code', 0) != 0:
            return safe_error(result.get('message') or '业务执行失败')
        if result.get('fail_count', 0) or result.get('failed', 0) or result.get('fail_list'):
            return '任务中有未完成项目，请查看执行记录'
    return None


class Runtime:
    def __init__(self, ctx):
        self.ctx = ctx
        self.loop = asyncio.get_running_loop()
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
        self.jobs = {}
        self.active_keys = set()
        self.tasks = set()
        self.network = set()
        self.queue = deque()
        self.dispatcher = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="immortal-job")
        self.api_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="immortal-api")
        self.api_slots = asyncio.Semaphore(2)
        self.closed = False
        self._stopped = False

    def check_cancelled(self):
        event = _cancel_scope.get()
        if self.stop_event.is_set() or (event is not None and event.is_set()):
            raise CancelledError("任务已停止")

    @property
    def in_job(self):
        return _cancel_scope.get() is not None

    def sleep(self, seconds):
        end = time.monotonic() + max(0, float(seconds))
        while time.monotonic() < end:
            self.check_cancelled()
            self.stop_event.wait(min(0.2, end - time.monotonic()))
        self.check_cancelled()

    def require_download(self):
        self.check_cancelled()
        if self.ctx.config.get("allow_downloads", False) is not True:
            raise ValueError("下载提交已关闭，请先在插件设置中开启并保存")

    def snapshot(self):
        with self.lock:
            return [{k: value for k, value in job.items() if not k.startswith("_")} for job in self.jobs.values()]

    def submit(self, label, callback, *args, task_key=None, **kwargs):
        self.check_cancelled()
        if not callable(callback):
            raise TypeError("任务函数无效")
        with self.lock:
            if self.closed:
                raise CancelledError("插件已停用")
            if task_key is not None and task_key in self.active_keys:
                raise ValueError("任务已在运行或排队，请勿重复执行")
            if sum(job['state'] in {'queued', 'running', 'stopping'} for job in self.jobs.values()) >= 32:
                raise ValueError("等待任务过多，请先等待当前任务完成")
            job_id = secrets.token_hex(8)
            job = {"id": job_id, "label": str(label)[:100], "state": "queued", "error": "",
                   "created": datetime.now(timezone.utc).isoformat(), "_cancel": threading.Event(), "_key": task_key}
            self.jobs[job_id] = job
            self.queue.append((job, callback, args, kwargs))
            if task_key is not None:
                self.active_keys.add(task_key)
            # Retain recent results without retaining callback/credentials.
            for old_id in list(self.jobs):
                if len(self.jobs) <= 100:
                    break
                if self.jobs[old_id]['state'] not in {'queued', 'running', 'stopping'}:
                    del self.jobs[old_id]
        try:
            self.loop.call_soon_threadsafe(self._start)
        except RuntimeError:
            # A closing event loop cannot own any new work.
            self._finish(job, 'cancelled')
            with self.lock:
                self.queue = deque(item for item in self.queue if item[0] is not job)
            raise CancelledError("平台正在关闭") from None
        return {"id": job_id, "label": job['label'], "state": "queued"}

    def _start(self):
        if self.closed:
            self._cancel_queue()
            return
        if self.dispatcher is not None and not self.dispatcher.done():
            return
        with self.lock:
            if not self.queue:
                return
        # Waiting jobs are plain data, not 32 platform tasks competing with
        # status/cancel requests. One owned dispatcher drains them serially.
        coroutine = self._dispatch()
        try:
            task = self.ctx.create_task(coroutine, name="immortal-dispatcher")
        except BaseException:
            coroutine.close()
            self._cancel_queue('failed', "平台未允许创建后台任务")
            return
        self.dispatcher = task
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        task.add_done_callback(self._dispatcher_finished)

    def _dispatcher_finished(self, task):
        if task.cancelled():
            # This also handles cancellation before the coroutine entered its
            # try/finally block.
            self.closed = True
            self.stop_event.set()
            self._cancel_queue()

    def _cancel_queue(self, state='cancelled', error=''):
        with self.lock:
            while self.queue:
                job, *_ = self.queue.popleft()
                self._finish(job, state, error)

    async def _dispatch(self):
        try:
            while not self.closed:
                with self.lock:
                    if not self.queue:
                        return
                    job, callback, args, kwargs = self.queue.popleft()
                await self._execute(job, callback, args, kwargs)
        except asyncio.CancelledError:
            # Cancelling the dispatcher means platform shutdown, not permission
            # to start the next queued callback after the worker drains.
            self.closed = True
            self.stop_event.set()
            raise
        finally:
            if self.closed:
                self._cancel_queue()

    @staticmethod
    async def _drain(future):
        # Repeated cancellation must not release database/client ownership
        # while the native worker can still be using those resources.
        while not future.done():
            try:
                await asyncio.shield(future)
            except asyncio.CancelledError:
                continue
            except BaseException:
                break
        try:
            return future.result()
        except BaseException:
            return None

    def _finish(self, job, state, error=""):
        with self.lock:
            job.update(state=state, error=error, finished=datetime.now(timezone.utc).isoformat())
            self.active_keys.discard(job['_key'])

    async def _execute(self, job, callback, args, kwargs):
        future = None
        try:
            if job['_cancel'].is_set() or self.closed:
                raise CancelledError()
            with self.lock:
                job['state'] = 'running'
            self.ctx.log.info("开始任务：%s", job['label'])

            def worker():
                token = _cancel_scope.set(job['_cancel'])
                try:
                    self.check_cancelled()
                    value = callback(*args, **kwargs)
                    if inspect.isawaitable(value):
                        value = asyncio.run(value)
                    self.check_cancelled()
                    return value
                finally:
                    _cancel_scope.reset(token)

            future = self.loop.run_in_executor(self.executor, worker)
            result = await asyncio.shield(future)
            failure = result_failure(result)
            if failure:
                raise ValueError(failure)
            self._finish(job, 'success')
            self.ctx.log.info("任务完成：%s", job['label'])
        except asyncio.CancelledError:
            job['_cancel'].set()
            if future is not None:
                await self._drain(future)
            self._finish(job, 'cancelled')
            raise
        except CancelledError:
            job['_cancel'].set()
            if future is not None:
                await self._drain(future)
            self._finish(job, 'cancelled')
        except BaseException as error:
            self._finish(job, 'failed', safe_error(error))
            self.ctx.log.warning("任务失败：%s（%s）", job['label'], safe_error(error))

    def cancel(self, job_id=None, task_key=None):
        cancelled = 0
        with self.lock:
            for job in self.jobs.values():
                if job_id and job['id'] != job_id:
                    continue
                if task_key is not None and job['_key'] != task_key:
                    continue
                if job['state'] in {'queued', 'running', 'stopping'}:
                    job['_cancel'].set()
                    job['state'] = 'stopping'
                    cancelled += 1
        return cancelled

    async def api_call(self, callback):
        async with self.api_slots:
            self.check_cancelled()
            context = contextvars.copy_context()
            future = self.loop.run_in_executor(self.api_executor, context.run, callback)
            # Keep owned work visible until it has really exited.
            self.network.add(future)
            future.add_done_callback(self._api_finished)
            return await asyncio.shield(future)

    def _api_finished(self, future):
        self.network.discard(future)
        if not future.cancelled():
            # A caller may have been cancelled while its shielded worker was
            # still exiting; consume the owned future's error in that case.
            future.exception()

    async def _request(self, method, url, use_proxy, timeout, kwargs, proxy=None):
        follow_redirects = kwargs.pop('follow_redirects', True)
        async def read(stream):
            async with stream as response:
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    self.check_cancelled()
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE:
                        raise ValueError("远程响应超过 8 MB 限制")
                return httpx.Response(response.status_code, headers=response.headers,
                                      content=bytes(chunks), request=response.request)
        if use_proxy and proxy is None:
            return await read(self.ctx.http.stream(method, url, timeout=timeout, follow_redirects=follow_redirects, **kwargs))
        async with httpx.AsyncClient(timeout=timeout, proxy=proxy if use_proxy else None,
                                     follow_redirects=follow_redirects, trust_env=False) as client:
            return await read(client.stream(method, url, **kwargs))

    def request(self, method, url, use_proxy=True, **kwargs):
        self.check_cancelled()
        parts = urlsplit(str(url))
        if parts.scheme not in {'http', 'https'} or not parts.hostname:
            raise ValueError("请求地址必须使用 http 或 https")
        try:
            if asyncio.get_running_loop() is self.loop:
                raise RuntimeError("同步网络请求不能在平台事件循环中执行")
        except RuntimeError as error:
            if str(error) != 'no running event loop':
                raise
        raw_timeout = kwargs.pop('timeout', 30)
        if isinstance(raw_timeout, (list, tuple)):
            raw_timeout = max(raw_timeout)
        timeout = min(30, max(1, float(raw_timeout or 30)))
        kwargs.pop('impersonate', None)
        if 'allow_redirects' in kwargs:
            kwargs.setdefault('follow_redirects', kwargs.pop('allow_redirects'))
        if not isinstance(kwargs.get('follow_redirects', True), bool):
            raise ValueError("是否跟随跳转必须是布尔值")
        proxies = kwargs.pop('proxies', None)
        proxy = None
        if isinstance(proxies, dict):
            proxy = proxies.get(parts.scheme) or proxies.get('all')
        kwargs.pop('verify', None)  # Never silently turn off TLS verification.
        future = asyncio.run_coroutine_threadsafe(self._request(method, url, use_proxy, timeout, kwargs, proxy), self.loop)
        try:
            response = future.result(timeout + 5)
            self.check_cancelled()
            return response
        except BaseException:
            future.cancel()
            raise

    def notify(self, message, title=None):
        if self.closed or self.ctx.config.get('notify_results', False) is not True:
            return False
        async def send():
            if self.closed:
                return
            try:
                await self.ctx.notify((str(title) + '\n' if title else '') + str(message))
            except Exception as error:
                self.ctx.log.warning("通知发送失败（%s）", type(error).__name__)
        def start():
            if self.closed:
                return
            coroutine = send()
            try:
                task = self.ctx.create_task(coroutine, name='immortal-notification')
            except Exception:
                coroutine.close()
                self.ctx.log.warning('通知发送失败，平台未允许创建任务')
                return
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        self.loop.call_soon_threadsafe(start)
        return True

    async def stop(self):
        if self._stopped:
            return
        self.closed = True
        self.stop_event.set()
        self.cancel()
        self._cancel_queue()
        # Synchronous integrations use bounded requests and cooperative loops.
        pending = list(self.tasks) + list(self.network)
        if pending:
            await self._drain(asyncio.gather(*pending, return_exceptions=True))
        # Never block the platform event loop waiting for a native thread.
        await asyncio.to_thread(self.executor.shutdown, wait=True, cancel_futures=True)
        await asyncio.to_thread(self.api_executor.shutdown, wait=True, cancel_futures=True)
        self._stopped = True
