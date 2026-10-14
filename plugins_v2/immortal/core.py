"""Platform lifecycle and bounded private administrator bridge."""
from __future__ import annotations
import asyncio
import base64
import binascii
import json
import re
import sys
import threading
from concurrent.futures import Future
from urllib.parse import urlsplit
import httpx
from starlette.responses import JSONResponse
from .runtime import MAX_RESPONSE, Runtime, bind_runtime, safe_error

DEFAULTS = {'auto_tasks': False, 'allow_downloads': False, 'notify_results': False, 'database_url': ''}
MAX_UPLOAD = 6 * 1024 * 1024
PATH = re.compile(r'^/api/v1/(articles|config|tasks|download-log|rules|logs|rank|movies|casts|filters|priorities|subscribes)(?:/[A-Za-z0-9_.-]+)*/?$')


def validate_config(config):
    result = {key: config.get(key, value) for key, value in DEFAULTS.items()}
    for key in ('auto_tasks', 'allow_downloads', 'notify_results'):
        if not isinstance(result[key], bool):
            raise ValueError('开关配置必须是布尔值')
    if not isinstance(result['database_url'], str):
        raise ValueError('数据库地址格式无效')
    value = result['database_url'].strip()
    if value and urlsplit(value).scheme not in {'postgresql', 'postgresql+psycopg2'}:
        raise ValueError('外部数据库只接受 PostgreSQL 地址；留空使用内置 SQLite')
    result['database_url'] = value
    return result


def normalize_request(payload):
    if not isinstance(payload, dict):
        raise ValueError('请求内容必须是对象')
    method, path = payload.get('method', 'GET'), payload.get('path')
    if method not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'} or not isinstance(path, str):
        raise ValueError('请求方法或路径无效')
    if len(path) > 300 or not PATH.fullmatch(path) or any(s in {'.', '..'} for s in path.split('/')):
        raise ValueError('不允许访问此接口')
    if path.rstrip('/') == '/api/v1/tasks/browse-dirs':
        raise ValueError('内置插件不开放服务器目录浏览')
    query = payload.get('query') or {}
    if not isinstance(query, dict) or len(query) > 30 or len(json.dumps(query, ensure_ascii=False)) > 20000:
        raise ValueError('查询参数格式无效或过长')
    body, raw, content_type = payload.get('body'), None, None
    if isinstance(body, dict):
        for key in ('page_size', 'limit'):
            if key in body and (isinstance(body[key], bool) or not isinstance(body[key], int) or not 1 <= body[key] <= 500):
                raise ValueError('每页或每次数量应为 1～500')
    if 'body_base64' in payload:
        if body is not None or method not in {'POST', 'PUT'}:
            raise ValueError('文件请求格式无效')
        encoded = payload['body_base64']
        if not isinstance(encoded, str) or len(encoded) > (MAX_UPLOAD + 2) // 3 * 4:
            raise ValueError('上传文件不能超过 6 MB')
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError('上传文件编码无效') from None
        content_type = payload.get('content_type')
        if not isinstance(content_type, str) or len(content_type) > 200 or '\r' in content_type or '\n' in content_type:
            raise ValueError('文件格式无效')
        if path != '/api/v1/articles/import/excel' or not content_type.startswith('multipart/form-data; boundary='):
            raise ValueError('二进制上传仅支持资源表格导入')
    elif len(json.dumps(body, ensure_ascii=False)) > 2 * 1024 * 1024:
        raise ValueError('请求数据过大')
    return method, path, query, body, raw, content_type


