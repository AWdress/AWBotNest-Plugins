from __future__ import annotations

import ast
import inspect
import json
import traceback


__plugin__ = {
    "name": "插件开发调试",
    "id": "custom_plugin",
    "version": "1.0.2",
    "author": "AWdress",
    "scope": "both",
    "default_enabled": False,
    "description": "在管理员配置页编辑、检查并运行 Python 插件源码，显示运行状态与错误堆栈，适合开发和调试单文件插件。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/custom_plugin.svg",
    "changelog": "v1.0.2 修复调试生命周期缺陷\n- 源码检查改用 AST 静态分析，不再执行顶层代码导致保存时重复副作用\n- 关闭运行开关时允许保存尚未完成或存在语法错误的草稿\n- 自定义 setup 完整成功前暂存消息、编辑、回调、API、Webhook、定时任务与清理注册\n- setup 失败时执行自定义清理并丢弃暂存注册，避免半成品监听器继续运行\n- 定时任务返回延迟绑定代理，兼容源码保存任务对象并读取运行状态\n- 按源码 __plugin__.scope 保持 user、bot、both 默认监听范围\n- 新增独立 JSON 运行配置并合并 config_schema 默认值，支持 ctx.config 与 ctx.update_config\n- 保留 /status 与 /validate 调试接口，防止自定义 API 覆盖后配置页失效\n\nv1.0.1 更名为插件开发调试\n- 展示名称调整为“插件开发调试”，更准确体现源码编辑、检查、运行和错误排查用途\n- 保留 custom_plugin 内部 ID，已安装用户可直接更新\n\nv1.0.0 初始版本\n- Vue 配置页内置 Python 源码编辑器与示例模板\n- 保存配置后编译并运行自定义 setup(ctx)\n- 停用或重载时调用自定义 teardown(ctx)\n- 编译或运行失败时保留容器插件，便于直接修正源码\n- 仅管理员配置页可修改，不开放 Telegram 远程写代码",
    "render_mode": "vue",
    "webhook": True,
}


DEFAULT_SOURCE = '''from __future__ import annotations


async def setup(ctx):
    """在这里注册你的消息监听、定时任务或 API。"""

    @ctx.on_message(ctx.filters.incoming & ctx.filters.text, group=10)
    async def hello(client, message):
        if (message.text or "").strip() == "/hello":
            await message.reply("Hello from 插件开发调试 👋")


async def teardown(ctx):
    """可选：释放自定义资源。平台会自动注销通过 ctx 注册的处理器。"""
    pass
'''

_runtime_namespace: dict | None = None
_runtime_teardown = None
_runtime_context = None
_status = {
    "state": "idle",
    "message": "尚未运行自定义源码",
    "traceback": "",
}


def _inspect_source(source: str) -> None:
    """只做静态检查，绝不执行用户源码。"""
    if not source.strip():
        raise ValueError("源码为空")
    tree = ast.parse(source, filename="<custom_plugin_source>", mode="exec")
    funcs = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    custom_setup = funcs.get("setup")
    if not isinstance(custom_setup, ast.AsyncFunctionDef):
        raise TypeError("源码必须定义顶层 async def setup(ctx)")
    custom_teardown = funcs.get("teardown")
    if custom_teardown is not None and not isinstance(custom_teardown, ast.AsyncFunctionDef):
        raise TypeError("teardown 如存在，必须是顶层 async def teardown(ctx)")
    compile(tree, "<custom_plugin_source>", "exec")


def _execute_source(source: str) -> tuple[object, dict]:
    _inspect_source(source)
    code = compile(source, "<custom_plugin_source>", "exec")
    namespace = {
        "__name__": "awbotnest_custom_plugin",
        "__file__": "<custom_plugin_source>",
        "__package__": None,
    }
    exec(code, namespace, namespace)  # noqa: S102 - 此插件的明确用途就是执行管理员源码
    custom_setup = namespace.get("setup")
    if not callable(custom_setup) or not inspect.iscoroutinefunction(custom_setup):
        raise TypeError("源码必须定义 async def setup(ctx)")
    custom_teardown = namespace.get("teardown")
    if custom_teardown is not None and (
        not callable(custom_teardown) or not inspect.iscoroutinefunction(custom_teardown)
    ):
        raise TypeError("teardown 如存在，必须是 async def teardown(ctx)")
    return custom_setup, namespace


