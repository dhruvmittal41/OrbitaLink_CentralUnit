#!/usr/bin/env python3
"""
fu_registry.py
FU heartbeat to POST /api/fu.
Sends:
  - fu_id
  - ip (public)
  - occupied_slots
  - location (derived from IP)
"""

import time
import uuid
import requests
import socket
import os

SERVER_HTTP = "https://orbitalink-centralunit.onrender.com"

API_FU = f"{SERVER_HTTP}/api/fu"
HEARTBEAT_INTERVAL = 30  # seconds

FU_ID_FILE = "fu_id.txt"

# Cache location so we don't geolocate every heartbeat
_cached_location = None


def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(f"{(mac >> ele) & 0xff:02x}" for ele in range(40, -1, -8))


def load_or_create_fu_id():
    if os.path.exists(FU_ID_FILE):
        return open(FU_ID_FILE).read().strip()
    fu = get_mac_address()
    with open(FU_ID_FILE, "w") as f:
        f.write(fu)
    return fu


def get_public_ip():
    """Get public IP address."""
    try:
        return requests.get("https://api.ipify.org", timeout=5).text.strip()
    except Exception:
        return None


def get_location_from_ip(ip):
    global _cached_location

    print(f"[DEBUG] Resolving location for IP: {ip}")

    if _cached_location:
        print("[DEBUG] Using cached location")
        return _cached_location

    try:
        url = f"https://ipapi.co/{ip}/json/"

        resp = requests.get(url, timeout=5)

        data = resp.json()

        lat = data.get("latitude")
        lon = data.get("longitude")

        if not lat or not lon:
            print("[WARN] No lat/lon in geo response")
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
        print("[ERROR] Geo exception:", e)
        return None


def register_fu(fu_id):
    public_ip = get_public_ip()

    payload = {
        "fu_id": "FU 001",
        "ip": public_ip,
        "occupied_slots": [],
        "satellite": "ICEYE-X40"
    }

    if public_ip:
        print("[DEBUG] Attempting IP-based geolocation")
        location = get_location_from_ip(public_ip)
        if location:
            payload["location"] = location
            print("[DEBUG] Payload:", payload)

    try:
        resp = requests.post(API_FU, json=payload, timeout=5)
        print(f"[REG] HTTP {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"[REG] Error: {e}")
        return False


def main():
    fu_id = load_or_create_fu_id()
    print(f"[INFO] FU_ID={fu_id}")

    while True:
        ok = register_fu(fu_id)
        if not ok:
            print("[WARN] Registration failed; will retry.")
        time.sleep(HEARTBEAT_INTERVAL)


if __name__ == "__main__":
    main()
