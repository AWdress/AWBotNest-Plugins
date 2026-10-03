"""Bounded local file operations for AW115MST; no Telegram or cloud access."""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, replace
import hashlib
import os
from pathlib import Path
import re
import stat
import threading
from typing import Any, Callable, Mapping


class UnsafePathError(ValueError):
    """A configured path or filesystem entry leaves the allowed scope."""


class FileChangedError(RuntimeError):
    """The scanned/hashed file is no longer the file being processed."""


class _OperationStopped(Exception):
    pass


@dataclass(frozen=True)
class Roots:
    input_dir: Path
    rapid_dir: Path
    non_rapid_dir: Path


@dataclass(frozen=True)
class FileSnapshot:
    size: int
    mtime_ns: int
    ctime_ns: int
    device: int
    inode: int
    sha1: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _snapshot(info: os.stat_result) -> FileSnapshot:
    return FileSnapshot(info.st_size, info.st_mtime_ns, info.st_ctime_ns,
                        info.st_dev, info.st_ino)


def _expected(value: FileSnapshot | Mapping[str, Any]) -> FileSnapshot:
    return value if isinstance(value, FileSnapshot) else FileSnapshot(**dict(value))


def _same(actual: FileSnapshot, expected: FileSnapshot) -> bool:
    return replace(actual, sha1="") == replace(expected, sha1="")


