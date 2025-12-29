#!/usr/bin/env python3
import socketio
import time
import uuid
import os
import signal
import sys

# ============================================================
# CONFIG
# ============================================================
SERVER_URL = "https://orbitalinkcentralunit-production.up.railway.app"
HEARTBEAT_INTERVAL = 10  # seconds

FU_ID_FILE = "fu_id.txt"

# ============================================================
# HELPERS
# ============================================================


def load_or_create_fu_id():
    if os.path.exists(FU_ID_FILE):
        return open(FU_ID_FILE).read().strip()

    fu_id = f"FU-{uuid.uuid4().hex[:6].upper()}"
    with open(FU_ID_FILE, "w") as f:
        f.write(fu_id)

    return fu_id


FU_ID = load_or_create_fu_id()

# ============================================================
# SOCKET.IO CLIENT
# ============================================================
sio = socketio.Client(
    reconnection=True,
    reconnection_attempts=0,
    reconnection_delay=2,
)

# ============================================================
# EVENTS
# ============================================================


@sio.event
def connect():
    print(f"[CONNECTED] FU_ID={FU_ID}")


@sio.event
def disconnect():
    print("[DISCONNECTED]")


@sio.on("fu_schedule_update")
def on_schedule_update(data):
    print("[SCHEDULE UPDATE]")
    print(data)


@sio.on("fu_command")
def on_fu_command(cmd):
    print(f"[COMMAND RECEIVED] {cmd}")

    # Simulate command execution
    time.sleep(1)

    # ACK command
    sio.emit("fu_command_ack", {
        "fu_id": FU_ID,
        "command_id": cmd["command_id"],
        "status": "OK"
    })

    print("[COMMAND ACK SENT]")

# ============================================================
# HEARTBEAT LOOP
# ============================================================


def send_heartbeat():
    sio.emit("fu_status", {
        "fu_id": FU_ID,
        "state": "IDLE",
        "health": "OK",
        "mode": "AUTO",
        "az": None,
        "el": None,
        "location": {
            "latitude": 28.6139,
            "longitude": 77.2090
        },
        "current_pass": None
    })

    print("[HEARTBEAT SENT]")

# ============================================================
# CLEAN EXIT
# ============================================================


def shutdown(sig, frame):
    print("\n[SHUTDOWN]")
    sio.disconnect()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print(f"[STARTING FU] {FU_ID}")
    sio.connect(
        SERVER_URL,
        transports=["polling"],
        socketio_path="socket.io"
    )

    while True:
        send_heartbeat()
        time.sleep(HEARTBEAT_INTERVAL)
