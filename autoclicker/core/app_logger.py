import logging
import os
from typing import Optional


_LOGGER: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    appdata = os.getenv("APPDATA", os.path.expanduser("~"))
    log_dir = os.path.join(appdata, "AutoClicker")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "autoclicker.log")

    logger = logging.getLogger("autoclicker")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _LOGGER = logger
    return logger