class _DeferredJob:
    """setup 暂存期间占位，提交后透明代理到 APScheduler Job。"""

    def __init__(self):
        self._job = None

    def bind(self, job) -> None:
        self._job = job

    def __getattr__(self, name):
        if self._job is None:
            raise RuntimeError("定时任务尚未提交，请在 setup(ctx) 完成后读取任务属性")
        return getattr(self._job, name)


class _StagedContext:
    """在自定义 setup 成功前暂存会改变平台注册状态的操作。"""

    def __init__(self, real_ctx, source_scope: str = "user", custom_config: dict | None = None):
        self._real = real_ctx
        self._source_scope = source_scope if source_scope in {"user", "bot", "both"} else "user"
        self._custom_config = dict(custom_config or {})
        self._staged: list[tuple[str, tuple, dict, object]] = []
        self._cleanups: list[object] = []
        self._committed = False

    def __getattr__(self, name):
        return getattr(self._real, name)

    @property
    def config(self) -> dict:
        return dict(self._custom_config)

    def update_config(self, patch: dict) -> dict:
        if not isinstance(patch, dict):
            raise TypeError("update_config 需要 dict")
        self._custom_config.update(patch)
        self._real.update_config({
            "custom_config": json.dumps(self._custom_config, ensure_ascii=False, indent=2),
        })
        return dict(self._custom_config)

    def _make_decorator(self, name: str, *args, **kwargs):
        if name in {"on_message", "on_edited_message", "on_callback"}:
            args = list(args)
            if len(args) >= 3 and args[2] == "auto":
                args[2] = self._source_scope
            elif len(args) < 3 and kwargs.get("target", "auto") == "auto":
                kwargs = {**kwargs, "target": self._source_scope}
            args = tuple(args)
        if self._committed:
            return getattr(self._real, name)(*args, **kwargs)

        def decorator(func):
            self._staged.append((name, args, kwargs, func))
            return func
        return decorator

    def on_message(self, *args, **kwargs):
        return self._make_decorator("on_message", *args, **kwargs)

    def on_edited_message(self, *args, **kwargs):
        return self._make_decorator("on_edited_message", *args, **kwargs)

    def on_callback(self, *args, **kwargs):
        return self._make_decorator("on_callback", *args, **kwargs)

    def action(self, *args, **kwargs):
        return self._make_decorator("action", *args, **kwargs)

    def on_api(self, *args, **kwargs):
        path = str(args[0] if args else kwargs.get("path", "")).strip().strip("/")
        if path in {"status", "validate"}:
            raise ValueError(f"自定义 API 路径 /{path} 为调试器保留端点，请更换路径")
        return self._make_decorator("on_api", *args, **kwargs)

    def on_webhook(self, func):
        if self._committed:
            return self._real.on_webhook(func)
        self._staged.append(("on_webhook", (), {}, func))
        return func

    def schedule(self, func, trigger="interval", **trigger_args):
        if self._committed:
            return self._real.schedule(func, trigger=trigger, **trigger_args)
        deferred = _DeferredJob()
        self._staged.append(("schedule", (func,), {"trigger": trigger, **trigger_args}, deferred))
        return deferred

    def add_cleanup(self, fn):
        if self._committed:
            return self._real.add_cleanup(fn)
        self._cleanups.append(fn)
        return None

    def commit(self) -> None:
        for name, args, kwargs, func in self._staged:
            if name == "schedule":
                func.bind(self._real.schedule(*args, **kwargs))
            elif name == "on_webhook":
                self._real.on_webhook(func)
            else:
                getattr(self._real, name)(*args, **kwargs)(func)
        for fn in self._cleanups:
            self._real.add_cleanup(fn)
        self._staged.clear()
        self._cleanups.clear()
        self._committed = True

    async def rollback(self) -> None:
        for fn in reversed(self._cleanups):
            try:
                result = fn()
                if inspect.isawaitable(result):
                    await result
            except Exception:  # noqa: BLE001
                pass
        self._staged.clear()
        self._cleanups.clear()


