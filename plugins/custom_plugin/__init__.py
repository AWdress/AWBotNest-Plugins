from __future__ import annotations

import inspect
import traceback


__plugin__ = {
    "name": "插件开发调试",
    "id": "custom_plugin",
    "version": "1.0.1",
    "author": "AWdress",
    "scope": "both",
    "default_enabled": False,
    "description": "在管理员配置页编辑、检查并运行 Python 插件源码，显示运行状态与错误堆栈，适合开发和调试单文件插件。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/custom_plugin.svg",
    "changelog": "v1.0.1 更名为插件开发调试\n- 展示名称调整为“插件开发调试”，更准确体现源码编辑、检查、运行和错误排查用途\n- 保留 custom_plugin 内部 ID，已安装用户可直接更新\n\nv1.0.0 初始版本\n- Vue 配置页内置 Python 源码编辑器与示例模板\n- 保存配置后编译并运行自定义 setup(ctx)\n- 停用或重载时调用自定义 teardown(ctx)\n- 编译或运行失败时保留容器插件，便于直接修正源码\n- 仅管理员配置页可修改，不开放 Telegram 远程写代码",
    "render_mode": "vue",
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
_status = {
    "state": "idle",
    "message": "尚未运行自定义源码",
    "traceback": "",
}


def _validate_source(source: str) -> tuple[object, dict]:
    if not source.strip():
        raise ValueError("源码为空")
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


async def setup(ctx):
    global _runtime_namespace, _runtime_teardown, _status

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(req):
        return {**_status, "template": DEFAULT_SOURCE}

    @ctx.on_api("/validate", methods=["POST"])
    async def api_validate(req):
        body = req.json if isinstance(req.json, dict) else {}
        source = str(body.get("source") or "")
        try:
            _validate_source(source)
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
    try:
        custom_setup, namespace = _validate_source(source)
        await custom_setup(ctx)
        _runtime_namespace = namespace
        _runtime_teardown = namespace.get("teardown")
        _status = {"state": "running", "message": "自定义源码已成功运行", "traceback": ""}
        ctx.log.info("[自定义代码] 自定义 setup(ctx) 已运行")
    except Exception as exc:  # noqa: BLE001
        detail = traceback.format_exc(limit=20)
        _runtime_namespace = None
        _runtime_teardown = None
        _status = {
            "state": "error",
            "message": f"{type(exc).__name__}: {exc}",
            "traceback": detail,
        }
        ctx.log.error("[自定义代码] 源码加载失败：%s\n%s", exc, detail)
        # 不抛出：保留容器与配置界面，让管理员能够直接修正源码。


async def teardown(ctx):
    global _runtime_namespace, _runtime_teardown, _status
    if _runtime_teardown is not None:
        try:
            await _runtime_teardown(ctx)
        except Exception as exc:  # noqa: BLE001
            ctx.log.error("[自定义代码] 自定义 teardown(ctx) 失败：%r", exc)
    _runtime_namespace = None
    _runtime_teardown = None
    _status = {"state": "idle", "message": "自定义源码已停止", "traceback": ""}
