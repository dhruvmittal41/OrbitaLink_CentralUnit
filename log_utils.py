import logging
from datetime import datetime

LOG_HISTORY_LIMIT = 500

event_log = []          # in-memory log buffer
sio_instance = None     # injected from server.py


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

        # Push to frontend (non-blocking)
        if sio_instance:
            sio_instance.start_background_task(
                sio_instance.emit,
                "log_update",
                entry
            )


def setup_logging(sio):
    global sio_instance
    sio_instance = sio

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)

    # File
    fh = logging.FileHandler("data/app.log")
    fh.setFormatter(formatter)

    # Socket.IO handler
    sh = SocketIOLogHandler()
    sh.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.addHandler(sh)

    return logging.getLogger("CU")
