from pathlib import Path
import logging
from typing import Optional

__all__ = ["get_logger"]


def get_logger(name: str = "text2sql", filename: str = "rag.log", level: int = logging.INFO) -> logging.Logger:
    """Return a configured file logger writing to <repo>/logs/<filename>.

    Creates the logs directory if missing and configures a single FileHandler
    per logger name (idempotent).
    """
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if not logger.handlers:
        fh = logging.FileHandler(logs_dir / filename, encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    logger.setLevel(level)
    return logger