class Service:
    def __init__(self, ctx):
        self.ctx = ctx
        self.config = validate_config(ctx.config)
        self.runtime = Runtime(ctx)
        self.runtime.reschedule = self.reschedule
        self.app = self.database = None
        self.stopped = False
        self.schedule_lock = threading.Lock()
        self.schedule_generation = 0

    async def setup(self):
        bind_runtime(self.runtime)
        await self.runtime.api_call(self._initialize)
        self.ctx.on_api('request', self.request_api, methods=['POST'])
        self.ctx.on_api('status', self.status_api, methods=['GET'])
        self.ctx.on_api('cancel', self.cancel_api, methods=['POST'])
        await self.runtime.api_call(self.reschedule)
        self.ctx.log.info('Immortal 已就绪，自动任务%s，下载提交%s', '开启' if self.config['auto_tasks'] else '关闭', '开启' if self.config['allow_downloads'] else '关闭')

    def _initialize(self):
        from .embedded.core import config, database
        config.configure(self.ctx.data_dir)
        database.configure(self.ctx.data_dir, self.config['database_url'])
        self.database = database
        from .embedded import models
        database.Base.metadata.create_all(bind=database.get_engine())
        from .embedded.models.config import Config
        from .embedded.enums import DownloadClientEnum, MediaServerEnum
        from .embedded.modules.downloadclient.manager import downloadManager
        from .embedded.modules.mediaserver.manager import mediaServerManager
        with database.session_scope() as db:
            for record in db.query(Config).all():
                if record.key == 'SystemConfig':
                    config.config_manager.reload(json.loads(record.content))
                elif record.key in {item.value for item in DownloadClientEnum}:
                    downloadManager.reload(record.key, json.loads(record.content))
                elif record.key in {item.value for item in MediaServerEnum}:
                    mediaServerManager.reload(record.key, json.loads(record.content))
        from .embedded.api import build_app
        self.app = build_app()

    def reschedule(self):
        if self.stopped:
            return
        with self.schedule_lock:
            self.schedule_generation += 1
            generation = self.schedule_generation
            records = []
            if self.database is not None and self.ctx.config.get('auto_tasks', False):
                from .embedded.models.task import Task
                with self.database.session_scope() as db:
                    tasks = db.query(Task).filter(Task.enable.is_(True)).order_by(Task.id).all()
                    if len(tasks) > 64:
                        raise ValueError('最多启用 64 个定时任务，请先停用部分任务')
                    records = [(task.id, task.task_name, task.task_cron) for task in tasks]
        completed = Future()
        def apply():
            try:
                if self.stopped or generation != self.schedule_generation:
                    completed.set_result(None)
                    return
                from apscheduler.triggers.cron import CronTrigger
                prepared = [(task_id, name, CronTrigger.from_crontab(cron, timezone='Asia/Shanghai')) for task_id, name, cron in records]
                self.ctx.scheduler.remove_plugin(self.ctx.instance_id)
                for task_id, name, trigger in prepared:
                    async def run(task_id=task_id):
                        def launch():
                            from .embedded.api.services.task_service import run_task
                            with self.database.session_scope() as db:
                                return run_task(db, task_id)
                        return await self.runtime.api_call(launch)
                    self.ctx.schedule(run, trigger=trigger, id=f'Immortal {task_id}：{name}')
                completed.set_result(None)
            except BaseException as error:
                completed.set_exception(error)
        try:
            on_loop = asyncio.get_running_loop() is self.runtime.loop
        except RuntimeError:
            on_loop = False
        if on_loop:
            apply()
            return completed.result()
        self.runtime.loop.call_soon_threadsafe(apply)
        return completed.result(timeout=10)

    async def request_api(self, request):
        if self.stopped:
            return JSONResponse({'message': '插件已停用'}, status_code=503)
        try:
            if len(request.body) > 10 * 1024 * 1024:
                raise ValueError('请求内容超过限制')
            params = normalize_request(request.json)
        except (TypeError, ValueError) as error:
            return JSONResponse({'message': str(error)}, status_code=400)
        try:
            return await self.runtime.api_call(lambda: asyncio.run(self._dispatch(params)))
        except Exception as error:
            self.ctx.log.warning('管理请求失败（%s）', type(error).__name__)
            return {'status': 500, 'headers': {'content-type': 'application/json'}, 'body': {'code': 1, 'message': safe_error(error), 'data': None}}

    async def _dispatch(self, params):
        from .embedded.api.deps import bridge_authorized
        method, path, query, body, raw, content_type = params
        token = bridge_authorized.set(True)
        try:
            transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url='http://immortal.internal', follow_redirects=True) as client:
                kwargs = {'params': query}
                if raw is not None:
                    kwargs.update(content=raw, headers={'content-type': content_type})
                elif body is not None:
                    kwargs['json'] = body
                response = await client.request(method, path, **kwargs)
            if len(response.content) > MAX_RESPONSE:
                return {'status': 413, 'headers': {'content-type': 'application/json'}, 'body': {'code': 1, 'message': '导出数据超过 8 MB，请缩小导出范围', 'data': None}}
            result = {'status': response.status_code, 'headers': {key: value for key, value in response.headers.items() if key in {'content-type', 'content-disposition'}}}
            if 'application/json' in response.headers.get('content-type', ''):
                result['body'] = response.json()
            else:
                result['body_base64'] = base64.b64encode(response.content).decode('ascii')
            return result
        finally:
            bridge_authorized.reset(token)

    def _counts(self):
        from sqlalchemy import func
        from .embedded.models import Article, Movie, Cast, Subscribe
        with self.database.session_scope() as db:
            return {key: db.query(func.count(model.id)).scalar() for key, model in [('articles', Article), ('movies', Movie), ('casts', Cast), ('subscriptions', Subscribe)]}

    async def status_api(self, request):
        jobs = self.runtime.snapshot()
        return {'ok': True, 'version': '0.0.1', 'database': self.database.get_engine().dialect.name,
                'auto_tasks': self.ctx.config.get('auto_tasks', False), 'allow_downloads': self.ctx.config.get('allow_downloads', False),
                'notify_results': self.ctx.config.get('notify_results', False),
                'running': [job for job in jobs if job['state'] in {'queued', 'running', 'stopping'}],
                'jobs': jobs, 'counts': await self.runtime.api_call(self._counts)}

    async def cancel_api(self, request):
        payload = request.json
        if not isinstance(payload, dict) or (payload.get('id') is not None and not isinstance(payload['id'], str)):
            return JSONResponse({'ok': False, 'message': '停止任务参数无效'}, status_code=400)
        if not payload.get('id') and payload.get('all') is not True:
            return JSONResponse({'ok': False, 'message': '请指定任务，或确认停止全部任务'}, status_code=400)
        count = self.runtime.cancel(job_id=payload.get('id'))
        return {'ok': True, 'message': f'已请求停止 {count} 个任务；正在提交的远程请求会等待结果后退出'}

    async def stop(self):
        if self.stopped:
            return
        self.stopped = True
        try:
            await self.runtime.stop()
            # Failed setup must not import additional source while unwinding.
            for module_name, manager_name in [('downloadclient', 'downloadManager'), ('mediaserver', 'mediaServerManager')]:
                module = sys.modules.get(__package__ + '.embedded.modules.' + module_name + '.manager')
                if module is not None:
                    try:
                        getattr(module, manager_name).close()
                    except Exception as error:
                        self.ctx.log.warning('关闭组件失败（%s）', type(error).__name__)
        finally:
            try:
                if self.database is not None:
                    self.database.close()
            finally:
                bind_runtime(None)
