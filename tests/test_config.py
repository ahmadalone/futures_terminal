import pytest
import os
from pathlib import Path
from utils.config import AppConfig

def test_load_config_defaults():
    config = AppConfig()
    assert config.database.path == "trading_terminal.db"
    assert config.logging.level == "DEBUG"
    assert config.defaults.leverage == 1

def test_load_from_yaml(tmp_path):
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text("database:\n  path: test.db\nlogging:\n  level: INFO")
    config = AppConfig.from_yaml(str(yaml_file))
    assert config.database.path == "test.db"
    assert config.logging.level == "INFO"