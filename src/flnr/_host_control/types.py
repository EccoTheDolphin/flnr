from typing import Protocol


class HostTerminationAttachment(Protocol):
    async def deactivate(self) -> None: ...
