"""
Simple async‑aware function profiler.
"""
import time
import functools
from contextlib import asynccontextmanager
from utils.logger import setup_logger

logger = setup_logger("profiler")

def profile(func):
    """Decorator that logs execution time of the function."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.monotonic()
        try:
            result = await func(*args, **kwargs)
        finally:
            elapsed = (time.monotonic() - start) * 1000
            logger.debug(f"{func.__qualname__} took {elapsed:.2f}ms")
        return result
    return wrapper

class Profiler:
    """Context manager to measure a block of code."""
    def __init__(self, name="block"):
        self.name = name
        self.start = None

    async def __aenter__(self):
        self.start = time.monotonic()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        elapsed = (time.monotonic() - self.start) * 1000
        logger.debug(f"Profiler [{self.name}] took {elapsed:.2f}ms")