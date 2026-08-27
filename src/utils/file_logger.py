"""
File-based logger — writes to ~/.facebook-notification/access.log and error.log
Replaces DB-based logging to keep SQLite light.
"""
import os
import logging
import threading
from src.config.constants import DATA_DIR

_lock = threading.Lock()
_initialized = False
_access_logger = None
_error_logger = None


def _init():
    global _initialized, _access_logger, _error_logger
    if _initialized:
        return
    with _lock:
        if _initialized:
            return
        os.makedirs(DATA_DIR, exist_ok=True)

        def _make(name, path):
            lg = logging.getLogger(name)
            if lg.handlers:
                return lg
            lg.setLevel(logging.DEBUG)
            h = logging.FileHandler(path, encoding="utf-8")
            h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
            lg.addHandler(h)
            lg.propagate = False
            return lg

        _access_logger = _make("fb.access", os.path.join(DATA_DIR, "access.log"))
        _error_logger  = _make("fb.error",  os.path.join(DATA_DIR, "error.log"))
        _initialized = True


def log_access(message: str, module: str = "APP"):
    _init()
    _access_logger.info(f"[{module}] {message}")


def log_error(message: str, module: str = "APP"):
    _init()
    _error_logger.error(f"[{module}] {message}")
    # errors also go to access log for timeline view
    _access_logger.error(f"[{module}] {message}")


def add_log(message: str, level: str = "INFO", module: str = "APP"):
    """Drop-in replacement for repository.add_log — writes to file, returns 0 (no DB row id)."""
    _init()
    if not message:
        return 0
    lvl = (level or "INFO").upper()
    if lvl in ("ERROR", "CRITICAL", "WARNING", "WARN"):
        log_error(message, module)
    else:
        log_access(message, module)
    return 0


def get_log_paths() -> dict:
    return {
        "access": os.path.join(DATA_DIR, "access.log"),
        "error":  os.path.join(DATA_DIR, "error.log"),
    }
