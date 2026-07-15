import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional

def setup_logger(
    name: str = "futures_terminal",
    level: str = "DEBUG",
    log_file: Optional[str] = None,
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
    fmt: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt: str = "%Y-%m-%d %H:%M:%S",
) -> logging.Logger:
    """
    Configure and return the root application logger.
    Handlers: console + rotating file (if log_file provided).
    """
    logger = logging.getLogger(name)
    # Avoid adding handlers multiple times
    if logger.hasHandlers():
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter(fmt, datefmt=datefmt)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(fmt, datefmt=datefmt)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger