"""
registry_control.py
HTTP-based FU registry that works with FastAPI server.py and the new
HTTP-POST field_unit registry (fu_registry.py).
"""

import json
import time
import threading
import os
from datetime import datetime, timezone, timedelta
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
DATA_DIR = os.path.abspath(DATA_DIR)
REGISTRY_FILE = os.path.join(DATA_DIR, "active_fus.json")
SERVER_API = "https://orbitalink-centralunit.onrender.com/api/fu_registry"
CHECK_INTERVAL = 30
TIMEOUT_MINUTES = 5

app = FastAPI()

fus = {}


def load_registry():
    global fus
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r") as f:
                fus = json.load(f)
        except:
            fus = {}
    else:
        fus = {}


def save_registry():
    with open(REGISTRY_FILE, "w") as f:
        json.dump(fus, f, indent=4)


def heartbeat_sync():
    """
    Periodically pulls FU_REGISTRY from FastAPI server and updates local registry.
    """
    global fus
    while True:
        try:
            resp = requests.get(SERVER_API, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                for fu_id, info in data.items():
                    fus[fu_id] = info
                save_registry()
                print("[SYNC] Registry synchronized")
        except Exception as e:
            print(f"[SYNC ERROR] {e}")

        time.sleep(CHECK_INTERVAL)


def remove_inactive():
    """
    Removes FUs that stopped heartbeating.
    """
    global fus
    while True:
        now = datetime.now(timezone.utc)
        dead = []

        for fu_id, info in fus.items():
            ts = datetime.fromtimestamp(info["timestamp"], tz=timezone.utc)
            if (now - ts) > timedelta(minutes=TIMEOUT_MINUTES):
                print(f"[TIMEOUT] Removing inactive FU: {fu_id}")
                dead.append(fu_id)

        for fu_id in dead:
            del fus[fu_id]

        if dead:
            save_registry()

        time.sleep(60)

# --------------------------------------------------
# HTTP API (optional)
# --------------------------------------------------


@app.get("/registry")
def get_registry():
    return JSONResponse(fus)


@app.get("/registry/{fu_id}")
def get_fu(fu_id: str):
    return fus.get(fu_id, {})


# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    load_registry()

    threading.Thread(target=heartbeat_sync, daemon=True).start()
    threading.Thread(target=remove_inactive, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=8091)
