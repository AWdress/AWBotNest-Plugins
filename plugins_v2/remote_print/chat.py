"""Small, plain-language print controls shared by Telegram and WeCom."""
from __future__ import annotations

import re


SIDE_LABELS = {"default": "打印机默认", "one-sided": "单面",
               "two-sided-auto": "双面（自动识别横竖方向）",
               "two-sided-long-edge": "双面（长边翻页）", "two-sided-short-edge": "双面（短边翻页）"}


def normalize_sides(value):
    if not isinstance(value, str) or value not in SIDE_LABELS:
        raise ValueError("打印单双面设置无效，请使用单面打印、双面打印或短边双面打印。")
    return value


def print_command(text):
    value = re.sub(r"\s+", "", str(text or "")).rstrip("。！!")
    if value in {"确认", "确认打印", "开始打印"}:
        value = "打印"
    match = re.fullmatch(r"(全部|所有)?(单面|长边双面|短边双面|双面)?打印(一份|1份|两份|二份|2份)?", value)
    if not match:
        return None
    sides = {None: "default", "单面": "one-sided", "双面": "two-sided-auto",
             "长边双面": "two-sided-long-edge", "短边双面": "two-sided-short-edge"}[match[2]]
    return {"all": bool(match[1]), "copies": 2 if match[3] in {"两份", "二份", "2份"} else 1, "sides": sides}


def short_command(text):
    value = str(text or "").strip().rstrip("。！!").strip()
    match = re.fullmatch(r"(打印|单面打印|长边双面打印|短边双面打印|双面打印|取消|查看|进度)\s*"
                         r"(?:第\s*([1-9][0-9]{0,8})\s*批\s*)?文件\s*"
                         r"([1-9][0-9]{0,8})(?:\s+([1-5])(?:份)?|\s*(一份|两份|二份))?", value)
    if not match or (match[1] in {"取消", "查看", "进度"} and (match[4] or match[5])):
        return None
    action = {"取消": "cancel", "查看": "status", "进度": "status"}.get(match[1], "print")
    copies = (int(match[4]) if match[4] else 2 if match[5] in {"两份", "二份"} else 1) if action == "print" else None
    sides = {"单面打印": "one-sided", "长边双面打印": "two-sided-long-edge",
             "双面打印": "two-sided-auto", "短边双面打印": "two-sided-short-edge"}.get(match[1], "default")
    return {"action": action, "number": match[3], "batch": int(match[2]) if match[2] else None,
            "copies": copies, "sides": sides}


def batch_cancel_command(text):
    value = re.sub(r"\s+", "", str(text or "")).rstrip("。！!")
    return value in {"全部取消", "取消全部", "所有取消", "取消所有"}


def file_number(job):
    number = job.get("number")
    return str(number) if type(number) is int and 1 <= number <= 999999999 else ""


def file_reference(job):
    """Current-batch controls stay short; historical controls name their batch."""
    batch = job.get("number_batch")
    prefix = f"第{batch}批" if job.get("current_number_batch") is False and type(batch) is int else ""
    return f"{prefix}文件{file_number(job)}"


def file_heading(job):
    batch = job.get("number_batch")
    prefix = f"第{batch}批 · " if type(batch) is int else ""
    return f"{prefix}文件{file_number(job)}"


def action_key(action, job_id, copies=None):
    key = f"rp:{action}:{job_id}"
    return key + f":{copies}" if copies is not None else key


def parse_action(value):
    if isinstance(value, bytes):
        try:
            value = value.decode("ascii")
        except UnicodeError:
            raise ValueError("这个按钮无效，请重新发送文件。") from None
    match = re.fullmatch(r"rp:(print|duplex|batch_duplex|cancel|status):([a-f0-9]{16})(?::([1-5]))?", str(value))
    if not match or (match[1] in {"print", "duplex", "batch_duplex"}) != bool(match[3]):
        raise ValueError("这个按钮无效，请重新发送文件。")
    return match[1], match[2], int(match[3]) if match[3] else None


def action_buttons(job, max_copies):
    actions = []
    if job["status"] == "pending":
        actions.append({"text": "打印一份", "key": action_key("print", job["id"], 1)})
        if max_copies >= 2:
            actions.append({"text": "打印两份", "key": action_key("print", job["id"], 2)})
        actions.append({"text": "双面打印", "key": action_key("duplex", job["id"], 1)})
        if max_copies >= 2:
            actions.append({"text": "双面两份", "key": action_key("duplex", job["id"], 2)})
        if type(job.get("number_batch")) is int and job["number_batch"] > 0:
            actions.append({"text": "本批双面打印", "key": action_key("batch_duplex", job["id"], 1)})
    if job["status"] in {"receiving", "pending", "queued", "leased"}:
        actions.append({"text": "取消打印", "key": action_key("cancel", job["id"])})
    actions.append({"text": "查看进度", "key": action_key("status", job["id"])})
    return actions


def received_text(job):
    if job["status"] != "pending":
        return status_text(job)
    reference = file_reference(job)
    label = file_heading(job) + " · "
    return (f"文件已收到\n{label}{display_filename(job)} · 共 {job['pages']} 页\n\n"
            "只打这份：点“打印一份”或“双面打印”。\n"
            "同批文件都收齐后，点“本批双面打印”；两张图片会正反面打印。\n"
            "不想打印可点“取消打印”。\n"
            + f"也可回复“打印{reference}”“双面打印{reference}”或“取消{reference}”。\n"
            + "所有待处理文件：全部打印 / 全部双面打印。\n全部不要：全部取消。")


