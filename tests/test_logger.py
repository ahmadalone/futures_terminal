import logging
from utils.logger import setup_logger

def test_setup_logger_returns_logger():
    logger = setup_logger("test", level="DEBUG", log_file=None)
    assert isinstance(logger, logging.Logger)
    assert logger.level == logging.DEBUG

def test_logger_has_handlers():
    logger = setup_logger("test2")
    # Should have at least a console handler
    assert len(logger.handlers) > 0