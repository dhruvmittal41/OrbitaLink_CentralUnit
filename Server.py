
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

# ============================================================
# CONFIGURATION
# ============================================================
DATA_PATH = "fu_data.json"
TLE_FILE = "all_tle_data.json"
ASSIGN_FILE = "data/assignments.json"
LOG_HISTORY_LIMIT = 500


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
event_log = []  # merged log from second server.py


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

# ============================================================
# LOAD TLE CACHE
# ============================================================
TLE_CACHE = {}
if os.path.exists(TLE_FILE):
    with open(TLE_FILE) as f:
        TLE_CACHE = json.load(f)
    print(f"[BOOT] Loaded {len(TLE_CACHE)} satellites")
else:
    print(f"[ERROR] Missing TLE file: {TLE_FILE}")

# ============================================================
# UTIL
# ============================================================


def save_field_units():
    with open(DATA_PATH, "w") as f:
        json.dump(field_units, f, indent=2)


def log_event(event_type, data):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {"time": timestamp, "type": event_type, "data": data}
    event_log.append(entry)
    if len(event_log) > LOG_HISTORY_LIMIT:
        event_log.pop(0)
    # Push event to dashboard
    uv = {"type": event_type, "msg": data}
    return sio.emit("log_update", uv)

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


@app.get("/api/satellites")
async def api_sat_list():
    return list(TLE_CACHE.keys())


@app.get("/api/tle_by_name")
async def api_tle_by_name(name: str = Query(...)):
    if name not in TLE_CACHE:
        raise HTTPException(404, f"TLE not found: {name}")
    x = TLE_CACHE[name]
    return {"name": name, "tle_line1": x["line1"], "tle_line2": x["line2"]}


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


@sio.event
async def connect(sid, environ):
    print(f"[CONNECT] {sid}")
    log_event("connect", f"FU connected SID={sid}")
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
        "satellite": field_units.get(fu_id, {}).get("satellite"),
        "az": field_units.get(fu_id, {}).get("az"),
        "el": field_units.get(fu_id, {}).get("el"),
        "location": field_units.get(fu_id, {}).get("location")
    }

    field_units.setdefault(fu_id, {})["sensor_data"] = sensor
    SID_TO_FU[sid] = fu_id

    await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})

    log_event("fu_log", f"{fu_id} sensor={sensor}")


@sio.on("select_satellite")
async def select_satellite(sid, data):
    fu_id = data["fu_id"]
    sat_name = data["satellite_name"]

    field_units.setdefault(fu_id, {})["satellite"] = sat_name
    FU_REGISTRY.setdefault(fu_id, {})["satellite"] = sat_name

    await sio.emit("az_el_update", {
        "fu_id": fu_id,
        "satellite_name": sat_name
    })

    log_event("sat_select", f"{fu_id} selected {sat_name}")


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

    log_event("az_el", f"{fu_id}: AZ={az} EL={el}")


@sio.event
async def disconnect(sid):
    fu_id = SID_TO_FU.pop(sid, None)
    if fu_id:
        FU_REGISTRY.pop(fu_id, None)
        save_field_units()
        log_event("disconnect", f"{fu_id} disconnected")

    await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})

# ============================================================
# RUN SERVER
# ============================================================
if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    uvicorn.run(asgi_app, host="0.0.0.0", port=8080)
