import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def get_logger(filename: str = "g-tracker-fastapi") -> logging.Logger:
    filename = f"{filename}.log" if not filename.endswith(".log") else filename
    Path("logs").mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(filename)
    log.setLevel(logging.INFO)
    format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    rotateHandler = TimedRotatingFileHandler(
        Path("logs") / filename,
        when="midnight",
        backupCount=3,
    )
    rotateHandler.setFormatter(format)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(format)
    log.addHandler(rotateHandler)
    log.addHandler(stream)
    return log
