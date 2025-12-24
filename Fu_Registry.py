# """
# registry_control.py

# HTTP-based FU registry that synchronizes active FUs from the Central Unit
# and maintains a normalized active_fus.json for the scheduler.
# """

# import json
# import time
# import threading
# import os
# from datetime import datetime, timezone, timedelta
# import requests
# from fastapi import FastAPI
# from fastapi.responses import JSONResponse
# import uvicorn


# # ==========================================================
# # PATHS & CONFIG
# # ==========================================================
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))
# os.makedirs(DATA_DIR, exist_ok=True)

# REGISTRY_FILE = os.path.join(DATA_DIR, "active_fus.json")

# SERVER_API = "https://orbitalink-centralunit.onrender.com/api/fu_registry"

# CHECK_INTERVAL = 30          # seconds
# TIMEOUT_MINUTES = 5          # FU inactivity timeout


# # ==========================================================
# # FASTAPI APP
# # ==========================================================
# app = FastAPI()

# fus = {}


# # ==========================================================
# # HELPERS
# # ==========================================================
# def normalize_location(loc: dict | None):
#     """
#     Normalize FU location into:
#     { "latitude": float, "longitude": float }
#     """
#     if not loc:
#         return None

#     if "latitude" in loc and "longitude" in loc:
#         return {
#             "latitude": loc["latitude"],
#             "longitude": loc["longitude"]
#         }

#     if "lat" in loc and "lon" in loc:
#         return {
#             "latitude": loc["lat"],
#             "longitude": loc["lon"]
#         }

#     return None


# def load_registry():
#     global fus
#     if os.path.exists(REGISTRY_FILE):
#         try:
#             with open(REGISTRY_FILE, "r") as f:
#                 fus = json.load(f)
#         except Exception:
#             fus = {}
#     else:
#         fus = {}


# def save_registry():
#     with open(REGISTRY_FILE, "w") as f:
#         json.dump(fus, f, indent=4)


# # ==========================================================
# # BACKGROUND TASKS
# # ==========================================================
# def heartbeat_sync():
#     """
#     Periodically pulls FU_REGISTRY from the Central Unit
#     and writes a normalized active_fus.json for the scheduler.
#     """
#     global fus

#     while True:
#         try:
#             resp = requests.get(SERVER_API, timeout=5)
#             if resp.status_code == 200:
#                 data = resp.json()

#                 updated = {}
#                 for fu_id, info in data.items():
#                     loc = normalize_location(info.get("location"))

#                     # Skip FUs without valid location
#                     if not loc:
#                         continue

#                     updated[fu_id] = {
#                         "fu_id": fu_id,
#                         "timestamp": info.get("timestamp"),
#                         "location": loc,
#                         "sensor_data": info.get("sensor_data", {}),
#                         "satellite": info.get("satellite"),
#                         "az": info.get("az"),
#                         "el": info.get("el")
#                     }

#                 fus = updated
#                 save_registry()
#                 print(f"[SYNC] Registry synchronized ({len(fus)} active FUs)")

#         except Exception as e:
#             print(f"[SYNC ERROR] {e}")

#         time.sleep(CHECK_INTERVAL)


# def remove_inactive():
#     """
#     Removes FUs that stopped heartbeating.
#     """
#     global fus

#     while True:
#         now = datetime.now(timezone.utc)
#         dead = []

#         for fu_id, info in fus.items():
#             ts = info.get("timestamp")
#             if not ts:
#                 dead.append(fu_id)
#                 continue

#             last = datetime.fromtimestamp(ts, tz=timezone.utc)
#             if (now - last) > timedelta(minutes=TIMEOUT_MINUTES):
#                 print(f"[TIMEOUT] Removing inactive FU: {fu_id}")
#                 dead.append(fu_id)

#         for fu_id in dead:
#             fus.pop(fu_id, None)

#         if dead:
#             save_registry()

#         time.sleep(60)


# # ==========================================================
# # HTTP API (OPTIONAL)
# # ==========================================================
# @app.get("/registry")
# def get_registry():
#     return JSONResponse(fus)


# @app.get("/registry/{fu_id}")
# def get_fu(fu_id: str):
#     return fus.get(fu_id, {})


# # ==========================================================
# # MAIN
# # ==========================================================
# if __name__ == "__main__":
#     load_registry()

#     threading.Thread(target=heartbeat_sync, daemon=True).start()
#     threading.Thread(target=remove_inactive, daemon=True).start()

#     uvicorn.run(app, host="0.0.0.0", port=8091)
