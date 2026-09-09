"""憨憨插件的原生异步存储缓存。"""

from __future__ import annotations

import asyncio

_state: dict = {}
_tasks: set[asyncio.Task] = set()


async def initialize(ctx) -> None:
    _state.clear()
    _state.update(dict(await ctx.storage.items()))


def get(ctx, key, default=None):
    return _state.get(key, default)


def set(ctx, key, value) -> None:
    _state[key] = value
    task = ctx.create_task(ctx.storage.set(key, value), name=f"hhan-storage:{key}")
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def close() -> None:
    if _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
    _tasks.clear()
    _state.clear()
