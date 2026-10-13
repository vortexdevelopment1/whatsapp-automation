import asyncio
from typing import Dict, Any


class ConversationLockManager:
    """In-memory per-lead conversation lock manager to prevent race conditions during message bursts."""

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def get_lock(self, key: Any) -> asyncio.Lock:
        k = str(key)
        async with self._global_lock:
            if k not in self._locks:
                self._locks[k] = asyncio.Lock()
            return self._locks[k]

    async def acquire(self, key: Any, timeout: float = 5.0) -> bool:
        lock = await self.get_lock(key)
        try:
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def release(self, key: Any) -> None:
        lock = await self.get_lock(key)
        if lock.locked():
            lock.release()


conversation_lock_manager = ConversationLockManager()
