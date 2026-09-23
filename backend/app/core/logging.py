"""Centralized logging configuration for the application."""

import logging
import sys


def setup_logging(log_level: str | None = None) -> None:
    """Configure root and application loggers with formatted stream output."""
    level_name = (log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Suppress overly chatty third-party loggers if needed
    logging.getLogger("uvicorn.access").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Retrieve a configured logger by module name."""
    return logging.getLogger(name)
