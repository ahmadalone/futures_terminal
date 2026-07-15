"""
Async lock context manager for protecting shared mutable state.
"""
import asyncio

class AsyncLockGuard:
    """Usage: async with lock: ..."""
    def __init__(self, lock: asyncio.Lock):
        self.lock = lock

    async def __aenter__(self):
        await self.lock.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        self.lock.release()