#!/usr/bin/env python3
import json
import os
import time
import asyncio
import uuid
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import socketio
import uvicorn

from services.prisma_client import fetch_users
from services.cache import save, load
from log_utils import setup_logging, event_log
from Scheduler.Schedule_Generator import generate_schedule

from datetime import datetime
from pydantic import BaseModel


class CustomTrackRequest(BaseModel):
    fu_id: str
    norad_id: int
    start_time: str
    end_time: str


# ============================================================
# CONFIGURATION
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

ASSIGN_FILE = os.path.join(DATA_DIR, "schedule.json")
ACTIVE_FU_FILE = os.path.join(DATA_DIR, "active_fus.json")

LOG_HISTORY_LIMIT = 500
FU_TIMEOUT_SEC = 30

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
)

asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)
logger = setup_logging(sio)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# IN-MEMORY STATE (AUTHORITATIVE)
# ============================================================
SID_TO_FU: Dict[str, str] = {}

FU_REGISTRY: Dict[str, dict] = {
    # fu_id: {
    #   fu_id, state, health, mode,
    #   az, el, location,
    #   last_seen, current_pass
    # }
}

SCHEDULE_CACHE: Dict[str, list] = {}


# ============================================================
# ACTIVITY EXECUTION STATE
# ============================================================

ACTIVITY_STATE: Dict[str, dict] = {
    # activity_id: {
    #   activity, fu_id, state, started_at
    # }
}


# ============================================================
# HELPERS
# ============================================================
def load_assignments():
    global SCHEDULE_CACHE
    if os.path.exists(ASSIGN_FILE):
        with open(ASSIGN_FILE) as f:
            SCHEDULE_CACHE = json.load(f)
    else:
        SCHEDULE_CACHE = {}
    return SCHEDULE_CACHE


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

    with open(ACTIVE_FU_FILE, "w") as f:
        json.dump(active, f, indent=2)


async def push_all_schedules():
    await sio.emit("fu_schedule_update", SCHEDULE_CACHE)


def mark_fu_offline():
    now = time.time()
    changed = False

    for fu in FU_REGISTRY.values():
        if fu["state"] != "OFFLINE" and now - fu["last_seen"] > FU_TIMEOUT_SEC:
            fu["state"] = "OFFLINE"
            fu["health"] = "ERROR"
            changed = True

    return changed


