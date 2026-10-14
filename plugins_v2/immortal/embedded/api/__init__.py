"""Private in-memory ASGI router; no lifespan, server, CORS or public mount."""
from importlib import import_module
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from ...runtime import safe_error

ROUTERS = [('article', 'articles'), ('config', 'config'), ('task', 'tasks'),
           ('download_log', 'download-log'), ('rule', 'rules'), ('log', 'logs'),
           ('rank', 'rank'), ('movie', 'movies'), ('cast', 'casts'),
           ('filter', 'filters'), ('priority', 'priorities'), ('subscribe', 'subscribes')]


def build_app():
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    # Never silently omit a router on import failure.
    for module, prefix in ROUTERS:
        router = import_module('.v1.' + module, __package__).router
        app.include_router(router, prefix='/api/v1/' + prefix)

    @app.exception_handler(Exception)
    async def error_handler(request, error):
        return JSONResponse({'code': 1, 'message': safe_error(error), 'data': None}, status_code=500)

    return app
