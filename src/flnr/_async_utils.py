"""Internal asyncio helper utilities."""

import asyncio
from typing import Any


async def _cancel_tasks(*tasks: asyncio.Task[Any] | None) -> None:
    live_tasks = [task for task in tasks if task is not None]

    if not live_tasks:
        return

    for task in live_tasks:
        task.cancel()

    await asyncio.gather(*live_tasks, return_exceptions=True)
