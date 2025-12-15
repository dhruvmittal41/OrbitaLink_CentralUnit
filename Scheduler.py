#!/usr/bin/env python3
"""
scheduler.py — Generate 24-hour satellite pass schedules
for each active FU location.

Assumes:
- TLEs exist in data/satellites.json
- Active FUs exist in data/location_data/active_fus.json
"""

import json
import os
from datetime import datetime, timedelta, timezone
from skyfield.api import load, wgs84, EarthSatellite

# ==============================
# CONFIGURATION
# ==============================
SATELLITES_FILE = "data/satellites.json"
ACTIVE_FUS_FILE = "data/location_data/active_fus.json"
SCHEDULE_FILE = "data/schedule.json"

IST = timezone(timedelta(hours=5, minutes=30))

MIN_ELEVATION_DEG = 10.0
SCHEDULE_HOURS = 24

# ==============================
# PASS COMPUTATION
# ==============================


def find_passes(satellite, location, ts, start_time, hours):
    """Return all visible passes within time window."""
    t0 = ts.from_datetime(start_time)
    t1 = ts.from_datetime(start_time + timedelta(hours=hours))

    times, events = satellite.find_events(
        location, t0, t1, altitude_degrees=MIN_ELEVATION_DEG
    )

    passes = []
    current_pass = None

    for ti, event in zip(times, events):
        t_local = ti.utc_datetime().astimezone(IST)

        if event == 0:  # Rise
            current_pass = {
                "start_time": t_local.isoformat()
            }

        elif event == 1 and current_pass is not None:  # Culmination
            alt, _, _ = (satellite - location).at(ti).altaz()
            current_pass["max_elevation_deg"] = round(alt.degrees, 2)

        elif event == 2 and current_pass is not None:  # Set
            current_pass["end_time"] = t_local.isoformat()
            passes.append(current_pass)
            current_pass = None

    return passes

# ==============================
# SCHEDULE GENERATION
# ==============================


def generate_schedule():
    if not os.path.exists(SATELLITES_FILE):
        raise FileNotFoundError(f"Missing {SATELLITES_FILE}")

    if not os.path.exists(ACTIVE_FUS_FILE):
        raise FileNotFoundError(f"Missing {ACTIVE_FUS_FILE}")

    with open(SATELLITES_FILE, "r") as f:
        satellites_data = json.load(f)

    with open(ACTIVE_FUS_FILE, "r") as f:
        fus_data = json.load(f)

    ts = load.timescale()
    now_utc = datetime.now(timezone.utc)

    full_schedule = {}

    print(f"\n[INFO] Active FUs detected: {len(fus_data)}")
    print(f"[INFO] Satellites loaded: {len(satellites_data)}\n")

    for fu_id, fu in fus_data.items():
        loc = fu.get("location", {})
        lat = loc.get("latitude")
        lon = loc.get("longitude")

        if lat is None or lon is None:
            print(f"[WARN] FU {fu_id} missing location, skipping")
            continue

        print(f"[INFO] Scheduling for FU {fu_id} @ ({lat}, {lon})")

        location = wgs84.latlon(lat, lon, 0.0)
        fu_schedule = []

        for norad_id, sat in satellites_data.items():
            satellite = EarthSatellite(
                sat["line1"],
                sat["line2"],
                sat["name"],
                ts
            )

            passes = find_passes(
                satellite,
                location,
                ts,
                now_utc,
                hours=SCHEDULE_HOURS
            )

            for p in passes:
                p.update({
                    "fu_id": fu_id,
                    "norad_id": norad_id,
                    "satellite": sat["name"]
                })

            fu_schedule.extend(passes)

        full_schedule[fu_id] = {
            "fu_id": fu_id,
            "location": loc,
            "generated_at": datetime.now(IST).isoformat(),
            "schedule": sorted(
                fu_schedule,
                key=lambda x: x["start_time"]
            )
        }

        print(f"[SCHEDULE] FU {fu_id}: {len(fu_schedule)} passes")

    os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(full_schedule, f, indent=4)

    print(f"\n✅ Schedule generated for {len(full_schedule)} FUs")
    print(f"📁 Saved to {SCHEDULE_FILE}")


# ==============================
# ENTRY POINT
# ==============================
if __name__ == "__main__":
    generate_schedule()