def _source_scope(namespace: dict) -> str:
    meta = namespace.get("__plugin__")
    scope = str(meta.get("scope", "user")) if isinstance(meta, dict) else "user"
    if scope not in {"user", "bot", "both"}:
        raise ValueError("__plugin__.scope 只支持 user、bot 或 both")
    return scope


def _custom_config(namespace: dict, raw_config) -> dict:
    meta = namespace.get("__plugin__")
    schema = meta.get("config_schema", {}) if isinstance(meta, dict) else {}
    defaults = {
        key: field.get("default")
        for key, field in schema.items()
        if isinstance(field, dict) and "default" in field
    } if isinstance(schema, dict) else {}
    if isinstance(raw_config, dict):
        saved = raw_config
    else:
        text = str(raw_config or "").strip() or "{}"
        saved = json.loads(text)
    if not isinstance(saved, dict):
        raise ValueError("自定义运行配置必须是 JSON 对象")
    return {**defaults, **saved}


async def setup(ctx):
    global _runtime_namespace, _runtime_teardown, _runtime_context, _status

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(req):
        return {**_status, "template": DEFAULT_SOURCE}

    @ctx.on_api("/validate", methods=["POST"])
    async def api_validate(req):
        body = req.json if isinstance(req.json, dict) else {}
        source = str(body.get("source") or "")
        try:
            _inspect_source(source)
            raw_config = body.get("custom_config", "{}")
            if isinstance(raw_config, str):
                parsed = json.loads(raw_config.strip() or "{}")
                if not isinstance(parsed, dict):
                    raise ValueError("自定义运行配置必须是 JSON 对象")
            return {"ok": True, "message": "语法和入口检查通过"}
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "message": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=8),
            }

    cfg = dict(ctx.config or {})
    if not cfg.get("code_enabled", False):
        _status = {"state": "disabled", "message": "自定义源码运行开关未开启", "traceback": ""}
        ctx.log.info("[自定义代码] 容器已加载，自定义源码未启用")
        return

    source = str(cfg.get("source") or "")
    staged_ctx = None
    namespace = None
    try:
        custom_setup, namespace = _execute_source(source)
        staged_ctx = _StagedContext(
            ctx,
            source_scope=_source_scope(namespace),
            custom_config=_custom_config(namespace, cfg.get("custom_config", "{}")),
        )
        await custom_setup(staged_ctx)
        staged_ctx.commit()
        _runtime_namespace = namespace
        _runtime_teardown = namespace.get("teardown")
        _runtime_context = staged_ctx
        _status = {"state": "running", "message": "自定义源码已成功运行", "traceback": ""}
        ctx.log.info("[自定义代码] 自定义 setup(ctx) 已运行")
    except Exception as exc:  # noqa: BLE001
        detail = traceback.format_exc(limit=20)
        custom_teardown = namespace.get("teardown") if namespace else None
        if custom_teardown is not None:
            try:
                await custom_teardown(staged_ctx or ctx)
            except Exception:  # noqa: BLE001
                detail += "\n清理失败：\n" + traceback.format_exc(limit=10)
        if staged_ctx is not None:
            await staged_ctx.rollback()
        _runtime_namespace = None
        _runtime_teardown = None
        _runtime_context = None
        _status = {
            "state": "error",
            "message": f"{type(exc).__name__}: {exc}",
            "traceback": detail,
        }
        ctx.log.error("[自定义代码] 源码加载失败：%s\n%s", exc, detail)
        # 不抛出：保留容器与配置界面，让管理员能够直接修正源码。


async def teardown(ctx):
    global _runtime_namespace, _runtime_teardown, _runtime_context, _status
    if _runtime_teardown is not None:
        try:
            await _runtime_teardown(_runtime_context or ctx)
        except Exception as exc:  # noqa: BLE001
            ctx.log.error("[自定义代码] 自定义 teardown(ctx) 失败：%r", exc)
    _runtime_namespace = None
    _runtime_teardown = None
    _runtime_context = None
    _status = {"state": "idle", "message": "自定义源码已停止", "traceback": ""}
