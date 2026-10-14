from ..api.services.article_service import import_excel
from ..core.database import session_scope
from ..utils import safe_get, logger
from ..utils.wrapper import task_monitor_async


class AsyncFileWrapper:
    def __init__(self, content: bytes, filename: str):
        self._content = content
        self.filename = filename

    async def read(self):
        return self._content


@task_monitor_async
async def sync_article(url, token):
    logger.info('开始执行远程资源库同步')
    headers = {
        'X-API-KEY': token
    }
    res = safe_get(url, headers=headers, timeout=600)
    if res is not None and 200 <= res.status_code < 300:
        logger.info('远程文件下载完成，开始导入资源库数据')
        filename = 'temp.csv'
        file_obj = AsyncFileWrapper(res.content, filename)
        with session_scope() as session:
            result = await import_excel(file_obj, session)
            if isinstance(result, dict) and result.get('code', 0) == 0:
                logger.info('远程资源库同步完成')
            return result

    status = f'（HTTP {res.status_code}）' if res is not None else ''
    raise RuntimeError(f'远程资源库文件下载失败{status}')
