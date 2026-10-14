import re

from ...core.runtime import get_runtime
from ...enums import DownloadClientEnum
from ...modules.downloadclient.base import BaseDownloader
from ...utils.log import logger


class Thunder(BaseDownloader):
    device_id: str = None
    config: dict = None
    name = DownloadClientEnum.THUNDER.value
    AUTH_STATUS_CODES = {401, 403}

    def __init__(self, conf):
        self.config = conf
        self.device_id = None

    def _parse_json_response(self, response, action: str, **context):
        if response is None or response.status_code >= 400:
            logger.error(self.build_log_context(action, reason='no_response', **context))
            return None

        try:
            return response.json()
        except Exception:
            logger.exception(self.build_log_context(action, reason='invalid_json', **context))
            return None

    @staticmethod
    def _extract_resource_list(payload: dict) -> list:
        if not isinstance(payload, dict):
            return []
        resource_list = (payload.get('list') or {}).get('resources') or []
        return resource_list if isinstance(resource_list, list) else []

    @classmethod
    def _extract_primary_resource(cls, payload: dict):
        resources = cls._extract_resource_list(payload)
        resource = resources[0] if resources else None
        return resource if isinstance(resource, dict) else None

    @staticmethod
    def _extract_device_target(payload: dict):
        if not isinstance(payload, dict):
            return None
        tasks = payload.get('tasks') or []
        if not isinstance(tasks, list):
            return None
        for task in tasks:
            if not isinstance(task, dict):
                continue
            target = (task.get('params') or {}).get('target')
            if target:
                return target
        return None

    @staticmethod
    def _build_headers(pan_auth: str | None, authorization: str | None):
        headers = {}
        if pan_auth:
            headers['pan-auth'] = pan_auth
        if authorization:
            headers['Authorization'] = authorization
        return headers

    @classmethod
    def _is_auth_response(cls, response) -> bool:
        return bool(response is not None and getattr(response, 'status_code', None) in cls.AUTH_STATUS_CODES)

    def _request_with_reauth(self, action: str, method: str, url: str, **kwargs):
        runtime = get_runtime()
        runtime.check_cancelled()
        pan_auth = self.get_pan_auth()
        if not pan_auth:
            logger.error(self.build_log_context(action, url=url, reason='pan_auth_empty'))
            return None

        request_kwargs = dict(kwargs)
        request_kwargs['headers'] = self._build_headers(pan_auth, self.config.get('authorization'))
        response = runtime.request(method, url, use_proxy=False, timeout=20, **request_kwargs)
        if self._is_auth_response(response):
            logger.warning(self.build_log_context(action, url=url, retry='reauth', reason='auth_session'))
            pan_auth = self.get_pan_auth()
            if not pan_auth:
                logger.error(self.build_log_context(action, url=url, reason='refreshed_pan_auth_empty'))
                return response
            request_kwargs['headers'] = self._build_headers(pan_auth, self.config.get('authorization'))
            response = runtime.request(method, url, use_proxy=False, timeout=20, **request_kwargs)
        return response

    def _ensure_device_id(self, force=False):
        if force or not self.device_id:
            self.device_id = self.get_device_id()
        return bool(self.device_id)

    def get_pan_auth(self):
        base_url = (self.config.get('url') or '').rstrip('/')
        if not base_url:
            logger.error(self.build_log_context('get_pan_auth', reason='url_empty'))
            return None

        index_url = f'{base_url}/webman/3rdparty/pan-xunlei-com/index.cgi/'
        try:
            headers = self._build_headers(None, self.config.get('authorization'))
            response = get_runtime().request('GET', index_url, use_proxy=False, timeout=20, headers=headers)
            if response.status_code < 400:
                pattern = r'uiauth\(.*?\)\s*{\s*return\s*"([^"]+)"'
                match = re.search(pattern, response.text)
                if match:
                    return match.group(1)
                logger.error(self.build_log_context('get_pan_auth', url=index_url, reason='pan_auth_not_found'))
            else:
                logger.error(self.build_log_context('get_pan_auth', url=index_url, reason='no_response'))
        except Exception:
            logger.exception(self.build_log_context('get_pan_auth', url=index_url))
        return None

    def get_device_id(self):
        base_url = (self.config.get('url') or '').rstrip('/')
        if not base_url:
            logger.error(self.build_log_context('get_device_id', reason='url_empty'))
            return None

        device_url = f'{base_url}/webman/3rdparty/pan-xunlei-com/index.cgi/drive/v1/tasks?type=user%23runner&device_space='
        try:
            response = self._request_with_reauth('get_device_id', 'GET', device_url)
            data = self._parse_json_response(response, 'get_device_id', url=device_url)
            if not data:
                return None

            if data.get('error'):
                logger.error(self.build_log_context('get_device_id', url=device_url, error=data.get('error')))
                return None

            target = self._extract_device_target(data)
            if target:
                return target

            logger.error(self.build_log_context('get_device_id', url=device_url, reason='missing_target'))
        except Exception:
            logger.exception(self.build_log_context('get_device_id', url=device_url))
        return None

    def analyze_size(self, magnet):
        base_url = (self.config.get('url') or '').rstrip('/')
        if not base_url:
            logger.error(self.build_log_context('analyze_size', magnet=magnet, reason='url_empty'))
            return None

        list_url = f'{base_url}/webman/3rdparty/pan-xunlei-com/index.cgi/drive/v1/resource/list'
        try:
            data = {
                'page_size': 1000,
                'urls': magnet,
            }
            logger.info(self.build_log_context('analyze_size', magnet=magnet, url=list_url))
            response = self._request_with_reauth('analyze_size', 'POST', list_url, json=data)
            payload = self._parse_json_response(response, 'analyze_size', magnet=magnet, url=list_url)
            resource = self._extract_primary_resource(payload)
            if not resource:
                logger.error(self.build_log_context('analyze_size', magnet=magnet, url=list_url, reason='resource_list_empty'))
                return None

            file_size = resource.get('file_size')
            if not isinstance(file_size, (int, float)):
                logger.error(self.build_log_context('analyze_size', magnet=magnet, url=list_url, reason='invalid_file_size'))
                return None
            return int(file_size / 1024 / 1024)
        except Exception:
            logger.exception(self.build_log_context('analyze_size', magnet=magnet, url=list_url))
        return None

    def download(self, magnet, file_id) -> tuple[bool, str | None]:
        get_runtime().require_download()
        base_url = (self.config.get('url') or '').rstrip('/')
        if not base_url:
            logger.error(self.build_log_context('download', magnet=magnet, file_id=file_id, reason='url_empty'))
            return False, '迅雷下载器 URL 未配置'
        if not file_id:
            logger.error(self.build_log_context('download', magnet=magnet, reason='file_id_empty'))
            return False, '保存路径为空'
        if not self._ensure_device_id() and not self._ensure_device_id(force=True):
            logger.error(self.build_log_context('download', magnet=magnet, file_id=file_id, reason='device_id_empty'))
            return False, '无法获取迅雷设备 ID'

        list_url = f'{base_url}/webman/3rdparty/pan-xunlei-com/index.cgi/drive/v1/resource/list'
        try:
            data = {
                'page_size': 1000,
                'urls': magnet,
            }
            logger.info(self.build_log_context('prepare_download', magnet=magnet, file_id=file_id, url=list_url))
            response = self._request_with_reauth('resolve_resource_list', 'POST', list_url, json=data)
            payload = self._parse_json_response(response, 'resolve_resource_list', magnet=magnet, file_id=file_id, url=list_url)
            if not payload:
                return False, '解析资源列表失败'

            resource = self._extract_primary_resource(payload)
            if not resource:
                logger.error(self.build_log_context('resolve_resource_list', magnet=magnet, file_id=file_id, url=list_url, reason='resource_list_empty'))
                return False, '资源列表为空'

            file_name = resource.get('name') or magnet
            directory = resource.get('dir') if isinstance(resource, dict) else None
            resources = directory.get('resources') if isinstance(directory, dict) else None
            resources = resources if isinstance(resources, list) else []
            indexes = []
            file_size = 0

            if resources:
                filtered_resources = []
                for index, current_resource in enumerate(resources):
                    if not isinstance(current_resource, dict):
                        continue
                    current_size = current_resource.get('file_size')
                    if not isinstance(current_size, (int, float)):
                        continue
                    if current_size > 1000000000:
                        indexes.append(str(index))
                        filtered_resources.append(current_resource)

                for current_resource in filtered_resources:
                    current_size = current_resource.get('file_size', 0)
                    logger.info(
                        self.build_log_context(
                            'keep_file',
                            magnet=magnet,
                            file_name=current_resource.get('name', 'unknown'),
                            size_mb=int(current_size / 1024 / 1024),
                        )
                    )
                    file_size += current_size

            if not resources or not indexes:
                resource_size = resource.get('file_size')
                if not isinstance(resource_size, (int, float)):
                    logger.error(self.build_log_context('download', magnet=magnet, file_id=file_id, reason='invalid_primary_file_size'))
                    return False, '迅雷返回了无效的文件大小'
                resources = [resource]
                file_size = resource_size
                indexes = ['0']

            task_url = f'{base_url}/webman/3rdparty/pan-xunlei-com/index.cgi/drive/v1/task'
            task_data = {
                'params': {
                    'parent_folder_id': file_id,
                    'url': magnet,
                    'target': self.device_id,
                    'total_file_count': str(len(resources)),
                    'sub_file_index': ','.join(indexes),
                },
                'file_name': file_name,
                'file_size': str(file_size),
                'name': file_name,
                'type': 'user#download-url',
                'space': self.device_id,
            }
            logger.info(self.build_log_context('create_download_task', magnet=magnet, file_id=file_id, file_name=file_name, url=task_url))
            response = self._request_with_reauth('create_download_task', 'POST', task_url, json=task_data)
            if response is not None and (response.status_code >= 500 or response.status_code == 408):
                raise RuntimeError('迅雷下载提交结果未确认')
            if response is not None and response.status_code < 400:
                payload = response.json()
                if not isinstance(payload, dict):
                    raise RuntimeError('迅雷未返回有效的提交结果')
                if payload.get('error'):
                    return False, '迅雷拒绝了下载请求'
                logger.info(self.build_log_context('create_download_task', magnet=magnet, file_id=file_id, file_name=file_name, result='submitted'))
                return True, None
            logger.error(self.build_log_context('create_download_task', magnet=magnet, file_id=file_id, file_name=file_name, reason='no_response'))
        except Exception as exc:
            raise RuntimeError('迅雷下载提交结果未确认') from exc
        return False, '迅雷下载任务创建失败'
