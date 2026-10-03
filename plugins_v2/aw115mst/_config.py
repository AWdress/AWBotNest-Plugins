"""AW115MST configuration, independent of the platform implementation."""
from __future__ import annotations

DEFAULTS = {
    "cookie": "", "target_pid": "0", "input_dir": "待检测", "rapid_dir": "可秒传",
    "non_rapid_dir": "待秒传", "use_copy": True, "keep_structure": True,
    "check_only": False, "delete_after_rapid": False, "delete_source_after_rapid": False,
    "upload_enabled": False, "delete_after_upload": False, "include_extensions": "",
    "exclude_extensions": ".txt,.log,.tmp,.part,.crdownload,.!qb,.!ut,.download,.aria2,.mp",
    "min_size_mb": 0, "max_size_gb": 100, "hash_chunk_mb": 1, "stable_seconds": 5,
    "watch_enabled": False, "watch_interval_seconds": 5, "schedule_enabled": False,
    "interval_minutes": 30, "recheck_enabled": False, "max_recheck_times": 10,
    "notify": False, "request_timeout": 30, "telegram_control": False,
    "telegram_admin_ids": "", "qr_app": "qandroid",
}


def normalize(values):
    result = dict(DEFAULTS)
    for key in result:
        if key in values and values[key] is not None:
            result[key] = values[key]
    for key, default in DEFAULTS.items():
        value = result[key]
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValueError(f"{key} 必须是开关值")
        elif isinstance(default, int):
            if isinstance(value, bool):
                raise ValueError(f"{key} 必须是数值")
            try:
                number = float(value)
                if not number.is_integer():
                    raise ValueError()
                result[key] = int(number)
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f"{key} 必须是整数") from None
        else:
            if not isinstance(value, str):
                raise ValueError(f"{key} 必须是文字")
            result[key] = value.strip()
    bounds = {
        "min_size_mb": (0, 102400), "max_size_gb": (0, 102400), "hash_chunk_mb": (1, 16),
        "stable_seconds": (0, 3600), "watch_interval_seconds": (5, 3600),
        "interval_minutes": (1, 10080), "max_recheck_times": (0, 10000),
        "request_timeout": (5, 300),
    }
    for key, (low, high) in bounds.items():
        if not low <= result[key] <= high:
            raise ValueError(f"{key} 范围应为 {low}–{high}")
    if not result["target_pid"].isdigit():
        raise ValueError("115 目标目录 ID 必须是非负整数")
    if result["qr_app"] not in {"qandroid", "115android", "tv", "ios", "web", "harmony"}:
        raise ValueError("不支持的扫码客户端")
    if result["check_only"] and any(result[key] for key in (
        "delete_after_rapid", "delete_source_after_rapid", "delete_after_upload")):
        raise ValueError("不处理本地文件模式不能同时开启删除")
    result["min_size"] = result["min_size_mb"] * 1024 ** 2
    result["max_size"] = result["max_size_gb"] * 1024 ** 3
    if result["max_size"] and result["min_size"] > result["max_size"]:
        raise ValueError("最小文件大小不能大于最大文件大小")
    return result
