"""
Async time‑to‑live (TTL) + LRU cache for async functions.
"""
import asyncio
import time
from collections import OrderedDict
from functools import wraps

class AsyncTTLCache:
    """
    Size‑limited, TTL‑enforced cache for async functions.
    """
    def __init__(self, maxsize=128, ttl=60.0):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key):
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if time.monotonic() > expiry:
                del self._cache[key]
                return None
            # Move to end to implement LRU
            self._cache.move_to_end(key)
            return value

    async def set(self, key, value):
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, time.monotonic() + self.ttl)
            if len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    async def delete(self, key):
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self):
        async with self._lock:
            self._cache.clear()

def async_cached(maxsize=128, ttl=60.0):
    """Decorator to cache async function results."""
    cache = AsyncTTLCache(maxsize=maxsize, ttl=ttl)
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = (args, frozenset(kwargs.items()))
            result = await cache.get(key)
            if result is not None:
                return result
            result = await func(*args, **kwargs)
            await cache.set(key, result)
            return result
        wrapper.cache = cache
        return wrapper
    return decorator