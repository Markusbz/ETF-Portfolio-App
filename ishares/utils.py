from pathlib import Path
from .. import config
import logging, os

CACHE_DIR = config.RAW_DATA_DIR
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def get_logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(name)s: %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    return log
