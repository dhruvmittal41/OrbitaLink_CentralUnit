import logging
import os
from datetime import datetime

LOG_HISTORY_LIMIT = 500
LOG_DIR = "data"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

event_log = []
sio_instance = None


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
    global sio_instance
    sio_instance = sio

    # ✅ ENSURE DIRECTORY EXISTS
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)

    # File (now safe)
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(formatter)

    # Socket.IO
    sh = SocketIOLogHandler()
    sh.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.addHandler(sh)

    return logging.getLogger("CU")