def iso_to_epoch(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


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

    load_assignments()
    asyncio.create_task(run_scheduler("startup"))
    asyncio.create_task(fu_watchdog())
    asyncio.create_task(activity_executor())


@app.get("/api/logs")
async def api_logs():
    return JSONResponse(event_log[-LOG_HISTORY_LIMIT:])


@app.get("/api/fu_registry")
async def api_fu_registry():
    return JSONResponse(list(FU_REGISTRY.values()))


@app.get("/api/scheduler/status")
async def scheduler_status():
    return SCHEDULER_STATE


@app.post("/api/scheduler/run")
async def run_scheduler(reason: str):
    if SCHEDULER_STATE["running"]:
        return {"status": "busy"}

    logger.info("Scheduler starting (%s)", reason)
    SCHEDULER_STATE["running"] = True

    try:
        write_active_fus_for_scheduler()
        await asyncio.to_thread(generate_schedule)
        load_assignments()

        SCHEDULER_STATE["last_run"] = time.time()
        await push_all_schedules()

        logger.info("Scheduler completed")
        return {"status": "ok"}

    except Exception as e:
        logger.error("Scheduler failed: %s", e, exc_info=True)
        return {"status": "error"}

    finally:
        SCHEDULER_STATE["running"] = False


@app.post("/api/track/custom")
async def create_custom_tracking(req: CustomTrackRequest):
    activity_id = str(uuid.uuid4())

    activity = {
        "activity_id": activity_id,
        "satellite": f"CAT-{req.norad_id}",
        "norad_id": req.norad_id,
        "type": "CUSTOM_TRACK",
        "start_time": req.start_time,
        "end_time": req.end_time,
        "state": "PLANNED",
    }

    SCHEDULE_CACHE.setdefault(req.fu_id, []).append(activity)

    with open(ASSIGN_FILE, "w") as f:
        json.dump(SCHEDULE_CACHE, f, indent=2)

    await push_all_schedules()

    logger.info(
        "CUSTOM_TRACK_CREATED | fu=%s norad=%s",
        req.fu_id,
        req.norad_id,
    )

    return {"status": "ok", "activity_id": activity_id}


# ============================================================
# SOCKET.IO EVENTS
# ============================================================
@sio.event
async def connect(sid, environ, auth=None):
    logger.info("connect | sid=%s", sid)

    await sio.emit("fu_registry_update", list(FU_REGISTRY.values()), to=sid)
    await sio.emit("fu_schedule_update", SCHEDULE_CACHE, to=sid)


@sio.on("fu_status")
async def fu_status(sid, data):
    fu_id = data["fu_id"]

    FU_REGISTRY[fu_id] = {
        "fu_id": fu_id,
        "state": data.get("state", "IDLE"),
        "health": data.get("health", "OK"),
        "mode": data.get("mode", "AUTO"),
        "az": data.get("az"),
        "el": data.get("el"),
        "location": data.get("location"),
        "last_seen": time.time(),
        "current_pass": data.get("current_pass"),
    }

    SID_TO_FU[sid] = fu_id

    await sio.emit("fu_registry_update", list(FU_REGISTRY.values()))

    if fu_id in SCHEDULE_CACHE:
        await sio.emit(
            "fu_schedule_update",
            {fu_id: SCHEDULE_CACHE[fu_id]},
            to=sid,
        )

    logger.info("FU_STATUS | %s %s", fu_id, FU_REGISTRY[fu_id]["state"])


@sio.on("fu_command_ack")
async def fu_command_ack(sid, data):
    logger.info(
        "CMD_ACK | fu=%s cmd=%s status=%s",
        data.get("fu_id"),
        data.get("command_id"),
        data.get("status"),
    )


@sio.event
async def disconnect(sid):
    fu_id = SID_TO_FU.pop(sid, None)
    if fu_id and fu_id in FU_REGISTRY:
        FU_REGISTRY[fu_id]["state"] = "OFFLINE"
        FU_REGISTRY[fu_id]["health"] = "ERROR"

        await sio.emit("fu_registry_update", list(FU_REGISTRY.values()))
        logger.info("disconnect | %s", fu_id)


# ============================================================
# BACKGROUND TASKS
# ============================================================
async def fu_watchdog():
    while True:
        await asyncio.sleep(5)
        if mark_fu_offline():
            await sio.emit("fu_registry_update", list(FU_REGISTRY.values()))


# ============================================================
# ACTIVITY EXECUTION ENGINE
# ============================================================

async def activity_executor():
    """
    Authoritative ground-station execution loop.
    """
    logger.info("Activity executor started")

    while True:
        now = time.time()

        for fu_id, activities in SCHEDULE_CACHE.items():
            fu = FU_REGISTRY.get(fu_id)
            if not fu or fu["state"] != "IDLE":
                continue

            for activity in activities:
                if activity["state"] != "PLANNED":
                    continue

                start = iso_to_epoch(activity["start_time"])
                end = iso_to_epoch(activity["end_time"])

                # Start activity
                if start <= now <= end:
                    logger.info(
                        "ACTIVATE | %s %s",
                        fu_id,
                        activity["satellite"],
                    )

                    activity["state"] = "ACTIVE"
                    ACTIVITY_STATE[activity["activity_id"]] = {
                        "fu_id": fu_id,
                        "activity": activity,
                        "started_at": now,
                    }

                    # Send TRACK command
                    await send_fu_command(
                        fu_id,
                        "track",
                        {
                            "satellite": activity["satellite"],
                            "norad_id": activity["norad_id"],
                            "end_time": activity["end_time"],
                        },
                    )

                    fu["state"] = "BUSY"
                    fu["current_pass"] = activity["activity_id"]

        # Complete activities
        for act_id, ctx in list(ACTIVITY_STATE.items()):
            activity = ctx["activity"]
            fu_id = ctx["fu_id"]
            fu = FU_REGISTRY.get(fu_id)

            if iso_to_epoch(activity["end_time"]) < now:
                logger.info(
                    "COMPLETE | %s %s",
                    fu_id,
                    activity["satellite"],
                )

                activity["state"] = "COMPLETED"
                ACTIVITY_STATE.pop(act_id)

                if fu:
                    fu["state"] = "IDLE"
                    fu["current_pass"] = None

        await asyncio.sleep(1)


# ============================================================
# COMMAND API (GROUND → FU)
# ============================================================
async def send_fu_command(fu_id: str, cmd_type: str, args: dict):
    cmd = {
        "command_id": str(uuid.uuid4()),
        "fu_id": fu_id,
        "type": cmd_type,
        "args": args,
        "timestamp": time.time(),
    }

    await sio.emit("fu_command", cmd)
    logger.info("CMD_SENT | %s %s", fu_id, cmd_type)
    return cmd


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(asgi_app, host="0.0.0.0", port=port)
