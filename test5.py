#!/usr/bin/env python3
"""
fu_client.py
CCSDS-style Field Unit housekeeping & status client
"""

import time
import uuid
import os
import socketio
import requests

SERVER_URL = "https://orbitalink-centralunit.onrender.com"
SOCKET_URL = SERVER_URL
HEARTBEAT_INTERVAL = 10  # seconds

FU_ID_FILE = "fu_id.txt"

# ==========================================================
# FU ID
# ==========================================================


def get_mac_based_id():
    mac = uuid.getnode()
    return f"FU-{mac:012X}"


def load_or_create_fu_id():
    if os.path.exists(FU_ID_FILE):
        return open(FU_ID_FILE).read().strip()

    fu_id = get_mac_based_id()
    with open(FU_ID_FILE, "w") as f:
        f.write(fu_id)

    return fu_id


# ==========================================================
# LOCATION (STATIC OR GPS)
# ==========================================================
def get_location():
    """
    Replace this later with real GPS.
    """
    try:
        resp = requests.get("https://ipapi.co/json/", timeout=5)
        data = resp.json()
        return {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        }
    except Exception:
        return None


# ==========================================================
# SOCKET.IO CLIENT
# ==========================================================
sio = socketio.Client(reconnection=True)
fu_id = load_or_create_fu_id()
location = get_location()


@sio.event
def connect():
    print(f"[FU {fu_id}] Connected to Ground Station")


@sio.event
def disconnect():
    print(f"[FU {fu_id}] Disconnected")


@sio.on("fu_command")
def handle_command(cmd):
    """
    Execute command and ACK/NACK
    """
    cmd_id = cmd["command_id"]
    cmd_type = cmd["type"]

    print(f"[FU {fu_id}] CMD {cmd_type}")

    try:
        # --- EXECUTION STUB ---
        # Replace with real antenna control
        time.sleep(1)

        sio.emit("fu_command_ack", {
            "fu_id": fu_id,
            "command_id": cmd_id,
            "status": "ACK"
        })

    except Exception as e:
        sio.emit("fu_command_ack", {
            "fu_id": fu_id,
            "command_id": cmd_id,
            "status": "NACK",
            "reason": str(e)
        })


# ==========================================================
# MAIN LOOP
# ==========================================================
def heartbeat():
    while True:
        sio.emit("fu_status", {
            "fu_id": fu_id,
            "state": "IDLE",
            "health": "OK",
            "mode": "AUTO",
            "az": None,
            "el": None,
            "location": location,
            "current_pass": None
        })
        time.sleep(HEARTBEAT_INTERVAL)


def main():
    print(f"[START] FU ID = {fu_id}")
    sio.connect(SOCKET_URL, transports=["websocket"])
    heartbeat()


if __name__ == "__main__":
    main()
