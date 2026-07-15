"""
Dynamic strategy loader with hot‑reload support via watchdog.
"""
import os
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Type, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from strategies.base import BaseStrategy
from utils.logger import setup_logger

logger = setup_logger(__name__)

class StrategyLoader:
    """
    Scans a directory for Python files, imports classes that inherit from BaseStrategy,
    and provides a registry of available strategies. Listens for file changes to reload.
    """
    def __init__(self, strategies_dir: str = "strategies"):
        self.strategies_dir = Path(strategies_dir)
        self.registry: Dict[str, Type[BaseStrategy]] = {}
        self.observer = Observer()
        self._load_all()
        self._start_watching()

    def _load_all(self):
        """Import all strategy modules from the folder."""
        if not self.strategies_dir.exists():
            return
        for file in self.strategies_dir.iterdir():
            if file.suffix == ".py" and file.name != "__init__.py" and file.name != "base.py":
                self._import_module(file.stem)

    def _import_module(self, module_name: str):
        try:
            full_path = self.strategies_dir / f"{module_name}.py"
            spec = importlib.util.spec_from_file_location(module_name, full_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)
            # Find all BaseStrategy subclasses
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, BaseStrategy) and
                    attr is not BaseStrategy):
                    self.registry[attr_name] = attr
                    logger.info(f"Loaded strategy: {attr_name}")
        except Exception as e:
            logger.error(f"Failed to import {module_name}: {e}")

    def _unload_module(self, module_name: str):
        if module_name in sys.modules:
            del sys.modules[module_name]
        # Remove any strategies from registry that came from that module
        # (We need to track which classes belong to which module; for simplicity,
        #  we'll re‑load the whole module on change and rebuild registry.)
        self.registry = {}
        self._load_all()

    def _start_watching(self):
        if not self.strategies_dir.exists():
            return
        event_handler = _StrategyFileHandler(self)
        self.observer.schedule(event_handler, str(self.strategies_dir), recursive=False)
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()

    def get_strategy_class(self, name: str) -> Optional[Type[BaseStrategy]]:
        return self.registry.get(name)


class _StrategyFileHandler(FileSystemEventHandler):
    def __init__(self, loader: StrategyLoader):
        super().__init__()
        self.loader = loader

    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            module_name = Path(event.src_path).stem
            logger.info(f"Detected change in {module_name}, reloading...")
            self.loader._unload_module(module_name)

    def on_created(self, event):
        if event.src_path.endswith(".py"):
            module_name = Path(event.src_path).stem
            logger.info(f"New strategy file {module_name} detected, loading...")
            self.loader._import_module(module_name)