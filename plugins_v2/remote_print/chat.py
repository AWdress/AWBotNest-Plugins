"""Small, plain-language print controls shared by Telegram and WeCom."""
from __future__ import annotations

import re


def action_key(action, job_id, copies=None):
    key = f"rp:{action}:{job_id}"
    return key + f":{copies}" if copies is not None else key


def parse_action(value):
    if isinstance(value, bytes):
        try:
            value = value.decode("ascii")
        except UnicodeError:
            raise ValueError("这个按钮无效，请重新发送文件。") from None
    match = re.fullmatch(r"rp:(print|cancel|status):([a-f0-9]{16})(?::([1-5]))?", str(value))
    if not match or (match[1] == "print") != bool(match[3]):
        raise ValueError("这个按钮无效，请重新发送文件。")
    return match[1], match[2], int(match[3]) if match[3] else None


def action_buttons(job, max_copies):
    actions = []
    if job["status"] == "pending":
        actions.append({"text": "打印一份", "key": action_key("print", job["id"], 1)})
        if max_copies >= 2:
            actions.append({"text": "打印两份", "key": action_key("print", job["id"], 2)})
    if job["status"] in {"receiving", "pending", "queued", "leased"}:
        actions.append({"text": "取消打印", "key": action_key("cancel", job["id"])})
    actions.append({"text": "查看进度", "key": action_key("status", job["id"])})
    return actions


def received_text(job):
    if job["status"] != "pending":
        return status_text(job)
    return (f"收到：{job['filename']}\n共 {job['pages']} 页。\n"
            "点“打印一份”就开始，不想打印可点“取消打印”。\n"
            "也可以回复“打印”或“取消”。")


def status_text(job):
    phrases = {
        "receiving": "正在收文件，请稍等。",
        "pending": "还没开始打印。点“打印一份”即可。",
        "queued": f"已确认打印 {job['copies']} 份，正在等待打印机。\n先不要重复发送文件。",
        "leased": "正在准备打印，请稍等。",
        "started": "正在发送到打印机，请稍等，不要重复操作。",
        "submitted": "已提交打印，请到打印机旁看看是否出纸。",
        "failed": "这份文件没能提交打印。\n请检查打印机，再重新发送文件。",
        "unknown": "暂时不能确定有没有出纸。\n请先看看打印机，不会自动重打。",
        "cancelled": "已取消，这份文件不会继续提交打印。",
        "archived": "已结束核查，不会重新打印。",
    }
    return f"{job['filename']}\n" + phrases.get(job["status"], "请查看打印机，或联系家人帮忙检查。")


def welcome_text():
    return ("把照片或 PDF 文件发给我。\n"
            "收到后点“打印一份”即可。\n"
            "不想打印回复“取消”，想看进度回复“进度”。\n"
            "图片会完整缩放，不裁切；Word、Excel 请先转成 PDF。")


def simple_command(text):
    value = re.sub(r"\s+", "", str(text or "")).rstrip("。！!")
    if value in {"打印", "确认", "确认打印", "开始打印", "打印一份", "打印1份"}:
        return "print", 1
    if value in {"打印两份", "打印二份", "打印2份"}:
        return "print", 2
    if value in {"取消", "取消打印", "不打了", "不打印"}:
        return "cancel", None
    if value in {"进度", "查看进度", "打印进度", "状态", "查询"}:
        return "status", None
    return None


def is_mutating_text(text):
    simple = simple_command(text)
    if simple:
        return simple[0] in {"print", "cancel"}
    return bool(re.match(r"^(?:/(?:print|print_cancel)(?:@\w+)?(?:\s|$)|(?:打印|取消)\s+)", str(text or "").strip()))
