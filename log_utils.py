from datetime import datetime


def log_event(message):
    timestamp = datetime.utcnow().isoformat()
    with open("data/log.txt", "a") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")
