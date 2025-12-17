
import json
import os
import logging
from datetime import datetime, timezone, timedelta
from skyfield.api import load, wgs84, EarthSatellite
from Scheduler.Pass_Generator import find_passes
from Central_Unit.Assigner import assign_passes

from log_utils import get_logger
logger = get_logger("scheduler")
SATELLITES_FILE = "data/tles.json"
ACTIVE_FUS_FILE = "data/active_fus.json"
SCHEDULE_FILE = "data/schedule.json"
SCHEDULE_HOURS = 24

IST = timezone(timedelta(hours=5, minutes=30))


def generate_schedule():
    logger.info("Scheduler started")

    if not os.path.exists(SATELLITES_FILE):
        logger.error("Missing satellites file: %s", SATELLITES_FILE)
        raise FileNotFoundError(SATELLITES_FILE)

    if not os.path.exists(ACTIVE_FUS_FILE):
        logger.error("Missing active FUs file: %s", ACTIVE_FUS_FILE)
        raise FileNotFoundError(ACTIVE_FUS_FILE)

    with open(SATELLITES_FILE, "r") as f:
        satellites_data = json.load(f)

    with open(ACTIVE_FUS_FILE, "r") as f:
        fus_data = json.load(f)

    logger.info("Loaded %d satellites", len(satellites_data))
    logger.info("Detected %d active FUs", len(fus_data))

    ts = load.timescale()
    now_utc = datetime.now(timezone.utc)

    full_schedule = {}

    for fu_id, fu in fus_data.items():
        loc = fu.get("location", {})
        lat = loc.get("latitude")
        lon = loc.get("longitude")

        if lat is None or lon is None:
            logger.warning("FU %s missing location, skipping", fu_id)
            continue

        logger.info("Scheduling FU %s at lat=%s lon=%s", fu_id, lat, lon)

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

            logger.debug(
                "FU %s | %s (%s): %d passes",
                fu_id,
                sat["name"],
                norad_id,
                len(passes)
            )

            for p in passes:
                p.update({
                    "fu_id": fu_id,
                    "norad_id": norad_id,
                    "satellite": sat["name"]
                })

            fu_schedule.extend(passes)

        fu_schedule.sort(key=lambda x: x["start_time"])

        full_schedule[fu_id] = {
            "fu_id": fu_id,
            "location": loc,
            "generated_at": datetime.now(IST).isoformat(),
            "schedule": fu_schedule
        }

        logger.info(
            "FU %s scheduling complete: %d total passes",
            fu_id,
            len(fu_schedule)
        )

    os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(full_schedule, f, indent=4)

    logger.info(
        "Scheduler finished: %d FUs scheduled, output=%s",
        len(full_schedule),
        SCHEDULE_FILE
    )

    logger.info("Running assignment phase")
    assign_passes()
    logger.info("Assignment phase completed")
