

from datetime import datetime, timedelta, timezone
IST = timezone(timedelta(hours=5, minutes=30))
MIN_ELEVATION_DEG = 0.0


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

        if event == 0:
            current_pass = {
                "start_time": t_local.isoformat()
            }

        elif event == 1 and current_pass is not None:
            alt, _, _ = (satellite - location).at(ti).altaz()
            current_pass["max_elevation_deg"] = round(alt.degrees, 2)

        elif event == 2 and current_pass is not None:
            current_pass["end_time"] = t_local.isoformat()
            passes.append(current_pass)
            current_pass = None

    return passes
