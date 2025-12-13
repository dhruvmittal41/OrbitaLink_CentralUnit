#!/usr/bin/env python3
"""
scheduler.py — Generate 24-hour satellite pass schedules for the Central Unit (CU).

This version assumes TLEs are already updated (by `update_tles.py`).
"""

import json
import os
from datetime import datetime, timedelta, timezone
from skyfield.api import load, wgs84, EarthSatellite
import requests

# ==============================
# CONFIGURATION
# ==============================
SATELLITES_FILE = "data/satellites.json"
SCHEDULE_FILE = "data/schedule.json"

SELECTED_SATELLITES = [
    "NOAA 20 (JPSS-1)"
]

DEFAULT_LAT, DEFAULT_LON, DEFAULT_ALT = 29.97, 78.17, 0.216  # Haridwar fallback
IST = timezone(timedelta(hours=5, minutes=30))

# ==============================
# GET LOCATION (with caching)
# ==============================


def get_current_location():
    """Get approximate lat/lon via IP geolocation with cache fallback."""
    os.makedirs("data", exist_ok=True)
    cache_path = "data/location_cache.json"

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)
            print(
                f"[INFO] Using cached location: {cached['lat']:.4f}, {cached['lon']:.4f}")
            return cached["lat"], cached["lon"], cached.get("alt", DEFAULT_ALT)
        except Exception:
            pass

    providers = [
        "https://ipapi.co/json/",
        "https://ipinfo.io/json",
        "https://geolocation-db.com/json/",
    ]

    for provider in providers:
        try:
            print(f"[INFO] Trying geolocation provider: {provider}")
            res = requests.get(provider, timeout=8)
            res.raise_for_status()
            data = res.json()

            lat = (
                float(data.get("latitude"))
                if "latitude" in data
                else float(data.get("lat", DEFAULT_LAT))
            )
            lon = (
                float(data.get("longitude"))
                if "longitude" in data
                else float(data.get("lon", DEFAULT_LON))
            )

            with open(cache_path, "w") as f:
                json.dump({"lat": lat, "lon": lon, "alt": DEFAULT_ALT}, f)

            print(f"[INFO] Detected location: {lat:.4f}, {lon:.4f}")
            return lat, lon, DEFAULT_ALT
        except Exception as e:
            print(f"[WARN] Provider failed ({provider}): {e}")

    print(
        f"[INFO] Falling back to default coordinates ({DEFAULT_LAT}, {DEFAULT_LON})")
    return DEFAULT_LAT, DEFAULT_LON, DEFAULT_ALT


# ==============================
# FIND SATELLITE PASSES
# ==============================
def find_passes(satellite, location, ts, start_time, hours=24):
    """Return all visible passes for the next `hours` hours (above 10° elevation)."""
    t0 = ts.from_datetime(start_time)
    t1 = ts.from_datetime(start_time + timedelta(hours=hours))

    times, events = satellite.find_events(
        location, t0, t1, altitude_degrees=10.0)
    passes, current_pass = [], {}

    for ti, event in zip(times, events):
        t_local = ti.utc_datetime().astimezone(IST)
        if event == 0:  # Rise
            current_pass = {"start_time": t_local.strftime(
                "%Y-%m-%d %H:%M:%S %Z")}
        elif event == 1:  # Culminate
            alt, _, _ = (satellite - location).at(ti).altaz()
            current_pass["max_elevation_deg"] = round(alt.degrees, 2)
        elif event == 2:  # Set
            current_pass["end_time"] = t_local.strftime("%Y-%m-%d %H:%M:%S %Z")
            passes.append(current_pass)
            current_pass = {}

    return passes


# ==============================
# GENERATE SCHEDULE
# ==============================
def generate_schedule(selected_satellites):
    """Generate a 24-hour visibility schedule (IST) using pre-fetched TLEs."""
    lat, lon, alt = get_current_location()
    ts = load.timescale()
    location = wgs84.latlon(lat, lon, alt)

    if not os.path.exists(SATELLITES_FILE):
        raise FileNotFoundError(
            f"TLE file '{SATELLITES_FILE}' not found. Run update_tles.py first."
        )

    with open(SATELLITES_FILE, "r") as f:
        satellites_data = json.load(f)

    now_utc = datetime.now(timezone.utc)
    schedule = []

    for satname in selected_satellites:
        if satname not in satellites_data:
            print(
                f"[WARNING] {satname} not found in {SATELLITES_FILE}, skipping...")
            continue

        tle = satellites_data[satname]
        satellite = EarthSatellite(tle["line1"], tle["line2"], satname, ts)

        print(f"[INFO] Calculating visible passes for {satname}...")
        passes = find_passes(satellite, location, ts, now_utc, hours=24)

        for p in passes:
            p["satellite"] = satname
        schedule.extend(passes)

        print(f"[SCHEDULE] {satname}: {len(passes)} passes found.")

    os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=4)

    print(f"\n✅ Generated {len(schedule)} total schedule entries (IST).")
    print(f"📁 Output saved to: {SCHEDULE_FILE}")


if __name__ == "__main__":
    generate_schedule(SELECTED_SATELLITES)
