
#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import socketio
from fastapi import Query
import uvicorn
from services.prisma_client import fetch_users
from services.cache import save, load
from log_utils import setup_logging, event_log
from Scheduler.Schedule_Generator import generate_schedule
import asyncio


# ============================================================
# CONFIGURATION
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATA_PATH = os.path.join(BASE_DIR, "fu_data.json")
TLE_FILE = os.path.join(DATA_DIR, "tles.json")
ASSIGN_FILE = os.path.join(DATA_DIR, "schedule.json")
LOG_HISTORY_LIMIT = 500
SCHEDULER_STATE = {
    "running": False,
    "last_run": None
}

# ============================================================
# FASTAPI + SOCKET.IO SETUP
# ============================================================
app = FastAPI()
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_timeout=20,
    ping_interval=10,
    message_queue="redis://localhost:6379"
)
asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)

logger = setup_logging(sio)

# Enable CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static dashboard files
app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================
# IN-MEMORY STATE
# ============================================================
SID_TO_FU = {}
FU_REGISTRY = {}
field_units = {}


# ============================================================
# LOAD FIELD UNIT STATE
# ============================================================
if os.path.exists(DATA_PATH):
    with open(DATA_PATH, "r") as f:
        field_units.update(json.load(f))
    for fu_id, data in field_units.items():
        FU_REGISTRY[fu_id] = {
            "fu_id": fu_id,
            "sensor_data": data.get("sensor_data", {}),
            "timestamp": time.time(),
            "satellite": data.get("satellite"),
            "az": data.get("az"),
            "el": data.get("el"),
            "gps": data.get("gps")
        }

    print(f"[BOOT] Restored {len(field_units)} Field Units")


def save_field_units():
    with open(DATA_PATH, "w") as f:
        json.dump(field_units, f, indent=2)


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


@app.get("/users")
async def users():
    return load()


@app.get("/")
async def dashboard():
    return FileResponse("static/dashboard.html")


@app.get("/api/logs")
async def api_logs():
    return JSONResponse(event_log[-LOG_HISTORY_LIMIT:])


@app.get("/api/fu_schedule/{fu_id}")
async def api_fu_schedule(fu_id: str):
    if not os.path.exists(ASSIGN_FILE):
        return []
    with open(ASSIGN_FILE) as f:
        assignments = json.load(f)
    return assignments.get(fu_id, [])


@app.post("/api/scheduler/run")
async def run_scheduler(reason: str):
    if SCHEDULER_STATE["running"]:
        logger.warning("Scheduler already running, skipping (%s)", reason)
        return

    logger.info("Scheduler starting (%s)", reason)
    SCHEDULER_STATE["running"] = True

    try:
        await asyncio.to_thread(generate_schedule)
        SCHEDULER_STATE["last_run"] = time.time()
        logger.info("Scheduler finished successfully")
    except Exception as e:
        logger.error("Scheduler failed with exception: %s", e, exc_info=True)
    finally:
        SCHEDULER_STATE["running"] = False


@app.post("/api/fu")
async def api_fu_post(request: Request):
    data = await request.json()
    await handle_field_unit_data(None, data)
    return {"status": "ok"}


@app.get("/api/fu_registry")
async def api_fu_registry():
    return JSONResponse(FU_REGISTRY)

# ============================================================
# SOCKET.IO EVENTS
# ============================================================


def load_assignments():
    if not os.path.exists(ASSIGN_FILE):
        return {}
    with open(ASSIGN_FILE) as f:
        return json.load(f)


@sio.event
async def connect(sid, environ, auth=None):
    print(f"[CONNECT] {sid}")
    logger.info("connect: FU connected")
    if (
        not SCHEDULER_STATE["last_run"]
        or time.time() - SCHEDULER_STATE["last_run"] > 86400
    ):
        asyncio.create_task(run_scheduler("fu_connect"))

    await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})


@sio.on("field_unit_data")
async def handle_field_unit_data(sid, data):
    fu_id = data.get("fu_id")
    sensor = data.get("sensor_data", {})

    if not fu_id:
        print("[WARN] Missing fu_id")
        return

    FU_REGISTRY[fu_id] = {
        "fu_id": fu_id,
        "sensor_data": sensor,
        "timestamp": time.time(),
        "satellite": data.get("satellite"),
        "az": field_units.get(fu_id, {}).get("az"),
        "el": field_units.get(fu_id, {}).get("el"),
        "location": data.get("location")
    }

    field_units.setdefault(fu_id, {})["sensor_data"] = sensor
    SID_TO_FU[sid] = fu_id

    await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})

    logger.info("fu_log | %s", fu_id)

    assignments = load_assignments()
    if fu_id in assignments:
        await sio.emit(
            "fu_schedule",
            {
                "fu_id": fu_id,
                "schedule": assignments[fu_id]
            },
            to=sid
        )


@sio.on("az_el_result")
async def az_el_result(sid, data):
    fu_id = data["fu_id"]
    az = data["az"]
    el = data["el"]
    gps = data.get("gps", {})
    sat = data.get("satellite_name")

    field_units.setdefault(fu_id, {}).update({
        "az": az, "el": el, "gps": gps, "satellite": sat
    })

    await sio.emit("az_el_command", {"fu_id": fu_id, "az": az, "el": el})

    logger.info("az_el", f"{fu_id}: AZ={az} EL={el}")


@sio.event
async def disconnect(sid):
    fu_id = SID_TO_FU.pop(sid, None)
    if fu_id:
        FU_REGISTRY.pop(fu_id, None)
        save_field_units()
        logger.info("disconnect", f"{fu_id} disconnected")

    await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    uvicorn.run(asgi_app, host="0.0.0.0", port=8080)
