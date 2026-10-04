"""Telegram / 企业微信消息入口和经过设备密钥鉴权的主动领取接口。"""
from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import urlsplit

from starlette.responses import FileResponse, JSONResponse, PlainTextResponse

from . import __plugin__
from .channels import PlatformChannels
from .files import inspect_file, safe_name
from .ipp import IPPPrinter, IPPRejected, IPPSubmissionUnknown
from .queue import LABELS, PrintQueue
from .wecom import WeCom


def members(value):
    return set(re.split(r"[\s,，;；]+", str(value or "").strip())) - {""}


OBSOLETE_CHANNEL_FIELDS = {
    "telegram_enabled", "wecom_enabled", "wecom_corp_id", "wecom_agent_id",
    "wecom_secret", "wecom_token", "wecom_encoding_aes_key",
}


class RemotePrint:
    def __init__(self, ctx):
        self.ctx = ctx
        self.queue = PrintQueue(ctx, self.config)
        self.channels = PlatformChannels(ctx)
        self.callback_keys = {}
        self.callback_lock = asyncio.Lock()
        self.wecom = WeCom(ctx, self.wecom_config)
        self.ipp = IPPPrinter(ctx, self.config)
        self.ipp_status = {}
        self.dispatch_lock = asyncio.Lock()
        self.downloads = asyncio.Semaphore(2)
        self.receiving = 0
        self.stopped = False
        self.telegram_binding = None
        self.telegram_handlers = []
        self.telegram_connection_issue = ""

    def config(self):
        cfg = {key: copy.deepcopy(field["default"]) for key, field in __plugin__["config_schema"].items() if "default" in field and field["type"] != "info"}
        cfg.update({key: value for key, value in dict(self.ctx.config).items() if key in cfg})
        for key, limits in {"default_copies": (1, 5), "max_copies": (1, 5), "max_pages": (1, 50), "max_file_mb": (1, 25),
                            "max_queue": (1, 100), "max_storage_mb": (25, 1000), "retention_hours": (1, 168), "ipp_timeout_seconds": (5, 120)}.items():
            try:
                number = int(cfg[key])
            except (ValueError, TypeError, OverflowError):
                number = __plugin__["config_schema"][key]["default"]
            cfg[key] = max(limits[0], min(limits[1], number))
        for key in ("enabled", "auto_print"):
            cfg[key] = cfg[key] is True
        for key in ("device_id", "device_token", "printer_name", "public_base_url", "ipp_url", "ipp_printer_uri"):
            cfg[key] = str(cfg[key] or "").strip()
        if cfg["print_mode"] not in {"ipp", "agent"}:
            cfg["print_mode"] = "ipp"
        return cfg

    def remove_obsolete_channel_config(self):
        # Only this plugin's former channel fields are removed. Platform channel
        # settings are never changed or copied into plugin configuration.
        settings = getattr(self.ctx, "settings", None)
        configs = getattr(settings, "plugin_config", None)
        if not isinstance(configs, dict):
            return
        current = configs.get("remote_print", {})
        if not isinstance(current, dict) or not OBSOLETE_CHANNEL_FIELDS.intersection(current):
            return
        configs["remote_print"] = {key: value for key, value in current.items() if key not in OBSOLETE_CHANNEL_FIELDS}
        try:
            self.ctx.update_config({})
        except BaseException:
            configs["remote_print"] = current
            raise

    @staticmethod
    def wecom_identity(config):
        return hashlib.sha256("\0".join(str(config.get(key) or "") for key in
            ("wecom_channel_id", "wecom_corp_id", "wecom_agent_id")).encode("utf-8")).hexdigest()

    def wecom_config(self):
        config = self.channels.wecom_config()
        if not config:
            raise ValueError("请先在平台配置企业微信自建应用；群机器人不能接收文件")
        supplied = (config.get("wecom_token"), config.get("wecom_encoding_aes_key"))
        if any(supplied):
            if not all(supplied):
                raise ValueError("平台企业微信回调密钥不完整，请检查平台渠道配置")
            return config
        keys = self.callback_keys.get(self.wecom_identity(config))
        if not isinstance(keys, dict):
            raise ValueError("请先点击“查看企业微信接收配置”，生成回调密钥")
        if (not re.fullmatch(r"[A-Za-z0-9]{32}", str(keys.get("token") or ""))
                or not re.fullmatch(r"[A-Za-z0-9+/]{43}", str(keys.get("aes_key") or ""))):
            raise ValueError("企业微信回调密钥记录损坏，请先备份并检查插件数据")
        return {**config, "wecom_token": keys["token"], "wecom_encoding_aes_key": keys["aes_key"]}

    async def show_wecom_setup(self, payload=None):
        try:
            async with self.callback_lock:
                # A cancelled storage write may already have committed. Re-read
                # before generation so a later action never replaces that pair.
                stored = await self.ctx.storage.get("wecom_callback_keys_v1", {})
                if not isinstance(stored, dict):
                    raise ValueError("企业微信回调密钥记录损坏，请先备份并检查插件数据")
                self.callback_keys = stored
                config = self.channels.wecom_config()
                if not config:
                    raise ValueError("请先在平台配置企业微信自建应用；群机器人不能接收文件")
                identity = self.wecom_identity(config)
                if not (config.get("wecom_token") or config.get("wecom_encoding_aes_key")) and identity not in self.callback_keys:
                    keys = {"token": secrets.token_hex(16), "aes_key": base64.b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")}
                    snapshot = {**self.callback_keys, identity: keys}
                    await self.ctx.storage.set("wecom_callback_keys_v1", snapshot)
                    self.callback_keys = snapshot
                config = self.wecom_config()
                return {"ok": True, "message": (
                    f"平台企业微信应用：{config.get('wecom_channel_name') or config['wecom_channel_id']}\n"
                    + self.urls() + "\n\n请将以下两项复制到企业微信后台的“接收消息”配置；重载插件不会更换密钥。"
                    + f"\nToken：{config['wecom_token']}\nEncodingAESKey：{config['wecom_encoding_aes_key']}"
                    + "\n不要分享这些密钥。插件不会修改平台的企业微信配置。")}
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}

    async def setup(self):
        self.remove_obsolete_channel_config()
        await self.queue.open()
        self.callback_keys = await self.ctx.storage.get("wecom_callback_keys_v1", {})
        if not isinstance(self.callback_keys, dict):
            raise ValueError("企业微信回调密钥记录损坏，请先备份并检查插件数据")
        self.ctx.on_webhook("wecom", self.wecom_callback)
        self.ctx.on_webhook("agent", self.agent)
        self.ctx.on_webhook("agent_file", self.agent_file)
        self.ctx.on_api("status", self.admin_status)
        self.ctx.action("show_connection", self.show_connection)
        self.ctx.action("show_jobs", self.show_jobs)
        self.ctx.action("generate_device_token", self.generate_device_token)
        self.ctx.action("cleanup_files", self.cleanup_files)
        self.ctx.action("archive_unknown", self.archive_unknown)
        self.ctx.action("test_ipp", self.test_ipp)
        self.ctx.action("show_wecom_setup", self.show_wecom_setup)
        self.ctx.schedule_interval("print_cleanup", self.cleanup, seconds=60)
        if self.config()["print_mode"] == "ipp":
            self.ctx.schedule_interval("ipp_dispatch", self.dispatch, seconds=3)
        await self.refresh_telegram()
        # Standalone plugins are not reloaded by the platform's Bot reconnect.
        # Check the read-only selection and restore a managed handler ourselves.
        self.ctx.schedule_interval("print_telegram_binding", self.refresh_telegram, seconds=10)
        self.ctx.log.info("远程打印已就绪，方式=%s", "IPP / FRP 直连" if self.config()["print_mode"] == "ipp" else "Windows 打印端")

    def unbind_telegram(self):
        self.telegram_binding = None
        for entry in self.telegram_handlers:
            client, callback, builder = entry
            try:
                client.remove_event_handler(callback, builder)
            except Exception:
                # The inactive binding also gates this handler. Keep the SDK's
                # record so normal context teardown can retry its removal.
                continue
            handlers = getattr(self.ctx, "_handlers", None)
            if isinstance(handlers, list):
                handlers[:] = [item for item in handlers if item is not entry]
        self.telegram_handlers = []

    async def refresh_telegram(self):
        if self.stopped:
            return
        try:
            selected = self.channels.telegram_bot_id()
            client = self.ctx.get_bot(selected)
            if client is None:
                raise ValueError("平台选定的 Telegram Bot 当前不可用")
        except ValueError as exc:
            self.unbind_telegram()
            issue = str(exc)
            if issue != self.telegram_connection_issue and members(self.config()["telegram_users"]):
                self.ctx.log.warning("Telegram 打印未接入：%s；恢复后自动接入，其他打印渠道不受影响", issue)
            self.telegram_connection_issue = issue
            return
        if self.telegram_binding and self.telegram_binding[:2] == (selected, client):
            return
        self.unbind_telegram()
        binding = (selected, client, object())

        async def receive(event):
            if self.stopped or self.telegram_binding is not binding:
                return
            try:
                # Route changes must reject old-client events even before the
                # next interval runs. Never substitute an unrelated online Bot.
                if (self.channels.telegram_bot_id() != selected or self.ctx.get_bot(selected) is not client
                        or event.client is not client):
                    return
            except ValueError:
                return
            await self.telegram(event)

        original_scope = getattr(self.ctx, "scope", "standalone")
        handlers = getattr(self.ctx, "_handlers", [])
        previous = {id(item) for item in handlers}
        self.ctx.bot_id = selected
        self.ctx.scope = "bot"
        try:
            self.ctx.on_message(incoming=True, outgoing=False)(receive)
            self.telegram_binding = binding
        except Exception as exc:
            issue = "处理器注册失败（" + type(exc).__name__ + "）"
            if issue != self.telegram_connection_issue and members(self.config()["telegram_users"]):
                self.ctx.log.warning("Telegram 打印未接入：%s；稍后自动重试", issue)
            self.telegram_connection_issue = issue
        finally:
            self.ctx.scope = original_scope
            self.telegram_handlers = [item for item in getattr(self.ctx, "_handlers", []) if id(item) not in previous]
        if self.telegram_binding is None:
            self.unbind_telegram()
        else:
            if self.telegram_connection_issue and members(self.config()["telegram_users"]):
                self.ctx.log.info("Telegram 打印已重新接入平台 Bot")
            self.telegram_connection_issue = ""

    def spawn(self, coroutine, name):
        if self.stopped:
            coroutine.close()
            raise ValueError("插件正在停止")
        try:
            return self.ctx.create_task(coroutine, name=name)
        except BaseException:
            coroutine.close()
            raise

    async def notify(self, source, owner, text, source_channel=""):
        if self.stopped:
            return
        try:
            if source == "telegram":
                bot = self.ctx.get_bot(source_channel) if source_channel else self.ctx.bot
                if bot is None:
                    raise ValueError("Bot 未连接")
                await bot.send_message(int(owner.split(":", 1)[1]), text, parse_mode=None)
            elif source == "wecom":
                config = self.wecom_config()
                identity = self.wecom_identity(config)
                if source_channel != identity or not owner.startswith("wecom:" + identity + ":"):
                    raise ValueError("企业微信应用已更换，未将旧任务回执发送到其他应用")
                await self.wecom.send(owner.rsplit(":", 1)[1], text)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.ctx.log.warning("打印回执发送失败（%s），任务状态已保存", type(exc).__name__)

    async def notify_job(self, job):
        text = f"打印任务 {job['id']}\n{job['filename']}\n状态：{LABELS[job['status']]}"
        if job.get("message"):
            text += "\n" + job["message"]
        await self.notify(job["source"], job["owner"], text, job.get("source_channel", ""))

    async def telegram(self, event):
        cfg = self.config()
        if not cfg["enabled"] or not event.is_private:
            return
        sender = str(event.sender_id)
        if sender not in members(cfg["telegram_users"]) or not sender.isdecimal():
            return
        owner = "telegram:" + sender
        message = event.message
        if getattr(message, "photo", None) or getattr(message, "document", None):
            if self.receiving >= 4:
                await event.reply("正在收取其他文件，请稍后重发。", parse_mode=None)
                return
            file = getattr(message, "file", None)
            name = safe_name(getattr(file, "name", None) or "image.jpg")
            size = int(getattr(file, "size", 0) or 0)
            maximum = cfg["max_file_mb"] * 1024 * 1024
            if size <= 0 or size > maximum:
                await event.reply("文件为空或超过大小上限。", parse_mode=None)
                return
            try:
                bot_id = str(getattr(self.ctx, "bot_id", "") or "")
                job = await self.queue.reserve(f"telegram:{bot_id}:{event.chat_id}:{message.id}", owner, name, "telegram", size,
                                               source_channel=bot_id)
                if job is None:
                    return
                self.receiving += 1
                try:
                    self.spawn(self.receive_telegram(job, event), "print_telegram_download")
                except BaseException:
                    self.receiving -= 1
                    await self.queue.fail_receive(job["id"], "下载任务未能启动，请重新发送")
                    raise
            except ValueError as exc:
                await event.reply(str(exc), parse_mode=None)
            return
        text = str(getattr(message, "raw_text", "") or "").strip()
        if re.match(r"^(?:/(?:start|print(?:_help|_jobs|_cancel)?|printers)(?:@\w+)?(?:\s|$)|打印|任务|取消|帮助)", text):
            answer = await self.command(owner, text)
            await event.reply(answer, parse_mode=None)

    async def command(self, owner, text):
        parts = text.split(maxsplit=1)
        if not parts:
            return ""
        command, argument = parts[0].split("@", 1)[0].lower(), parts[1] if len(parts) == 2 else ""
        try:
            if command in {"/print", "打印"}:
                values = argument.split(maxsplit=2)
                if not values:
                    return self.help()
                copies = int(values[1]) if len(values) > 1 else None
                printer = values[2] if len(values) > 2 else None
                job = await self.queue.confirm(values[0], owner, copies, printer)
                if job.get("backend") == "ipp":
                    return f"已确认任务 {job['id']}：{job['copies']} 份。等待服务器通过 IPP 提交打印。"
                return f"已确认任务 {job['id']}：{job['copies']} 份。等待电脑端提交打印；电脑离线时会排队。"
            if command in {"/print_cancel", "取消"}:
                job = await self.queue.cancel(argument.strip(), owner)
                return f"任务 {job['id']} 已取消。"
            if command in {"/print_jobs", "任务"}:
                return self.jobs_text(await self.queue.jobs(owner))
            if command in {"/printers", "打印机"}:
                if self.config()["print_mode"] == "ipp":
                    await self.refresh_ipp()
                return self.device_text()
            return self.help()
        except ValueError as exc:
            return str(exc) if str(exc) != "invalid literal for int() with base 10" and not str(exc).startswith("invalid literal") else "份数必须是整数。"

    def help(self):
        printer = " [打印机完整名称]" if self.config()["print_mode"] == "agent" else ""
        return (f"先发送 PDF 或图片。\n打印 任务ID [份数]{printer}\n取消 任务ID\n任务：查看你的最近任务\n打印机：查看设备状态"
                + "\nTelegram 仅接受私聊，支持 /print、/print_cancel、/print_jobs、/printers。\n已提交仅表示打印队列接收，不保证实际出纸。")

    @staticmethod
    def jobs_text(jobs):
        if not jobs:
            return "暂无打印任务。"
        return "最近打印任务：\n" + "\n".join(f"{j['id']} · {LABELS[j['status']]} · {j['filename']} · {j['copies']}份" for j in jobs)

    def device_text(self):
        if self.config()["print_mode"] == "ipp":
            if not self.ipp_status:
                return "IPP / FRP 直连模式。请先填写 IPP 访问地址，点击“测试 IPP 连接（不打印）”。"
            return self.ipp_text(self.ipp_status)
        device = self.queue.device
        if not device:
            return "电脑端尚未连接。请在 Windows 电脑配置并运行 agent 打印端。"
        online = time.time() - device.get("last_seen", 0) < 60
        return ("电脑端在线" if online else "电脑端离线（以下为上次报告）") + "\n允许的打印机：\n" + ("\n".join(device.get("printers", [])) or "无") + "\n默认打印机：" + (device.get("default_printer") or "未设置")

    async def receive_telegram(self, job, event):
        async def download(path, maximum):
            total = 0
            # Telethon 原生流式下载；未知/虚报大小也不能超出实际下载上限。
            with path.open("wb") as output:
                async for chunk in event.client.iter_download(event.message.media, request_size=256 * 1024):
                    total += len(chunk)
                    if total > maximum or total > job["size"]:
                        raise ValueError("文件实际大小超过允许范围")
                    await asyncio.to_thread(output.write, chunk)
            return job["filename"]
        await self.receive(job, download)

    async def receive_wecom(self, job, media_id):
        async def download(path, maximum):
            if job.get("source_channel") != self.wecom_identity(self.wecom_config()):
                raise ValueError("企业微信应用已更换，请在当前应用重新发送文件")
            suggested = await self.wecom.download(media_id, path, maximum)
            return suggested or job["filename"]
        await self.receive(job, download)

    async def receive(self, job, downloader):
        path = self.queue.file(job["id"])
        temporary = path.with_suffix(".part")
        try:
            async with self.downloads:
                cfg = self.config()
                name = await asyncio.wait_for(downloader(temporary, cfg["max_file_mb"] * 1024 * 1024), timeout=150)
                metadata = await asyncio.to_thread(inspect_file, temporary, name, cfg["max_file_mb"] * 1024 * 1024, cfg["max_pages"])
                await asyncio.to_thread(temporary.replace, path)
                job = await self.queue.finish(job["id"], metadata)
            text = f"收到：{job['filename']}\n任务：{job['id']}\n{job['pages']} 页，{job['copies']} 份\n状态：{LABELS[job['status']]}"
            if job["status"] == "pending":
                text += f"\n发送“打印 {job['id']}”确认；也可“取消 {job['id']}”。"
            await self.notify(job["source"], job["owner"], text, job.get("source_channel", ""))
            self.ctx.log.info("打印文件已收取：任务 %s，%s 页，状态=%s", job["id"], job["pages"], LABELS[job["status"]])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            reason = str(exc) if isinstance(exc, ValueError) else "收取文件失败，请重新发送或检查网络"
            try:
                await self.queue.fail_receive(job["id"], reason)
            except Exception:
                self.ctx.log.error("打印任务保存失败，请重载插件后检查队列")
            await self.notify(job["source"], job["owner"], f"任务 {job['id']} 未进入打印队列：{reason}", job.get("source_channel", ""))
            self.ctx.log.warning("打印文件未入队：任务 %s（%s）", job["id"], type(exc).__name__)
        finally:
            self.receiving -= 1
            # 平台停用时不会继续处理业务，未完成收件由下次启用恢复为失败。
            await asyncio.to_thread(temporary.unlink, missing_ok=True)

    async def wecom_callback(self, request):
        cfg = self.config()
        try:
            channel = self.wecom_config()
        except ValueError:
            return PlainTextResponse("disabled", status_code=503)
        try:
            decrypted = await self.wecom.verify(request)
            if request.method == "GET":
                return PlainTextResponse(decrypted.decode("utf-8"))
            if not cfg["enabled"]:
                return PlainTextResponse("disabled", status_code=503)
            message = self.wecom.parse(decrypted)
            if message.get("ToUserName") != channel["wecom_corp_id"] or message.get("AgentID") != str(channel["wecom_agent_id"]):
                return PlainTextResponse("forbidden", status_code=403)
            user = message.get("FromUserName", "")
            if not user or user not in members(cfg["wecom_users"]) or not re.fullmatch(r"[A-Za-z0-9_.@-]{1,128}", user) or user.lower() == "@all":
                return PlainTextResponse("success")
            identity = self.wecom_identity(channel)
            owner = "wecom:" + identity + ":" + user
            if message.get("MsgType") in {"file", "image"}:
                if self.receiving >= 4:
                    return PlainTextResponse("busy", status_code=429)
                media = message.get("MediaId", "")
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", media):
                    raise ValueError("企业微信媒体 ID 无效")
                source_key = f"wecom:{identity}:{user}:{message.get('MsgId') or media}"
                job = await self.queue.reserve(source_key, owner, safe_name(message.get("FileName") or "image"), "wecom", cfg["max_file_mb"] * 1024 * 1024,
                                               source_channel=identity)
                if job is not None:
                    self.receiving += 1
                    try:
                        self.spawn(self.receive_wecom(job, media), "print_wecom_download")
                    except BaseException:
                        self.receiving -= 1
                        await self.queue.fail_receive(job["id"], "下载任务未能启动，请重新发送")
                        raise
            elif message.get("MsgType") == "text":
                self.spawn(self.wecom_command(owner, message.get("Content", "")), "print_wecom_command")
            return PlainTextResponse("success")
        except ValueError:
            return PlainTextResponse("invalid request", status_code=400)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.ctx.log.warning("企业微信打印请求失败（%s）", type(exc).__name__)
            return PlainTextResponse("unavailable", status_code=503)

    async def wecom_command(self, owner, content):
        await self.notify("wecom", owner, await self.command(owner, content), owner.split(":", 2)[1])

    def authorized_agent(self, request):
        cfg = self.config()
        token = cfg["device_token"]
        supplied = str(request.headers.get("authorization", ""))
        return (cfg["enabled"] and cfg["print_mode"] == "agent" and re.fullmatch(r"[!-~]{32,512}", token) is not None and
                re.fullmatch(r"[A-Za-z0-9_-]{1,128}", cfg["device_id"]) is not None and len(supplied) < 1024 and
                hmac.compare_digest(supplied.encode("utf-8"), ("Bearer " + token).encode("ascii")) and
                hmac.compare_digest(str(request.headers.get("x-print-device", "")).encode("utf-8"), cfg["device_id"].encode("ascii")))

    async def agent(self, request):
        if not self.authorized_agent(request):
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        if request.method != "POST" or len(request.body) > 16 * 1024:
            return JSONResponse({"ok": False, "error": "invalid request"}, status_code=400)
        payload = request.json
        if not isinstance(payload, dict):
            return JSONResponse({"ok": False, "error": "invalid request"}, status_code=400)
        try:
            op = payload.get("op")
            if op == "hello":
                return await self.queue.hello(payload)
            if op == "poll":
                if "printers" in payload:
                    await self.queue.hello(payload)
                return await self.queue.poll()
            if op == "start":
                return await self.queue.start(payload.get("job_id"), payload.get("claim_token"))
            if op == "result":
                job = await self.queue.result(payload.get("job_id"), payload.get("claim_token"), payload.get("status"), payload.get("spool_id", ""))
                if job:
                    self.ctx.log.info("打印任务 %s：%s", job["id"], LABELS[job["status"]])
                    try:
                        self.spawn(self.notify_job(job), "print_result_notice")
                    except Exception:
                        self.ctx.log.warning("打印回执未发送，任务状态已保存")
                return {"ok": True}
            raise ValueError("操作无效")
        except ValueError:
            return JSONResponse({"ok": False, "error": "invalid job or operation"}, status_code=409)

    async def agent_file(self, request):
        if not self.authorized_agent(request):
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        if request.method != "GET":
            return JSONResponse({"ok": False}, status_code=405)
        try:
            path = await self.queue.downloadable(request.query.get("job_id"), request.headers.get("x-print-claim", ""))
            return FileResponse(path, media_type="application/octet-stream", headers={"Cache-Control": "no-store"})
        except ValueError:
            return JSONResponse({"ok": False, "error": "invalid claim"}, status_code=409)

    async def cleanup(self):
        _, jobs = await self.queue.cleanup()
        for job in jobs:
            await self.notify_job(job)

    @staticmethod
    def ipp_text(caps):
        states = {3: "空闲", 4: "正在处理", 5: "已停止"}
        return (f"IPP 打印机：{caps.get('name') or '未提供名称'}\n状态：{states.get(caps.get('state'), '未知')}"
                + f"\n接受任务：{'是' if caps.get('accepting_jobs') else '否'}"
                + "\n支持格式：" + "、".join(caps.get("formats", []))
                + ("\n图片排版：完整等比缩放，不裁切" if "fit" in caps.get("print_scaling_supported", [])
                   else "\n图片排版：设备未声明完整缩放能力，图片任务不会提交"))

    async def refresh_ipp(self):
        caps = await self.ipp.probe()
        self.ipp_status = caps
        return caps

    async def test_ipp(self, payload=None):
        try:
            caps = await self.refresh_ipp()
            return {"ok": True, "message": self.ipp_text(caps) + "\n只读取设备能力，未发送打印任务。"}
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}

    async def dispatch(self):
        cfg = self.config()
        if self.stopped or not cfg["enabled"] or cfg["print_mode"] != "ipp" or self.dispatch_lock.locked():
            return
        async with self.dispatch_lock:
            grant = (await self.queue.poll("ipp"))["job"]
            if grant is None:
                return
            job_id, claim = grant["id"], grant["claim_token"]
            original = self.queue.file(job_id)
            converted = original.with_suffix(".ipp.jpg")
            started, status, spool_id = False, "failed", ""
            message = ""
            try:
                caps = await self.refresh_ipp()
                metadata = await asyncio.to_thread(inspect_file, original, grant["filename"], cfg["max_file_mb"] * 1024 * 1024, cfg["max_pages"])
                if metadata["sha256"] != grant["sha256"] or metadata["format"] != grant["format"] or metadata["size"] != grant["size"]:
                    raise ValueError("打印文件内容与收件记录不一致，已停止提交")
                if grant["copies"] > self.config()["max_copies"]:
                    raise ValueError("打印份数超过当前安全上限，请重新发送并确认")
                self.ipp.validate_document(grant["format"], grant["copies"], caps)
                prepared, mime = await self.ipp.prepare(original, grant["format"])
                latest = self.config()
                if self.stopped or not latest["enabled"] or grant["copies"] > latest["max_copies"]:
                    raise ValueError("打印已关闭或份数上限已更改，未提交任务")
                permission = await self.queue.start(job_id, claim)
                if not permission["proceed"]:
                    return
                started = True
                receipt = await self.ipp.print_job(prepared, mime, job_id, grant["copies"], caps)
                spool_id, status = receipt["spool_id"], "submitted"
                message = f"打印机已接收任务（编号 {spool_id}）；实际出纸请查看打印机"
            except asyncio.CancelledError:
                # 正在 POST 时取消无法证明打印机未收件。重启也不能再次发送。
                try:
                    await self.queue.result(job_id, claim, "unknown" if started else "failed",
                                            message="提交中断，无法确认打印机是否已收件；不会自动重打" if started else "打印准备中断，未提交打印任务")
                except Exception:
                    pass  # 持久记录下次启用会恢复 unknown / failed。
                raise
            except IPPRejected as exc:
                status, message = "failed", str(exc)
            except IPPSubmissionUnknown as exc:
                status, message = "unknown", str(exc)
            except Exception as exc:
                status = "unknown" if started else "failed"
                message = str(exc) if isinstance(exc, ValueError) else ("IPP 提交结果不确定，请核查打印机；不会自动重打" if started else "IPP 准备失败，请检查连接和打印文件")
            finally:
                if converted.exists():
                    await self.queue._unlink(converted)
            result = await self.queue.result(job_id, claim, status, spool_id, message=message)
            if result is not None:
                self.ctx.log.info("IPP 打印任务 %s：%s", job_id, LABELS[status])
                await self.notify_job(result)

    def urls(self):
        base = self.config()["public_base_url"].rstrip("/")
        if not base and self.config()["print_mode"] == "ipp":
            return "Telegram / IPP 模式无需平台外网回调地址；企业微信接收文件需填写平台外网 HTTPS 地址。"
        parsed = urlsplit(base)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            return "请先设置正确的平台外网 HTTPS 地址。"
        result = f"企微接收消息 URL：\n{base}/api/plugin/remote_print/wecom"
        if self.config()["print_mode"] == "agent":
            result += f"\n电脑端 server_url：\n{base}\n电脑端接口：\n{base}/api/plugin/remote_print/agent"
        return result

    async def show_connection(self, payload=None):
        return {"ok": True, "message": self.urls() + "\n\n" + self.device_text()}

    async def show_jobs(self, payload=None):
        return {"ok": True, "message": self.jobs_text(await self.queue.jobs())}

    async def generate_device_token(self, payload=None):
        self.ctx.update_config({"device_token": secrets.token_urlsafe(32)})
        return {"ok": True, "message": "新密钥已保存。请刷新配置页，用眼睛查看“电脑端连接密钥”，更新电脑端配置。"}

    async def cleanup_files(self, payload=None):
        count, _ = await self.queue.cleanup(completed_only=True)
        return {"ok": True, "message": f"已清理 {count} 个已结束任务文件。不会重新打印任务。"}

    async def archive_unknown(self, payload=None):
        count = await self.queue.archive_unknown()
        return {"ok": True, "message": f"已归档 {count} 个待核查任务。未重新打印，也未取消打印机现有任务。"}

    async def admin_status(self, request):
        if request.method != "GET":
            return JSONResponse({"ok": False}, status_code=405)
        return {"ok": True, "faulted": self.queue.faulted, "mode": self.config()["print_mode"], "device": self.queue.device,
                "ipp": {key: self.ipp_status.get(key) for key in ("name", "state", "accepting_jobs", "formats")},
                "connection": self.urls(), "jobs": await self.queue.jobs()}


async def setup(ctx):
    service = RemotePrint(ctx)
    ctx._remote_print = service
    try:
        await service.setup()
    except BaseException:
        service.queue.close()
        raise


async def teardown(ctx):
    service = getattr(ctx, "_remote_print", None)
    if service is not None:
        service.stopped = True
        # 进程锁由平台 add_cleanup 在处理器和后台任务取消后释放。
