import logging
import os
from datetime import datetime

LOG_HISTORY_LIMIT = 500
LOG_DIR = "data"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

event_log = []
sio_instance = None
_root_configured = False


class SocketIOLogHandler(logging.Handler):
    def emit(self, record):
        global event_log

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        message = record.getMessage()

        entry = {
            "time": timestamp,
            "level": record.levelname,
            "source": record.name,
            "message": message
        }

        event_log.append(entry)
        if len(event_log) > LOG_HISTORY_LIMIT:
            event_log.pop(0)

        if sio_instance:
            sio_instance.start_background_task(
                sio_instance.emit,
                "log_update",
                entry
            )


def setup_logging(sio):
    """
    Configure root logger ONCE.
    All module loggers will inherit these handlers.
    """
    global sio_instance, _root_configured
    sio_instance = sio

    if _root_configured:
        return get_logger("CU")

    os.makedirs(LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # --- Console ---
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)

    # --- File ---
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(formatter)

    # --- Socket.IO ---
    sh = SocketIOLogHandler()
    sh.setFormatter(formatter)

    root.handlers.clear()
    root.addHandler(ch)
    root.addHandler(fh)
    root.addHandler(sh)

    _root_configured = True
    return get_logger("CU")


def get_logger(name: str) -> logging.Logger:
    """
    Return a namespaced logger under CU.*
    Example:
        get_logger("scheduler") -> CU.scheduler
    """
    if not name.startswith("CU"):
        name = f"CU.{name}"

    return logging.getLogger(name)
