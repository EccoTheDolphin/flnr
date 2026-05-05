import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from ._async_utils import _cancel_tasks

_T = TypeVar("_T")


class _TaskLedger:
    def __init__(self) -> None:
        self._tasks: list[asyncio.Task[Any]] = []

    def register(self, task: asyncio.Task[_T]) -> asyncio.Task[_T]:
        self._tasks.append(task)
        return task

    def create_task(
        self,
        coro: Coroutine[Any, Any, _T],
        *,
        name: str,
    ) -> asyncio.Task[_T]:
        return self.register(asyncio.create_task(coro, name=name))

    async def cancel_all(self) -> None:
        await _cancel_tasks(*self._tasks)
