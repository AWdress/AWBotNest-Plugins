"""Telegram / 企业微信消息入口和经过设备密钥鉴权的主动领取接口。"""
from __future__ import annotations

import asyncio
import copy
import hmac
import re
import secrets
import time
from urllib.parse import urlsplit

from starlette.responses import FileResponse, JSONResponse, PlainTextResponse

from . import __plugin__
from .files import inspect_file, safe_name
from .queue import LABELS, PrintQueue
from .wecom import WeCom


def members(value):
    return set(re.split(r"[\s,，;；]+", str(value or "").strip())) - {""}


class RemotePrint:
    def __init__(self, ctx):
        self.ctx = ctx
        self.queue = PrintQueue(ctx, self.config)
        self.wecom = WeCom(ctx, self.config)
        self.downloads = asyncio.Semaphore(2)
        self.receiving = 0
        self.stopped = False

    def config(self):
        cfg = {key: copy.deepcopy(field["default"]) for key, field in __plugin__["config_schema"].items() if "default" in field and field["type"] != "info"}
        cfg.update(dict(self.ctx.config))
        for key, limits in {"default_copies": (1, 5), "max_copies": (1, 5), "max_pages": (1, 50), "max_file_mb": (1, 25),
                            "max_queue": (1, 100), "max_storage_mb": (25, 1000), "retention_hours": (1, 168)}.items():
            try:
                number = int(cfg[key])
            except (ValueError, TypeError, OverflowError):
                number = __plugin__["config_schema"][key]["default"]
            cfg[key] = max(limits[0], min(limits[1], number))
        for key in ("enabled", "telegram_enabled", "wecom_enabled", "auto_print"):
            cfg[key] = cfg[key] is True
        for key in ("device_id", "device_token", "printer_name", "public_base_url"):
            cfg[key] = str(cfg[key] or "").strip()
        return cfg

    async def setup(self):
        await self.queue.open()
        self.ctx.on_webhook("wecom", self.wecom_callback)
        self.ctx.on_webhook("agent", self.agent)
        self.ctx.on_webhook("agent_file", self.agent_file)
        self.ctx.on_api("status", self.admin_status)
        self.ctx.action("show_connection", self.show_connection)
        self.ctx.action("show_jobs", self.show_jobs)
        self.ctx.action("generate_device_token", self.generate_device_token)
        self.ctx.action("cleanup_files", self.cleanup_files)
        self.ctx.action("archive_unknown", self.archive_unknown)
        self.ctx.schedule_interval("print_cleanup", self.cleanup, seconds=60)
        if self.config()["telegram_enabled"]:
            if self.ctx.bot is None:
                self.ctx.log.warning("Telegram 打印未接入：请先连接平台 Bot；企业微信不受影响")
            else:
                self.ctx.on_message(incoming=True, outgoing=False)(self.telegram)
        self.ctx.log.info("远程打印已就绪，等待授权用户和电脑端连接")

    def spawn(self, coroutine, name):
        if self.stopped:
            coroutine.close()
            raise ValueError("插件正在停止")
        try:
            return self.ctx.create_task(coroutine, name=name)
        except BaseException:
            coroutine.close()
            raise

    async def notify(self, source, owner, text):
        if self.stopped:
            return
        try:
            if source == "telegram":
                if self.ctx.bot is None:
                    raise ValueError("Bot 未连接")
                await self.ctx.bot.send_message(int(owner.split(":", 1)[1]), text, parse_mode=None)
            elif source == "wecom":
                await self.wecom.send(owner.split(":", 1)[1], text)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.ctx.log.warning("打印回执发送失败（%s），任务状态已保存", type(exc).__name__)

    async def notify_job(self, job):
        text = f"打印任务 {job['id']}\n{job['filename']}\n状态：{LABELS[job['status']]}"
        if job.get("message"):
            text += "\n" + job["message"]
        await self.notify(job["source"], job["owner"], text)

    async def telegram(self, event):
        cfg = self.config()
        if not cfg["enabled"] or not cfg["telegram_enabled"] or not event.is_private:
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
                job = await self.queue.reserve(f"telegram:{event.chat_id}:{message.id}", owner, name, "telegram", size)
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
                return f"已确认任务 {job['id']}：{job['copies']} 份。等待电脑端提交打印；电脑离线时会排队。"
            if command in {"/print_cancel", "取消"}:
                job = await self.queue.cancel(argument.strip(), owner)
                return f"任务 {job['id']} 已取消。"
            if command in {"/print_jobs", "任务"}:
                return self.jobs_text(await self.queue.jobs(owner))
            if command in {"/printers", "打印机"}:
                return self.device_text()
            return self.help()
        except ValueError as exc:
            return str(exc) if str(exc) != "invalid literal for int() with base 10" and not str(exc).startswith("invalid literal") else "份数必须是整数。"

    @staticmethod
    def help():
        return "先私聊发送 PDF 或图片。\n打印 任务ID [份数] [打印机完整名称]\n取消 任务ID\n任务：查看你的最近任务\n打印机：查看允许的打印机\nTelegram 也支持 /print、/print_cancel、/print_jobs、/printers。\n已提交仅表示系统队列接收，不保证实际出纸。"

    @staticmethod
    def jobs_text(jobs):
        if not jobs:
            return "暂无打印任务。"
        return "最近打印任务：\n" + "\n".join(f"{j['id']} · {LABELS[j['status']]} · {j['filename']} · {j['copies']}份" for j in jobs)

    def device_text(self):
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
            await self.notify(job["source"], job["owner"], text)
            self.ctx.log.info("打印文件已收取：任务 %s，%s 页，状态=%s", job["id"], job["pages"], LABELS[job["status"]])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            reason = str(exc) if isinstance(exc, ValueError) else "收取文件失败，请重新发送或检查网络"
            try:
                await self.queue.fail_receive(job["id"], reason)
            except Exception:
                self.ctx.log.error("打印任务保存失败，请重载插件后检查队列")
            await self.notify(job["source"], job["owner"], f"任务 {job['id']} 未进入打印队列：{reason}")
            self.ctx.log.warning("打印文件未入队：任务 %s（%s）", job["id"], type(exc).__name__)
        finally:
            self.receiving -= 1
            # 平台停用时不会继续处理业务，未完成收件由下次启用恢复为失败。
            await asyncio.to_thread(temporary.unlink, missing_ok=True)

    async def wecom_callback(self, request):
        cfg = self.config()
        if not cfg["wecom_enabled"]:
            return PlainTextResponse("disabled", status_code=503)
        try:
            decrypted = await self.wecom.verify(request)
            if request.method == "GET":
                return PlainTextResponse(decrypted.decode("utf-8"))
            if not cfg["enabled"]:
                return PlainTextResponse("disabled", status_code=503)
            message = self.wecom.parse(decrypted)
            if message.get("ToUserName") != cfg["wecom_corp_id"] or message.get("AgentID") != str(cfg["wecom_agent_id"]):
                return PlainTextResponse("forbidden", status_code=403)
            user = message.get("FromUserName", "")
            if not user or user not in members(cfg["wecom_users"]) or not re.fullmatch(r"[A-Za-z0-9_.@-]{1,128}", user) or user.lower() == "@all":
                return PlainTextResponse("success")
            owner = "wecom:" + user
            if message.get("MsgType") in {"file", "image"}:
                if self.receiving >= 4:
                    return PlainTextResponse("busy", status_code=429)
                media = message.get("MediaId", "")
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", media):
                    raise ValueError("企业微信媒体 ID 无效")
                source_key = f"wecom:{user}:{message.get('MsgId') or media}"
                job = await self.queue.reserve(source_key, owner, safe_name(message.get("FileName") or "image"), "wecom", cfg["max_file_mb"] * 1024 * 1024)
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
        await self.notify("wecom", owner, await self.command(owner, content))

    def authorized_agent(self, request):
        cfg = self.config()
        token = cfg["device_token"]
        supplied = str(request.headers.get("authorization", ""))
        return (cfg["enabled"] and re.fullmatch(r"[!-~]{32,512}", token) is not None and
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

    def urls(self):
        base = self.config()["public_base_url"].rstrip("/")
        parsed = urlsplit(base)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            return "请先设置正确的平台外网 HTTPS 地址。"
        return f"企微接收消息 URL：\n{base}/api/plugin/remote_print/wecom\n电脑端 server_url：\n{base}\n电脑端接口：\n{base}/api/plugin/remote_print/agent"

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
        return {"ok": True, "message": f"已归档 {count} 个待核查任务。未重新打印，也未取消 Windows 打印队列中的任务。"}

    async def admin_status(self, request):
        if request.method != "GET":
            return JSONResponse({"ok": False}, status_code=405)
        return {"ok": True, "faulted": self.queue.faulted, "device": self.queue.device,
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
