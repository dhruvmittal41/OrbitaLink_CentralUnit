#!/usr/bin/env python3
"""
fu_registry.py
Heartbeat client for OrbitaLink Field Units
"""

import time
import uuid
import requests
import os

SERVER_HTTP = "https://orbitalink-centralunit.onrender.com"
API_FU = f"{SERVER_HTTP}/api/fu"
HEARTBEAT_INTERVAL = 30  # seconds

FU_ID_FILE = "fu_id.txt"
_cached_location = None


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


def get_public_ip():
    try:
        return requests.get("https://api.ipify.org", timeout=5).text.strip()
    except Exception:
        return None


def get_location_from_ip(ip):
    global _cached_location

    if _cached_location:
        return _cached_location

    try:
        resp = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        data = resp.json()

        lat = data.get("latitude")
        lon = data.get("longitude")

        if lat is None or lon is None:
            return None

        _cached_location = {
            "latitude": lat,
            "longitude": lon,
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country_name"),
            "source": "ip"
        }

        return _cached_location

    except Exception as e:
        print("[ERROR] Geo lookup failed:", e)
        return None


def register_fu(fu_id):
    public_ip = get_public_ip()

    payload = {
        "fu_id": fu_id,
        "satellite": None,
        "sensor_data": {},
    }

    if public_ip:
        location = get_location_from_ip(public_ip)
        if location:
            payload["location"] = location

    try:
        resp = requests.post(API_FU, json=payload, timeout=5)
        print(f"[FU {fu_id}] POST /api/fu → {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"[FU {fu_id}] ERROR:", e)
        return False


def main():
    fu_id = load_or_create_fu_id()
    print(f"[START] Field Unit ID = {fu_id}")

    while True:
        register_fu(fu_id)
        time.sleep(HEARTBEAT_INTERVAL)


if __name__ == "__main__":
    main()
