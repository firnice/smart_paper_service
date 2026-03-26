"""Centralised logger for the application.

Every module should use:

    from app.core.logger import logger

This keeps the logger name in one place so it is easy to swap to a
different logger (e.g. structlog) or change the name later.
"""

import logging

logger = logging.getLogger("uvicorn.error")
