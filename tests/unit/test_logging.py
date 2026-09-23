"""Unit tests for logging configuration."""

import logging

from backend.app.core.logging import get_logger, setup_logging


def test_setup_logging():
    """Verify that logging setup executes cleanly with given log level."""
    setup_logging(log_level="DEBUG")
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG

    setup_logging(log_level="INFO")
    assert root_logger.level == logging.INFO


def test_get_logger():
    """Verify logger instantiation."""
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"
