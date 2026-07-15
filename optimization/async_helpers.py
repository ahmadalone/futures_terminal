"""
Async helpers: task pool, throttle, batched execution.
"""
import asyncio
from typing import List, Coroutine, Any, Callable

class TaskPool:
    """Limit concurrent asyncio tasks."""
    def __init__(self, max_concurrency: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.tasks = set()

    async def submit(self, coro: Coroutine) -> Any:
        async def wrapper():
            async with self.semaphore:
                return await coro
        task = asyncio.create_task(wrapper())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def join(self):
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

def async_throttle(wait_seconds: float):
    """Decorator that limits calls to once per wait_seconds."""
    def decorator(func):
        last = 0
        lock = asyncio.Lock()
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal last
            async with lock:
                now = time.monotonic()
                if now - last < wait_seconds:
                    return None
                last = now
                return await func(*args, **kwargs)
        return wrapper
    return decorator

async def batched(coros: List[Coroutine], batch_size: int = 5) -> List:
    """Run coroutines in batches to limit memory usage."""
    results = []
    for i in range(0, len(coros), batch_size):
        batch = coros[i:i+batch_size]
        batch_results = await asyncio.gather(*batch, return_exceptions=True)
        results.extend(batch_results)
    return results