"""Core application utilities, configuration, and logging."""

from backend.app.core.config import get_settings, settings
from backend.app.core.logging import get_logger, setup_logging

__all__ = ["get_logger", "get_settings", "settings", "setup_logging"]
