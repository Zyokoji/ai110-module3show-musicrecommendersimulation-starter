"""Logging configuration: everything goes to logs/vibematch.log; the terminal shows errors (or INFO with --verbose)."""

import logging
import os

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "vibematch.log")


def setup_logging(verbose: bool = False, log_file: str = LOG_FILE) -> logging.Logger:
    """Configure the 'vibematch' logger once; verbose=True also prints INFO messages to the terminal."""
    logger = logging.getLogger("vibematch")
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):  # avoid duplicate handlers on repeated calls
        logger.removeHandler(handler)
        handler.close()

    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO if verbose else logging.ERROR)
    console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console)
    logger.propagate = False
    return logger
