"""Telegram / 企业微信消息入口和经过设备密钥鉴权的主动领取接口。"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import urlsplit

from starlette.responses import FileResponse, JSONResponse

from . import __plugin__
from .channels import PlatformChannels
from .chat import action_buttons, display_filename, failure_reason, is_mutating_text, parse_action, received_text, simple_command, status_text, wecom_received_text, welcome_text
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
        self.wecom = WeCom(ctx, self.wecom_config)
        self.ipp = IPPPrinter(ctx, self.config)
        self.ipp_status = {}
        self.dispatch_lock = asyncio.Lock()
        self.dispatch_task = None
        self.downloads = asyncio.Semaphore(2)
        self.receiving = 0
        self.stopped = False
        self.wecom_generation = None
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
            raise ValueError("请在平台通知设置为“远程打印”关联企业微信自建应用；群机器人不能接收文件")
        if config.get("wecom_callback_enabled") is not True:
            raise ValueError("请先在平台企业微信自建应用中开启消息回调")
        return config

    async def show_wecom_setup(self, payload=None):
        try:
            config = self.wecom_config()
            return {"ok": True, "message": (
                f"平台企业微信应用：{config.get('wecom_channel_name') or config['wecom_channel_id']}\n"
                + self.urls()
                + "\n\n填写位置：企业微信管理后台 → 应用管理 → 此自建应用 → 接收消息 → 设置 API 接收。"
                + "\n使用平台统一回调，已设置正确地址时不用更换；Token 和 EncodingAESKey 仍在平台通知渠道设置。"
                + "\n请在平台插件通知设置中为“远程打印”关联此应用，仅设置默认应用不能接收打印文件。"
                + "\n图片、PDF 和操作指令由平台交给本插件；/插件、/运行 等平台指令仍可使用，旧卡片可继续操作原任务。"
                + "\n若旧版填了 /api/plugin/remote_print/wecom，请换回上面的平台统一回调地址，旧打印专用入口已移除。"
                + "\n设置好后开启插件的“接收打印文件”，并确保成员账号在平台回调名单和插件打印名单中均已授权。")}
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}

    async def setup(self):
        if (not callable(getattr(self.ctx, "on_wecom_message", None))
                or not callable(getattr(getattr(self.ctx, "routes", None), "wecom_handler_token", None))):
            raise ValueError("远程打印需要平台的统一企业微信消息接口，请先更新平台再启用插件")
        self.remove_obsolete_channel_config()
        self.seed_config_defaults()
        await self.queue.open()
        self.ctx.on_wecom_message(self.wecom_message, message_types=("text", "image", "file", "event"),
                                 events=("enter_agent", "template_card_event"))
        self.wecom_generation = self.ctx.routes.wecom_handler_token(self.ctx.plugin_id, "text")
        if self.wecom_generation is None:
            raise ValueError("平台企业微信消息处理器未注册，无法启用远程打印")
        self.ctx.on_webhook("agent", self.agent)
        self.ctx.on_webhook("agent_file", self.agent_file)
        self.ctx.on_api("status", self.admin_status)
        self.ctx.on_api("tools", self.admin_tools)
        self.ctx.action("show_connection", self.show_connection)
        self.ctx.action("show_jobs", self.show_jobs)
        self.ctx.action("generate_device_token", self.generate_device_token)
        self.ctx.action("cleanup_files", self.cleanup_files)
        self.ctx.action("archive_unknown", self.archive_unknown)
        self.ctx.action("test_ipp", self.test_ipp)
        self.ctx.action("show_wecom_setup", self.show_wecom_setup)
        self.ctx.schedule_interval("打印文件清理", self.cleanup, seconds=900)
        if self.config()["print_mode"] == "ipp":
            self.ctx.schedule_interval("打印队列兜底检查", self.check_queue, seconds=300)
        await self.refresh_telegram()
        # Standalone plugins are not reloaded by the platform's Bot reconnect.
        # Check the read-only selection and restore a managed handler ourselves.
        self.ctx.schedule_interval("打印机器人连接检查", self.refresh_telegram, seconds=300)
        self.request_dispatch()
        self.ctx.log.info("远程打印已就绪，方式=%s", "直接连接网络打印机" if self.config()["print_mode"] == "ipp" else "通过 Windows 电脑打印")

    def seed_config_defaults(self):
        # The native form reads saved values, not schema defaults. Fill only this
        # plugin's missing fields; an explicitly saved empty/false value is kept.
        current = dict(self.ctx.config)
        missing = {key: copy.deepcopy(spec["default"])
                   for key, spec in __plugin__["config_schema"].items()
                   if "default" in spec and spec["type"] not in {"info", "action"} and key not in current}
        if missing:
            self.ctx.update_config(missing)

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

        async def clicked(event):
            if self.stopped or self.telegram_binding is not binding:
                return
            try:
                if (self.channels.telegram_bot_id() != selected or self.ctx.get_bot(selected) is not client
                        or event.client is not client):
                    return
            except ValueError:
                return
            await self.telegram_callback(event)

        original_scope = getattr(self.ctx, "scope", "standalone")
        handlers = getattr(self.ctx, "_handlers", [])
        previous = {id(item) for item in handlers}
        self.ctx.bot_id = selected
        self.ctx.scope = "bot"
        try:
            self.ctx.on_message(incoming=True, outgoing=False)(receive)
            self.ctx.on_callback(pattern=rb"^rp:")(clicked)
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

    @staticmethod
    def telegram_buttons(job, max_copies):
        from telethon import Button
        actions = action_buttons(job, max_copies)
        primary = [Button.inline(item["text"], item["key"].encode("ascii"))
                   for item in actions if item["key"].startswith("rp:print:")]
        secondary = [Button.inline(item["text"], item["key"].encode("ascii"))
                     for item in actions if not item["key"].startswith("rp:print:")]
        return [row for row in (primary, secondary) if row]

    def wecom_owner_allowed(self, owner, source_channel):
        if (self.wecom_generation is not None
                and self.ctx.routes.wecom_handler_token(self.ctx.plugin_id, "text") != self.wecom_generation):
            raise ValueError("打印入口已重载，本次回执未发送。")
        config = self.wecom_config()
        identity = self.wecom_identity(config)
        user = owner.rsplit(":", 1)[-1]
        platform_users = {value.strip().casefold() for value in config["wecom_callback_users"].split("|") if value.strip()}
        if (self.stopped or not self.config()["enabled"] or source_channel != identity
                or owner != f"wecom:{identity}:{user}" or user.casefold() not in platform_users
                or user.casefold() not in {value.casefold() for value in members(self.config()["wecom_users"])}
                or user.lower() == "@all"):
            raise ValueError("打印权限已更改，请联系家人或管理员。")
        return user

    def owner_allowed(self, owner, source_channel, *, client=None, binding=None):
        if owner.startswith("wecom:"):
            return self.wecom_owner_allowed(owner, source_channel)
        cfg = self.config()
        user = owner.removeprefix("telegram:")
        if (self.stopped or not cfg["enabled"] or not owner.startswith("telegram:")
                or not user.isdecimal() or user not in members(cfg["telegram_users"])):
            raise ValueError("打印权限已更改，请联系家人或管理员。")
        selected = self.channels.telegram_bot_id()
        bot = self.ctx.get_bot(selected)
        if (selected != source_channel or bot is None or (client is not None and bot is not client)
                or (binding is not None and self.telegram_binding is not binding)):
            raise ValueError("打印入口已更改，请使用当前的打印机器人。")
        return user

    async def notify(self, source, owner, text, source_channel="", *, job=None, message=None):
        if self.stopped:
            return
        try:
            if source == "telegram":
                bot = self.ctx.get_bot(source_channel) if source_channel else self.ctx.bot
                if bot is None:
                    raise ValueError("Bot 未连接")
                options = {"buttons": self.telegram_buttons(job, self.config()["max_copies"])} if job else {}
                await bot.send_message(int(owner.split(":", 1)[1]), text, parse_mode=None, **options)
            elif source == "wecom":
                user = self.wecom_owner_allowed(owner, source_channel)
                permission_check = lambda: self.wecom_owner_allowed(owner, source_channel)
                if job and job["status"] == "pending":
                    # The callback cannot reliably distinguish WeChat from
                    # WeCom. A single usable text avoids duplicate receipts.
                    instructions = wecom_received_text(job, self.config()["max_copies"])
                    # Recheck both the SDK handler generation and this plugin's
                    # file-reception switch after waiting for an access token.
                    await self.wecom.send(user, instructions, permission_check=permission_check)
                else:
                    await self.wecom.send(user, text, permission_check=permission_check)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.ctx.log.warning("打印回执发送失败（%s），任务状态已保存", type(exc).__name__)

    async def notify_job(self, job):
        await self.notify(job["source"], job["owner"], status_text(job), job.get("source_channel", ""))

    async def button_action(self, owner, source_channel, value, *, permission_check=None):
        permission_check = permission_check or (lambda: self.owner_allowed(owner, source_channel))
        action, job_id, copies = parse_action(value)
        job = await self.queue.get_job(job_id, owner, source_channel=source_channel, permission_check=permission_check)
        try:
            if action == "print" and job["status"] == "pending":
                job = await self.queue.confirm(job_id, owner, copies, source_channel=source_channel, permission_check=permission_check)
                self.request_dispatch()
                return job
            if action == "cancel" and job["status"] in {"receiving", "pending", "queued", "leased"}:
                return await self.queue.cancel(job_id, owner, source_channel=source_channel, permission_check=permission_check)
        except ValueError:
            latest = await self.queue.get_job(job_id, owner, source_channel=source_channel, permission_check=permission_check)
            if latest["status"] == job["status"]:
                raise
            return latest
        return job

    async def telegram_callback(self, event):
        cfg = self.config()
        sender = str(event.sender_id)
        if self.stopped or not cfg["enabled"]:
            await event.answer("打印服务已关闭，请联系家人。", alert=True)
            return
        if not event.is_private or sender not in members(cfg["telegram_users"]) or not sender.isdecimal():
            await event.answer("你没有打印权限，请联系家人。", alert=True)
            return
        try:
            selected = self.channels.telegram_bot_id()
            if event.client is not self.ctx.get_bot(selected):
                await event.answer("这个打印入口已更改，请使用当前的打印机器人。", alert=True)
                return
            owner, binding = "telegram:" + sender, self.telegram_binding
            permission_check = lambda: self.owner_allowed(owner, selected, client=event.client, binding=binding)
            job = await self.button_action(owner, selected, event.data, permission_check=permission_check)
        except ValueError as exc:
            await event.answer(str(exc)[:160], alert=True)
            return
        await event.answer("已取消" if job["status"] == "cancelled" else "已确认" if job["status"] == "queued" else "状态已更新")
        try:
            await event.edit(status_text(job), parse_mode=None, buttons=self.telegram_buttons(job, self.config()["max_copies"]))
        except asyncio.CancelledError:
            raise
        except Exception:
            # Editing an old Telegram message is cosmetic, never a reason to
            # roll back a durable confirmation or resubmit the file.
            await self.notify("telegram", job["owner"], status_text(job), selected)

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
        if simple_command(text) or re.match(r"^(?:/(?:start|print(?:_help|_jobs|_cancel)?|printers)(?:@\w+)?(?:\s|$)|打印|任务|取消|进度|帮助|你好|开始)", text):
            channel = str(getattr(self.ctx, "bot_id", "") or "")
            if is_mutating_text(text) and not await self.queue.claim_message(f"tg-action:{channel}:{event.chat_id}:{message.id}"):
                await event.reply("这条操作已经处理，不会重复打印。回复“进度”查看。", parse_mode=None)
                return
            binding = self.telegram_binding
            permission_check = lambda: self.owner_allowed(owner, channel, client=event.client, binding=binding)
            answer = await self.command(owner, text, channel, permission_check=permission_check)
            await event.reply(answer, parse_mode=None)

    async def command(self, owner, text, source_channel=None, *, permission_check=None):
        parts = text.split(maxsplit=1)
        if not parts:
            return ""
        command, argument = parts[0].split("@", 1)[0].lower(), parts[1] if len(parts) == 2 else ""
        try:
            if permission_check is None and source_channel is not None:
                permission_check = lambda: self.owner_allowed(owner, source_channel)
            if permission_check is not None:
                permission_check()
            simple = simple_command(text)
            if simple:
                channel = source_channel if source_channel is not None else (
                    owner.split(":", 2)[1] if owner.startswith("wecom:") else str(getattr(self.ctx, "bot_id", "") or ""))
                if simple[0] == "print":
                    job = await self.queue.confirm_single(owner, channel, copies=simple[1], permission_check=permission_check)
                    self.request_dispatch()
                elif simple[0] == "cancel":
                    job = await self.queue.cancel_single(owner, channel, permission_check=permission_check)
                else:
                    job = await self.queue.status_single(owner, channel, permission_check=permission_check)
                return status_text(job)
            if command in {"/print", "打印"}:
                values = argument.split(maxsplit=2)
                if not values:
                    job = await self.queue.confirm_single(owner, source_channel or "", copies=1, permission_check=permission_check)
                    self.request_dispatch()
                    return status_text(job)
                copies = int(values[1]) if len(values) > 1 else None
                printer = values[2] if len(values) > 2 else None
                job = await self.queue.confirm(values[0], owner, copies, printer, source_channel=source_channel, permission_check=permission_check)
                self.request_dispatch()
                return status_text(job)
            if command in {"/print_cancel", "取消"}:
                if not argument.strip():
                    job = await self.queue.cancel_single(owner, source_channel or "", permission_check=permission_check)
                else:
                    job = await self.queue.cancel(argument.strip(), owner, source_channel=source_channel, permission_check=permission_check)
                return status_text(job)
            if command in {"/print_jobs", "任务"}:
                return self.jobs_text(await self.queue.jobs(owner))
            if command == "进度" and argument.strip():
                job = await self.queue.get_job(argument.strip(), owner, source_channel=source_channel,
                                               permission_check=permission_check)
                return status_text(job)
            if command in {"/printers", "打印机"}:
                if self.config()["print_mode"] == "ipp":
                    await self.refresh_ipp()
                return self.device_text()
            return self.help(advanced=command == "/print_help")
        except ValueError as exc:
            return str(exc) if str(exc) != "invalid literal for int() with base 10" and not str(exc).startswith("invalid literal") else "份数必须是整数。"

    def help(self, *, advanced=False):
        if not advanced:
            return welcome_text()
        printer = " [打印机完整名称]" if self.config()["print_mode"] == "agent" else ""
        return (f"先发送 PDF 或图片。\n打印 任务ID [份数]{printer}\n取消 任务ID\n任务：查看你的最近任务\n打印机：查看设备状态"
                + "\nTelegram 仅接受私聊，支持 /print、/print_cancel、/print_jobs、/printers。\n已提交仅表示打印队列接收，不保证实际出纸。")

    @staticmethod
    def jobs_text(jobs):
        if not jobs:
            return "暂无打印任务。"
        entries = []
        for job in jobs:
            entry = (f"{display_filename(job)} · {LABELS[job['status']]} · {job['copies']} 份\n"
                     f"编号：{job['id']}")
            if job["status"] in {"failed", "unknown"}:
                entry += "\n原因：" + failure_reason(job.get("message"))
            entries.append(entry)
        return "最近打印任务\n\n" + "\n\n".join(entries)

    def device_text(self):
        if self.config()["print_mode"] == "ipp":
            if not self.ipp_status:
                return "直接连接网络打印机。请先填写打印机访问地址，保存后点击“检查能否连接打印机（不打印）”。"
            return self.ipp_text(self.ipp_status)
        device = self.queue.device
        if not device:
            return "电脑端尚未连接。请在连接打印机的 Windows 电脑上配置并运行配套打印程序。"
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

    async def receive_wecom(self, job, message):
        async def download(path, maximum):
            self.wecom_owner_allowed(job["owner"], job.get("source_channel", ""))
            media = await message.download_media(max_bytes=min(maximum, 20 * 1024 * 1024))
            self.wecom_owner_allowed(job["owner"], job.get("source_channel", ""))
            if not media.content or len(media.content) > job["size"]:
                raise ValueError("文件为空或实际大小超过允许范围，请重新发送")
            await asyncio.to_thread(path.write_bytes, media.content)
            # Photo media filenames are often opaque MediaIDs, not user names.
            return "图片" if message.message_type == "image" else safe_name(message.file_name or media.filename or job["filename"])
        await self.receive(job, download, wecom_message=message)

    async def receive(self, job, downloader, *, wecom_message=None):
        path = self.queue.file(job["id"])
        temporary = path.with_suffix(".part")
        try:
            async with self.downloads:
                cfg = self.config()
                name = await asyncio.wait_for(downloader(temporary, cfg["max_file_mb"] * 1024 * 1024), timeout=150)
                metadata = await asyncio.to_thread(inspect_file, temporary, name, cfg["max_file_mb"] * 1024 * 1024, cfg["max_pages"])
                await asyncio.to_thread(temporary.replace, path)
                permission_check = None
                if job["source"] == "wecom":
                    permission_check = lambda: self.wecom_owner_allowed(job["owner"], job.get("source_channel", ""))
                job = await self.queue.finish(job["id"], metadata, permission_check=permission_check)
            self.request_dispatch()
            await self.notify(job["source"], job["owner"], received_text(job), job.get("source_channel", ""),
                              job=job if job["status"] == "pending" else None, message=wecom_message)
            self.ctx.log.info("打印文件已收取：任务 %s，%s 页，状态=%s", job["id"], job["pages"], LABELS[job["status"]])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            reason = failure_reason(str(exc)) if isinstance(exc, ValueError) else "文件收取失败，请重新发送或检查网络"
            try:
                await self.queue.fail_receive(job["id"], reason)
            except Exception:
                self.ctx.log.error("打印任务保存失败，请重载插件后检查队列")
            await self.notify(job["source"], job["owner"], f"任务 {job['id']} 未进入打印队列：{reason}", job.get("source_channel", ""),
                              message=wecom_message)
            self.ctx.log.warning("打印文件未入队：任务 %s，原因：%s", job["id"], reason)
        finally:
            self.receiving -= 1
            # 平台停用时不会继续处理业务，未完成收件由下次启用恢复为失败。
            await asyncio.to_thread(temporary.unlink, missing_ok=True)

    async def wecom_message(self, message):
        """Receive only platform-authenticated messages; persist before download."""
        cfg = self.config()
        try:
            channel = self.wecom_config()
        except ValueError:
            return
        if (self.stopped or not cfg["enabled"] or message.channel_id != channel["wecom_channel_id"]
                or message.corp_id != channel["wecom_corp_id"]
                or message.agent_id != str(channel["wecom_agent_id"])):
            return
        identity = self.wecom_identity(channel)
        user = message.user_id
        owner = f"wecom:{identity}:{user}"
        try:
            self.wecom_owner_allowed(owner, identity)
        except ValueError:
            return
        try:
            if message.message_type in {"file", "image"}:
                if self.receiving >= 4:
                    return "正在收取其他文件，本次未收取。请稍后重新发送。"
                maximum = min(cfg["max_file_mb"], 20) * 1024 * 1024
                if message.file_size is not None and not 0 < message.file_size <= maximum:
                    return f"文件为空或超过 {min(cfg['max_file_mb'], 20)} MB，本次未收取。请压缩后重新发送。"
                source_key = f"wecom:{identity}:{user.casefold()}:{message.message_id}"
                job = await self.queue.reserve(source_key, owner, safe_name(message.file_name or "image"), "wecom", message.file_size or maximum,
                                               source_channel=identity)
                if job is not None:
                    self.receiving += 1
                    try:
                        self.spawn(self.receive_wecom(job, message), "print_wecom_download")
                    except BaseException:
                        self.receiving -= 1
                        await self.queue.fail_receive(job["id"], "下载任务未能启动，请重新发送")
                        raise
            elif message.message_type == "text":
                content = message.text
                if is_mutating_text(content):
                    if not await self.queue.claim_message(f"wx-action:{identity}:{user.casefold()}:{message.message_id}"):
                        return "这条操作已经处理，不会重复打印。回复“进度”查看。"
                await self.wecom_command(owner, content, message=message)
            elif message.message_type == "event":
                if message.event == "enter_agent":
                    await self.notify("wecom", owner, welcome_text(), identity, message=message)
                elif message.event == "template_card_event":
                    action, job_id, _ = parse_action(message.event_key)
                    if message.fields.get("CardType") != "button_interaction" or message.fields.get("TaskId") != "rp-" + job_id:
                        raise ValueError("企业微信打印按钮与文件不匹配")
                    if action in {"print", "cancel"}:
                        key = f"wx-button:{identity}:{user.casefold()}:{message.fields['TaskId']}:{message.event_key}:{message.create_time}"
                        if not await self.queue.claim_message(key):
                            return "这条操作已经处理，不会重复打印。回复“进度”查看。"
                    await self.wecom_button(owner, identity, message.event_key, message=message)
        except ValueError as exc:
            return str(exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.ctx.log.warning("企业微信打印请求失败（%s）", type(exc).__name__)
            return "本次打印操作未完成，请查看“进度”；新文件未收取时请重新发送。"

    async def wecom_command(self, owner, content, *, message):
        channel = owner.split(":", 2)[1]
        try:
            self.wecom_owner_allowed(owner, channel)
        except ValueError:
            return
        text = await self.command(owner, content, channel)
        self.wecom_owner_allowed(owner, channel)
        await self.notify("wecom", owner, text, channel, message=message)

    async def wecom_button(self, owner, channel, value, *, message):
        try:
            self.wecom_owner_allowed(owner, channel)
            job = await self.button_action(owner, channel, value)
            text = status_text(job)
        except ValueError as exc:
            text = str(exc)
        self.wecom_owner_allowed(owner, channel)
        await self.notify("wecom", owner, text, channel, message=message)

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

    async def check_queue(self):
        # The platform runs synchronous scheduled callbacks in a thread;
        # worker creation must stay on the event loop.
        self.request_dispatch()

    def request_dispatch(self):
        """Wake one managed worker only when there are queued IPP jobs."""
        cfg = self.config()
        if self.stopped or not cfg["enabled"] or cfg["print_mode"] != "ipp":
            return
        if self.dispatch_task is not None and not self.dispatch_task.done():
            return
        if not any(job["status"] == "queued" and job.get("backend") == "ipp"
                   for job in self.queue.state["jobs"].values()):
            return
        try:
            self.dispatch_task = self.spawn(self.dispatch_pending(), "print_ipp_dispatch")
        except Exception as exc:
            # A durable confirmation must not be reported as failed merely
            # because the worker could not start. The slow fallback can retry
            # queued jobs, never submitted or ambiguous jobs.
            self.ctx.log.warning("打印处理暂未启动（%s），已确认任务保留，稍后检查", type(exc).__name__)

    async def dispatch_pending(self):
        # Keep long queues outside the scheduler callback's time limit. Each
        # job still uses the persistent poll/start/result submission guards.
        # Reconcile expired leases when real work arrives; low-frequency file
        # cleanup must not leave a stale reservation blocking a new print.
        await self.cleanup()
        while await self.dispatch():
            pass

    async def dispatch(self):
        cfg = self.config()
        if self.stopped or not cfg["enabled"] or cfg["print_mode"] != "ipp" or self.dispatch_lock.locked():
            return False
        async with self.dispatch_lock:
            grant = (await self.queue.poll("ipp"))["job"]
            if grant is None:
                return False
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
                prepared, mime = await self.ipp.prepare(original, grant["format"], capabilities=caps)
                latest = self.config()
                if self.stopped or not latest["enabled"] or latest["print_mode"] != "ipp" or grant["copies"] > latest["max_copies"]:
                    raise ValueError("打印已关闭、连接方式或份数上限已更改，未提交任务")
                permission = await self.queue.start(job_id, claim)
                if not permission["proceed"]:
                    return True
                latest = self.config()
                if (self.stopped or not latest["enabled"] or latest["print_mode"] != "ipp"
                        or grant["copies"] > latest["max_copies"]
                        or not self.queue.route_matches(self.queue.state["jobs"][job_id])):
                    raise ValueError("打印设置在准备期间已更改，未提交任务")
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
                if status in {"failed", "unknown"}:
                    self.ctx.log.warning("IPP 打印任务 %s：%s，原因：%s", job_id, LABELS[status], failure_reason(message))
                else:
                    self.ctx.log.info("IPP 打印任务 %s：%s", job_id, LABELS[status])
                await self.notify_job(result)
            return True

    def urls(self):
        base = self.config()["public_base_url"].rstrip("/")
        if not base and self.config()["print_mode"] == "ipp":
            return "企业微信沿用平台统一回调；填写平台 HTTPS 访问地址后可查看完整 URL。仅 Telegram / IPP 模式无需填写。"
        parsed = urlsplit(base)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            return "请先设置正确的平台外网 HTTPS 地址。"
        try:
            channel = self.wecom_config()
            result = f"平台企业微信统一回调地址（填到企微后台“接收消息”）：\n{base}/api/wecom/callback/{channel['wecom_channel_id']}"
        except ValueError as exc:
            result = str(exc)
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

    async def admin_tools(self, request):
        # Registered only as an authenticated administrator API, never Webhook.
        if request.method != "POST":
            return JSONResponse({"ok": False, "message": "请使用 POST 执行管理工具。"}, status_code=405)
        if len(request.body) > 8192 or not isinstance(request.json, dict):
            return JSONResponse({"ok": False, "message": "工具请求格式无效。"}, status_code=400)
        payload = request.json
        tools = {"show_connection": self.show_connection, "show_jobs": self.show_jobs,
                 "show_wecom_setup": self.show_wecom_setup, "test_ipp": self.test_ipp,
                 "generate_device_token": self.generate_device_token,
                 "cleanup_files": self.cleanup_files, "archive_unknown": self.archive_unknown}
        action = payload.get("action")
        if not isinstance(action, str) or action not in tools:
            return JSONResponse({"ok": False, "message": "这个管理工具不存在。"}, status_code=400)
        if action in {"generate_device_token", "cleanup_files", "archive_unknown"} and payload.get("confirmed") is not True:
            return JSONResponse({"ok": False, "message": "请先确认此操作的影响。"}, status_code=400)
        return await tools[action]()


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