def _is_link(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _absolute(path: str | os.PathLike[str]) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _no_links(path: Path) -> None:
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if _is_link(info):
            raise UnsafePathError(f"不处理符号链接或重解析点：{component}")


def _root(path: str | os.PathLike[str]) -> Path:
    absolute = _absolute(path)
    _no_links(absolute)
    result = absolute.resolve(strict=False)
    _no_links(result)
    if result == Path(result.anchor) or result == _absolute(Path.home()).resolve(strict=False):
        raise UnsafePathError("目录不能是文件系统根目录或用户主目录")
    if result.exists() and not result.is_dir():
        raise UnsafePathError(f"配置目录实际是文件：{result}")
    return result


def _overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def validate_roots(data_dir: str | os.PathLike[str], config: Mapping[str, Any]) -> Roots:
    """Resolve relative config paths under data_dir, without creating directories."""
    base = _absolute(data_dir)
    _no_links(base)
    values = []
    for key, default in (("input_dir", "待检测"), ("rapid_dir", "可秒传"),
                         ("non_rapid_dir", "待秒传")):
        value = config.get(key, default)
        if not isinstance(value, (str, os.PathLike)) or not os.fspath(value).strip():
            raise UnsafePathError(f"目录配置不能为空：{key}")
        path = Path(os.path.expanduser(os.fspath(value)))
        # Neither C:folder nor \folder is relative to the plugin data directory.
        if (path.drive or path.root) and not path.is_absolute():
            raise UnsafePathError(f"目录必须使用完整绝对路径或普通相对路径：{key}")
        values.append(_root(path if path.is_absolute() else base / path))
    for index, first in enumerate(values):
        for second in values[index + 1:]:
            if _overlap(first, second):
                raise UnsafePathError("输入、可秒传和待秒传目录不能相同或互相嵌套")
    return Roots(*values)


def _file_path(path: str | os.PathLike[str], root: str | os.PathLike[str]) -> tuple[Path, Path]:
    allowed = _root(root)
    absolute = _absolute(path)
    if absolute == allowed or allowed not in absolute.parents:
        raise UnsafePathError(f"文件不在指定目录内：{absolute}")
    _no_links(absolute)
    return absolute, allowed


def signature(path: str | os.PathLike[str], root: str | os.PathLike[str]) -> FileSnapshot:
    file_path, _ = _file_path(path, root)
    info = file_path.lstat()
    if _is_link(info) or not stat.S_ISREG(info.st_mode):
        raise UnsafePathError(f"只处理普通文件：{file_path}")
    result = _snapshot(info)
    if os.name != "nt":
        return result
    # Windows 3.13 lstat may expose creation time as ctime, whereas fstat
    # exposes metadata change time after utime. Use handle-based snapshots
    # consistently rather than discarding the real change-time guard.
    descriptor = os.open(file_path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        opened = os.fstat(descriptor)
        opened_snapshot = _snapshot(opened)
        if (not stat.S_ISREG(opened.st_mode) or _is_link(opened) or
                replace(result, ctime_ns=opened_snapshot.ctime_ns) != opened_snapshot):
            raise FileChangedError(f"文件在读取快照前被替换或改变：{file_path}")
        _no_links(file_path)
        return opened_snapshot
    finally:
        os.close(descriptor)


def _extensions(raw: Any) -> set[str]:
    items = raw if isinstance(raw, (list, tuple, set)) else re.split(r"[,;\s]+", str(raw or ""))
    return {"." + str(item).strip().lower().lstrip(".") for item in items if str(item).strip()}


def scan_candidates(root: str | os.PathLike[str], config: Mapping[str, Any] | None = None,
                    recursive: bool | None = None) -> list[Path]:
    """Scan regular files without following links; call in a worker for large trees."""
    config = config or {}
    filters = config.get("filters", config)
    recursive = bool(config.get("recursive", True)) if recursive is None else recursive
    allowed = _root(root)
    if not allowed.exists():
        return []
    include = _extensions(filters.get("include_extensions", []))
    exclude = _extensions(filters.get("exclude_extensions", []))
    minimum = max(0, int(filters.get("min_size", 0)))
    maximum = int(filters.get("max_size", 0) or 0)
    skip_hidden = bool(config.get("skip_hidden", True))
    stack = [allowed]
    candidates = []
    while stack:
        directory = stack.pop()
        _no_links(directory)
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    info = entry.stat(follow_symlinks=False)
                    if _is_link(info) or (skip_hidden and entry.name.startswith((".", "~"))):
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        if recursive:
                            stack.append(Path(entry.path))
                        continue
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    suffix = Path(entry.name).suffix.lower()
                    if suffix in exclude or (include and suffix not in include):
                        continue
                    if info.st_size < minimum or (maximum > 0 and info.st_size > maximum):
                        continue
                    candidates.append(Path(entry.path))
                except (OSError, UnsafePathError):
                    continue
    return sorted(candidates, key=lambda path: os.path.normcase(str(path)))


def _check_stop(stop: threading.Event) -> None:
    if stop.is_set():
        raise _OperationStopped()


async def _run_worker(function: Callable, *args, return_committed: bool = False):
    """Drain cancelled workers; expose already committed mutations for checkpoints.

    A successful mutating worker may have committed just before cancellation.
    Its caller must persist that result, then honor task.cancelling() before
    starting another phase. Read-only operations always propagate cancellation.
    """
    stop = threading.Event()
    task = asyncio.create_task(asyncio.to_thread(function, *args, stop))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        stop.set()
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                stop.set()
            except Exception:
                break
        if task.done() and not task.cancelled():
            error = task.exception()
            if error is None and return_committed:
                return task.result()
        raise


def _open_source(path: Path, root: Path, expected: FileSnapshot):
    current = signature(path, root)
    if not _same(current, expected):
        raise FileChangedError(f"文件在处理前已改变：{path}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    file = os.fdopen(descriptor, "rb")
    try:
        if not _same(_snapshot(os.fstat(file.fileno())), expected):
            raise FileChangedError(f"打开的文件不是扫描时的文件：{path}")
        _no_links(path)
        return file
    except BaseException:
        file.close()
        raise


def _unchanged(path: Path, root: Path, file, expected: FileSnapshot) -> None:
    if (not _same(_snapshot(os.fstat(file.fileno())), expected) or
            not _same(signature(path, root), expected)):
        raise FileChangedError(f"文件在处理过程中改变：{path}")


def _hash_worker(path: Path, root: Path, expected: FileSnapshot, chunk_size: int,
                 stop: threading.Event) -> tuple[str, FileSnapshot]:
    _check_stop(stop)
    digest = hashlib.sha1()
    with _open_source(path, root, expected) as file:
        while True:
            _check_stop(stop)
            chunk = file.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
        _unchanged(path, root, file, expected)
    result = digest.hexdigest().upper()
    if expected.sha1 and result != expected.sha1.upper():
        raise FileChangedError(f"文件内容与已检测的 SHA1 不同：{path}")
    return result, replace(expected, sha1=result)


async def hash_file(path: str | os.PathLike[str], root: str | os.PathLike[str],
                    expected: FileSnapshot | Mapping[str, Any] | None = None,
                    chunk_size: int = 1024 * 1024) -> tuple[str, FileSnapshot]:
    file_path, allowed = _file_path(path, root)
    snapshot = signature(file_path, allowed) if expected is None else _expected(expected)
    if not 0 < chunk_size <= 16 * 1024 * 1024:
        raise ValueError("哈希块大小必须在 1 字节到 16 MiB 之间")
    return await _run_worker(_hash_worker, file_path, allowed, snapshot, chunk_size)


def _range_worker(path: Path, root: Path, expected: FileSnapshot, start: int, end: int,
                  stop: threading.Event) -> bytes:
    _check_stop(stop)
    with _open_source(path, root, expected) as file:
        file.seek(start)
        result = file.read(end - start + 1)
        _check_stop(stop)
        _unchanged(path, root, file, expected)
    if len(result) != end - start + 1:
        raise FileChangedError(f"二次验证范围未读足：{path}")
    return result


async def read_range(path: str | os.PathLike[str], root: str | os.PathLike[str],
                     expected: FileSnapshot | Mapping[str, Any], range_spec: str) -> bytes:
    file_path, allowed = _file_path(path, root)
    snapshot = _expected(expected)
    match = re.fullmatch(r"(\d+)-(\d+)", range_spec)
    if not match:
        raise ValueError("二次验证范围格式必须为 start-end")
    start, end = map(int, match.groups())
    if not 0 <= start <= end < snapshot.size or end - start + 1 > 8 * 1024 * 1024:
        raise ValueError("二次验证范围越界或超过 8 MiB")
    return await _run_worker(_range_worker, file_path, allowed, snapshot, start, end)


def _make_directory(path: Path, root: Path) -> None:
    if path != root and root not in path.parents:
        raise UnsafePathError("输出目录越界")
    _no_links(path)
    path.mkdir(parents=True, exist_ok=True)
    _no_links(path)
    if not path.is_dir():
        raise UnsafePathError(f"输出路径不是目录：{path}")


def _reserve(path: Path, root: Path) -> tuple[Path, int]:
    _make_directory(path.parent, root)
    for counter in range(100000):
        candidate = path if counter == 0 else path.with_name(f"{path.stem}_{counter}{path.suffix}")
        _no_links(candidate.parent)
        try:
            descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                 getattr(os, "O_BINARY", 0), 0o600)
            return candidate, descriptor
        except FileExistsError:
            continue
    raise FileExistsError("输出文件同名冲突过多")


def _same_owner(info: os.stat_result, owner: os.stat_result) -> bool:
    return (info.st_dev == owner.st_dev and info.st_ino == owner.st_ino and
            (owner.st_ino != 0 or
             getattr(info, "st_birthtime_ns", info.st_ctime_ns) ==
             getattr(owner, "st_birthtime_ns", owner.st_ctime_ns)))


def _remove_owned(path: Path, root: Path, owner: os.stat_result) -> None:
    try:
        _file_path(path, root)
        info = path.lstat()
        if not _is_link(info) and _same_owner(info, owner):
            path.unlink()
    except (FileNotFoundError, UnsafePathError):
        pass


def _cleanup_empty(parent: Path, root: Path) -> None:
    while parent != root and root in parent.parents:
        try:
            _no_links(parent)
            parent.rmdir()
        except (OSError, UnsafePathError):
            break
        parent = parent.parent


def _transfer_worker(source: Path, source_root: Path, target_root: Path,
                     expected: FileSnapshot, use_copy: bool, keep_structure: bool,
                     stop: threading.Event) -> Path:
    target = None
    owner = None
    removed = False
    try:
        _check_stop(stop)
        relative = source.relative_to(source_root) if keep_structure else Path(source.name)
        with _open_source(source, source_root, expected) as reader:
            target, descriptor = _reserve(target_root / relative, target_root)
            owner = os.fstat(descriptor)
            digest = hashlib.sha1()
            with os.fdopen(descriptor, "wb") as writer:
                while True:
                    _check_stop(stop)
                    chunk = reader.read(1024 * 1024)
                    if not chunk:
                        break
                    writer.write(chunk)
                    digest.update(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            _check_stop(stop)
            _unchanged(source, source_root, reader, expected)
            if expected.sha1 and digest.hexdigest().upper() != expected.sha1.upper():
                raise FileChangedError(f"文件内容在整理前改变：{source}")
        _no_links(target)
        target_info = target.lstat()
        if not _same_owner(target_info, owner):
            raise FileChangedError("输出文件在整理过程中被替换")
        os.utime(target, ns=(target_info.st_atime_ns, expected.mtime_ns))
        # Verify the completed destination before a move may remove its source.
        target_snapshot = signature(target, target_root)
        if not _same_owner(target.lstat(), owner) or target_snapshot.size != expected.size:
            raise FileChangedError("输出文件在整理完成前被替换或改变")
        target_snapshot = replace(target_snapshot, sha1=digest.hexdigest().upper())
        _hash_worker(target, target_root, target_snapshot, 1024 * 1024, stop)
        if not use_copy:
            _hash_worker(source, source_root, replace(expected, sha1=target_snapshot.sha1),
                         1024 * 1024, stop)
        _check_stop(stop)
        if not _same(signature(source, source_root), expected):
            raise FileChangedError(f"源文件在整理完成前改变：{source}")
        if not _same(signature(target, target_root), target_snapshot):
            raise FileChangedError("输出文件在验证完成前改变")
        _check_stop(stop)
        if not use_copy:
            source.unlink()
            removed = True
            _cleanup_empty(source.parent, source_root)
        return target
    except BaseException:
        if target is not None and owner is not None and not removed:
            _remove_owned(target, target_root, owner)
        raise


async def safe_transfer(source: str | os.PathLike[str], source_root: str | os.PathLike[str],
                        target_root: str | os.PathLike[str],
                        expected: FileSnapshot | Mapping[str, Any], *, use_copy: bool = False,
                        keep_structure: bool = True) -> Path:
    source, source_root = _file_path(source, source_root)
    target_root = _root(target_root)
    if _overlap(source_root, target_root):
        raise UnsafePathError("源目录和目标目录不能相同或互相嵌套")
    return await _run_worker(_transfer_worker, source, source_root, target_root,
                             _expected(expected), use_copy, keep_structure, return_committed=True)


def _remove_worker(path: Path, root: Path, expected: FileSnapshot,
                   stop: threading.Event) -> None:
    _hash_worker(path, root, expected, 1024 * 1024, stop)
    _check_stop(stop)
    if not _same(signature(path, root), expected):
        raise FileChangedError(f"删除前文件已改变：{path}")
    _check_stop(stop)
    path.unlink()
    _cleanup_empty(path.parent, root)


async def remove_file(path: str | os.PathLike[str], root: str | os.PathLike[str],
                      expected: FileSnapshot | Mapping[str, Any]) -> None:
    file_path, allowed = _file_path(path, root)
    await _run_worker(_remove_worker, file_path, allowed, _expected(expected), return_committed=True)
