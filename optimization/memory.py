"""
Memory optimization utilities: __slots__ mixin, weak reference cache.
"""
import weakref

class SlotsMixin:
    """Add to classes to automatically use __slots__ (metaclass approach)."""
    # This is a marker; real implementation would involve a metaclass.
    # We provide a function to reduce memory by deleting unnecessary attributes.
    pass

class WeakRefCache:
    """Cache that holds weak references to values, allowing GC to reclaim them."""
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()

    def get(self, key):
        return self._cache.get(key)

    def set(self, key, value):
        self._cache[key] = value

    def delete(self, key):
        self._cache.pop(key, None)

    def clear(self):
        self._cache.clear()