def wecom_received_text(job, max_copies):
    """One plain-text confirmation usable in both WeCom and WeChat."""
    if job["status"] != "pending":
        return status_text(job)
    reference = file_reference(job)
    label = file_heading(job) + " · "
    copies = f"\n打印两份：打印{reference}两份" if max_copies >= 2 else ""
    return (f"文件已收到\n{label}{display_filename(job)} · 共 {job['pages']} 页\n"
            "等待确认，还没开始打印。\n\n"
            f"打印一份：打印{reference}\n"
            f"取消这份：取消{reference}\n查看状态：查看{reference}\n"
            f"需要双面：双面打印{reference}{copies}\n\n"
            "多个文件都收齐后：\n全部打印 / 全部双面打印\n全部不要：全部取消")


def display_filename(job):
    name = re.sub(r"[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]", "", str(job.get("filename") or "文件"))
    name = re.split(r"[/\\]", name)[-1] or "文件"
    stem, separator, extension = name.rpartition(".")
    if (job.get("source") == "wecom" and extension.lower() in {"jpg", "jpeg", "png", "webp", "bmp"}
            and re.fullmatch(r"[A-Za-z0-9_-]{48,}", stem)):
        return "图片." + extension.lower()
    if len(name) > 40:
        suffix = "." + extension if separator and len(extension) <= 8 else name[-8:]
        return name[:29] + "…" + suffix
    return name


def failure_reason(message):
    """Only controlled, bounded diagnostics belong in chat or operation logs."""
    reason = re.sub(r"[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]", "", str(message or "")).strip()
    if (not reason.startswith(("IPP", "打印", "文件", "图片", "PDF", "转换", "合并", "请求份数", "未能", "未收到", "平台重启", "提交", "下载"))
            or re.search(r"(?i)(?:https?://|ipps?://|[a-z]:[\\/]|\\\\[^\\\s]+\\|(?:^|[\s：:（(])/(?!\s|$)|token|secret|cookie|password|authorization|api[_-]?key)", reason)):
        return "暂无详细原因，请联系管理员检查插件日志。"
    return reason[:200]


def status_text(job):
    phrases = {
        "receiving": "正在收文件，请稍等。",
        "pending": f"等待确认，尚未打印。\n打印一份：打印{file_reference(job)}",
        "queued": f"已确认打印 {job['copies']} 份，正在等待打印机。\n先不要重复发送文件。",
        "leased": "正在准备打印，请稍等。",
        "started": "正在发送到打印机，请稍等，不要重复操作。",
        "submitted": "已提交打印，请到打印机旁看看是否出纸。",
        "failed": "打印失败\n原因：" + failure_reason(job.get("message")) + "\n\n处理原因后再重新发送，不会自动重打。",
        "unknown": "打印结果待核查\n" + failure_reason(job.get("message")) + "\n\n请先核查打印机队列和是否出纸，不要重复发送。",
        "cancelled": "已取消，这份文件不会继续提交打印。",
        "archived": "已结束核查，不会重新打印。",
    }
    mode = SIDE_LABELS.get(job.get("sides", "default"), "未知")
    if job.get("auto_sides") is True:
        orientation = {"portrait": "竖向", "landscape": "横向"}.get(job.get("print_orientation"), "方向待核查")
        mode += f" · 自动识别为{orientation}，按左右翻阅"
    bundle = bundle_description(job)
    if bundle and job["status"] == "cancelled":
        phrases["cancelled"] = "已取消整组合并任务，这些图片都不会继续提交打印。"
    return f"{file_heading(job)}：{display_filename(job)}\n打印方式：{mode}\n" + (bundle + "\n" if bundle else "") + "\n" + phrases.get(job["status"], "请查看打印机，或联系家人帮忙检查。")


def bundle_description(job):
    count = job.get("bundle_image_count")
    if not job.get("bundle_leader") or type(count) is not int or count < 2:
        return ""
    return (f"本批 {count} 张图片已合并，共用同一个双面任务。\n"
            + ("第1张正面，第2张背面。" if count == 2 else "按发送顺序打印；每份奇数张的最后背面留白。"))


def welcome_text():
    return ("把照片或 PDF 文件发给我。\n"
            "收到提示后回复“打印”即可；Telegram 也可点“打印一份”或“双面打印”。\n"
            "不想打印回复“取消”，想看进度回复“进度”。\n"
            "多文件都收齐后回复“全部打印”；需要双面可回复“双面打印”或“全部双面打印”。\n"
            "全部不要可回复“全部取消”；已开始提交的任务不能保证远程取消。\n"
            "只选文件1：打印文件1 / 取消文件1 / 查看文件1；打印文件1两份才是两份。\n"
            "5分钟没收到新文件，下次收件从文件1开始；上述短口令只选当前批，旧批回复“任务”查看对应口令。\n"
            "双面会自动识别横竖方向，按左右翻阅选择翻边；也可回复“长边双面打印”或“短边双面打印”手动指定。\n"
            "横竖混合的 PDF 请手动指定长边或短边；旧文件方向未知时请重新发送。不支持时明确提示，不改单面。\n"
            "两张图片都收到后回复“全部双面打印”：第1张正面、第2张背面；不同批次不混合。\n"
            "Telegram 可点“本批双面打印”，只处理按钮所在批次的待打印文件，不会选中其他批次。\n"
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
    if batch_cancel_command(text):
        return True
    if print_command(text):
        return True
    short = short_command(text)
    if short:
        return short["action"] in {"print", "cancel"}
    simple = simple_command(text)
    if simple:
        return simple[0] in {"print", "cancel"}
    return bool(re.match(r"^(?:/(?:print|print_cancel)(?:@\w+)?(?:\s|$)|(?:打印|单面打印|双面打印|长边双面打印|短边双面打印|取消)\s+)", str(text or "").strip()))
