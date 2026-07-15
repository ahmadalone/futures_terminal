"""
PluginManager – discovers, loads, and manages plugin instances.
"""
import json
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional
from plugins.base import PluginBase
from plugins.manifest import PluginManifest
from plugins.services import ServiceRegistry
from utils.logger import setup_logger

logger = setup_logger(__name__)

class PluginManager:
    """
    Scans plugin directories, validates manifests, loads plugins,
    and provides access to running instances.
    """
    def __init__(self, services: ServiceRegistry, plugin_dirs: List[str] = None):
        self.services = services
        self.plugin_dirs = [Path(d) for d in (plugin_dirs or ["plugins"])]
        self.plugins: Dict[str, PluginBase] = {}
        self._modules = {}

    def discover(self) -> List[PluginManifest]:
        """Scan all plugin directories and return valid manifests."""
        manifests = []
        for d in self.plugin_dirs:
            if not d.exists():
                continue
            for manifest_file in d.rglob("manifest.json"):
                try:
                    with open(manifest_file) as f:
                        data = json.load(f)
                    manifest = PluginManifest(**data)
                    # Validate that entry_point module exists
                    module_dir = manifest_file.parent
                    module_file = module_dir / f"{manifest.entry_point}.py"
                    if not module_file.exists():
                        logger.warning(f"Entry point {manifest.entry_point}.py not found in {module_dir}")
                        continue
                    manifests.append(manifest)
                except Exception as e:
                    logger.error(f"Invalid manifest in {manifest_file}: {e}")
        return manifests

    def load_plugin(self, manifest: PluginManifest) -> Optional[PluginBase]:
        """Load a single plugin by its manifest. Returns PluginBase instance."""
        try:
            # Find the module file
            for d in self.plugin_dirs:
                module_dir = d / manifest.name
                module_file = module_dir / f"{manifest.entry_point}.py"
                if module_file.exists():
                    # Import the module
                    spec = importlib.util.spec_from_file_location(manifest.entry_point, module_file)
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[manifest.entry_point] = mod
                    spec.loader.exec_module(mod)
                    # Find the class
                    plugin_class = getattr(mod, manifest.entry_point)
                    if not issubclass(plugin_class, PluginBase):
                        logger.error(f"Class {manifest.entry_point} does not inherit PluginBase")
                        return None
                    instance = plugin_class(manifest, self.services)
                    self.plugins[manifest.name] = instance
                    self._modules[manifest.name] = mod
                    logger.info(f"Loaded plugin: {manifest.name} v{manifest.version}")
                    return instance
            logger.error(f"Plugin {manifest.name} not found in any directory")
            return None
        except Exception as e:
            logger.error(f"Failed to load plugin {manifest.name}: {e}")
            return None

    def load_all(self) -> List[PluginBase]:
        """Discover and load all plugins."""
        manifests = self.discover()
        loaded = []
        for m in manifests:
            instance = self.load_plugin(m)
            if instance:
                loaded.append(instance)
        return loaded

    def unload_plugin(self, name: str):
        if name in self.plugins:
            del self.plugins[name]
        if name in self._modules:
            del sys.modules[self._modules[name].__name__]
            del self._modules[name]
        logger.info(f"Unloaded plugin {name}")

    def get_plugin(self, name: str) -> Optional[PluginBase]:
        return self.plugins.get(name)

    def list_plugins(self) -> List[str]:
        return list(self.plugins.keys())

    async def start_all(self):
        for inst in self.plugins.values():
            await inst.on_start()

    async def stop_all(self):
        for inst in self.plugins.values():
            await inst.on_stop()