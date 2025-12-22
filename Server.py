#!/usr/bin/env python3
import json
import os
import time
import asyncio
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import socketio
import uvicorn

from services.prisma_client import fetch_users
from services.cache import save, load
from log_utils import setup_logging, event_log
from Scheduler.Schedule_Generator import generate_schedule


# ============================================================
# CONFIGURATION
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATA_PATH = os.path.join(BASE_DIR, "fu_data.json")
ASSIGN_FILE = os.path.join(DATA_DIR, "schedule.json")

LOG_HISTORY_LIMIT = 500

SCHEDULER_STATE = {
    "running": False,
    "last_run": None,
}

# ============================================================
# FASTAPI + SOCKET.IO
# ============================================================
app = FastAPI()

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_timeout=20,
    ping_interval=10,
    message_queue="redis://localhost:6379",
)

asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)
logger = setup_logging(sio)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================
# IN-MEMORY STATE
# ============================================================
SID_TO_FU = {}
FU_REGISTRY = {}
FIELD_UNITS = {}

# Cached schedules (key = fu_id)
SCHEDULE_CACHE = {}


# ============================================================
# BOOTSTRAP STATE
# ============================================================
if os.path.exists(DATA_PATH):
    with open(DATA_PATH) as f:
        FIELD_UNITS.update(json.load(f))

    for fu_id, data in FIELD_UNITS.items():
        FU_REGISTRY[fu_id] = {
            "fu_id": fu_id,
            "sensor_data": data.get("sensor_data", {}),
            "timestamp": time.time(),
            "satellite": data.get("satellite"),
            "az": data.get("az"),
            "el": data.get("el"),
            "location": data.get("location"),
        }

    print(f"[BOOT] Restored {len(FIELD_UNITS)} Field Units")

if os.path.exists(ASSIGN_FILE):
    with open(ASSIGN_FILE) as f:
        SCHEDULE_CACHE = json.load(f)


# ============================================================
# HELPERS
# ============================================================
def save_field_units():
    with open(DATA_PATH, "w") as f:
        json.dump(FIELD_UNITS, f, indent=2)


def write_active_fus_for_scheduler():
    active = {}

    for fu_id, fu in FU_REGISTRY.items():
        loc = fu.get("location")
        if not loc:
            continue

        lat = loc.get("latitude") or loc.get("lat")
        lon = loc.get("longitude") or loc.get("lon")

        if lat is None or lon is None:
            continue

        active[fu_id] = {
            "fu_id": fu_id,
            "location": {"latitude": lat, "longitude": lon},
        }

    with open(os.path.join(DATA_DIR, "active_fus.json"), "w") as f:
        json.dump(active, f, indent=2)


def load_assignments():
    global SCHEDULE_CACHE
    if not os.path.exists(ASSIGN_FILE):
        SCHEDULE_CACHE = {}
        return {}

    with open(ASSIGN_FILE) as f:
        SCHEDULE_CACHE = json.load(f)
    return SCHEDULE_CACHE


async def push_all_schedules():
    """Push schedules to all connected clients"""
    await sio.emit("fu_schedule_update", SCHEDULE_CACHE)


# ============================================================
# ROUTES
# ============================================================
@app.on_event("startup")
async def startup():
    try:
        users = await fetch_users()
        save(users)
    except Exception:
        pass

    asyncio.create_task(run_scheduler("startup"))


@app.get("/")
async def dashboard():
    return FileResponse("static/dashboard.html")


@app.get("/users")
async def users():
    return load()


@app.get("/api/logs")
async def api_logs():
    return JSONResponse(event_log[-LOG_HISTORY_LIMIT:])


@app.get("/api/scheduler/status")
async def scheduler_status():
    return SCHEDULER_STATE


@app.post("/api/scheduler/run")
async def run_scheduler(reason: str):
    if SCHEDULER_STATE["running"]:
        logger.warning("Scheduler already running (%s)", reason)
        return {"status": "busy"}

    logger.info("Scheduler starting (%s)", reason)
    SCHEDULER_STATE["running"] = True

    try:
        write_active_fus_for_scheduler()
        await asyncio.to_thread(generate_schedule)
        load_assignments()

        SCHEDULER_STATE["last_run"] = time.time()
        await push_all_schedules()

        logger.info("Scheduler completed successfully")
        return {"status": "ok"}

    except Exception as e:
        logger.error("Scheduler failed: %s", e, exc_info=True)
        return {"status": "error"}

    finally:
        SCHEDULER_STATE["running"] = False


@app.get("/api/fu/{fu_id}/schedule")
async def get_fu_schedule(fu_id: str):
    return SCHEDULE_CACHE.get(fu_id, [])


@app.get("/api/fu_registry")
async def api_fu_registry():
    return JSONResponse(FU_REGISTRY)


@app.post("/api/fu")
async def api_fu_post(request: Request):
    data = await request.json()
    await handle_field_unit_data(None, data)
    return {"status": "ok"}


# ============================================================
# SOCKET.IO EVENTS
# ============================================================
@sio.event
async def connect(sid, environ, auth=None):
    logger.info("connect | sid=%s", sid)

    if (
        not SCHEDULER_STATE["last_run"]
        or time.time() - SCHEDULER_STATE["last_run"] > 86400
    ):
        asyncio.create_task(run_scheduler("fu_connect"))

    await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})
    await sio.emit("fu_schedule_update", SCHEDULE_CACHE, to=sid)


@sio.on("field_unit_data")
async def handle_field_unit_data(sid, data):
    fu_id = data.get("fu_id")
    if not fu_id:
        return

    FU_REGISTRY[fu_id] = {
        "fu_id": fu_id,
        "sensor_data": data.get("sensor_data", {}),
        "timestamp": time.time(),
        "satellite": data.get("satellite"),
        "az": FIELD_UNITS.get(fu_id, {}).get("az"),
        "el": FIELD_UNITS.get(fu_id, {}).get("el"),
        "location": data.get("location"),
    }

    FIELD_UNITS.setdefault(fu_id, {})[
        "sensor_data"] = data.get("sensor_data", {})
    SID_TO_FU[sid] = fu_id

    await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})

    # Send schedule immediately if exists
    if fu_id in SCHEDULE_CACHE:
        await sio.emit(
            "fu_schedule_update",
            {fu_id: SCHEDULE_CACHE[fu_id]},
            to=sid,
        )

    logger.info("fu_update | %s", fu_id)


@sio.on("az_el_result")
async def az_el_result(sid, data):
    fu_id = data["fu_id"]

    FIELD_UNITS.setdefault(fu_id, {}).update(
        {
            "az": data["az"],
            "el": data["el"],
            "gps": data.get("gps"),
            "satellite": data.get("satellite_name"),
        }
    )

    await sio.emit(
        "az_el_command",
        {"fu_id": fu_id, "az": data["az"], "el": data["el"]},
    )

    logger.info("az_el | %s AZ=%s EL=%s", fu_id, data["az"], data["el"])


@sio.event
async def disconnect(sid):
    fu_id = SID_TO_FU.pop(sid, None)
    if fu_id:
        FU_REGISTRY.pop(fu_id, None)
        save_field_units()
        logger.info("disconnect | %s", fu_id)

    await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    uvicorn.run(asgi_app, host="0.0.0.0", port=8080)
