"""Internal asyncio helper utilities."""

import asyncio
from typing import Any


async def _cancel_tasks(*tasks: asyncio.Task[Any]) -> None:
    if not tasks:
        return

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)
