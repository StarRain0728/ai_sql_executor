import logging
from logging.handlers import RotatingFileHandler
import os

from core.config import get_settings


def setup_logger():
    settings = get_settings()
    app_logger = logging.getLogger("app")

    if app_logger.hasHandlers():
        return app_logger

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    handler = RotatingFileHandler(os.path.join(settings.log_dir, "app.log"),
                                  maxBytes=settings.log_max_bytes,
                                  backupCount=settings.log_backup_count,
                                  encoding=settings.log_encoding)

    handler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(level=settings.log_level)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(settings.log_level)
    root_logger.addHandler(console)
    root_logger.addHandler(handler)

    app_logger.setLevel(settings.log_level)
    app_logger.propagate = True

    return app_logger
