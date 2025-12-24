import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from skyfield.api import load, wgs84, EarthSatellite

from log_utils import get_logger
from Scheduler.Pass_Generator import find_visibility_windows
from Assigner import assign_passes


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))

SATELLITES_FILE = os.path.join(DATA_DIR, "tles.json")
ACTIVE_FUS_FILE = os.path.join(DATA_DIR, "active_fus.json")
SCHEDULE_FILE = os.path.join(DATA_DIR, "schedule.json")

logger = get_logger("scheduler")

SCHEDULE_HOURS = 24
IST = timezone(timedelta(hours=5, minutes=30))


def generate_schedule():
    logger.info("Scheduler started")

    if not os.path.exists(SATELLITES_FILE):
        raise FileNotFoundError(SATELLITES_FILE)

    if not os.path.exists(ACTIVE_FUS_FILE):
        raise FileNotFoundError(ACTIVE_FUS_FILE)

    with open(SATELLITES_FILE) as f:
        satellites = json.load(f)

    with open(ACTIVE_FUS_FILE) as f:
        fus = json.load(f)

    ts = load.timescale()
    now_utc = datetime.now(timezone.utc)

    activity_plan = {}

    for fu_id, fu in fus.items():
        loc = fu.get("location", {})
        lat = loc.get("latitude")
        lon = loc.get("longitude")

        if lat is None or lon is None:
            logger.warning("FU %s missing location", fu_id)
            continue

        logger.info("Planning activities for FU %s", fu_id)

        location = wgs84.latlon(lat, lon, 0.0)
        activities = []

        for norad_id, sat in satellites.items():
            satellite = EarthSatellite(
                sat["line1"],
                sat["line2"],
                sat["name"],
                ts
            )

            windows = find_visibility_windows(
                satellite,
                location,
                ts,
                now_utc,
                hours=SCHEDULE_HOURS
            )

            for w in windows:
                activities.append({
                    "activity_id": str(uuid.uuid4()),
                    "type": "TRACK",
                    "fu_id": fu_id,
                    "satellite": sat["name"],
                    "norad_id": norad_id,
                    "start_time": w["start_time"],
                    "end_time": w["end_time"],
                    "max_elevation_deg": w.get("max_elevation_deg"),
                    "state": "PLANNED"
                })

        activities.sort(key=lambda x: x["start_time"])
        activity_plan[fu_id] = activities

        logger.info(
            "FU %s planned %d activities",
            fu_id,
            len(activities)
        )

    os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(activity_plan, f, indent=2)

    logger.info(
        "Planning complete: %d FUs, output=%s",
        len(activity_plan),
        SCHEDULE_FILE
    )

    # Assignment phase (resource arbitration, conflicts, priorities)
    logger.info("Starting assignment phase")
    assign_passes()
    logger.info("Assignment phase completed")
