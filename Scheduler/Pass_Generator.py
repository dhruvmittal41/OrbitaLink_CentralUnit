from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
MIN_ELEVATION_DEG = 0.0


def find_visibility_windows(satellite, location, ts, start_time, hours):
    """
    Compute visibility windows for a satellite from a given location.
    Returns a list of visibility windows (not commands).
    """
    t0 = ts.from_datetime(start_time)
    t1 = ts.from_datetime(start_time + timedelta(hours=hours))

    times, events = satellite.find_events(
        location, t0, t1, altitude_degrees=MIN_ELEVATION_DEG
    )

    windows = []
    current = None

    for ti, event in zip(times, events):
        t_local = ti.utc_datetime().astimezone(IST)

        if event == 0:  # AOS
            current = {
                "start_time": t_local.isoformat()
            }

        elif event == 1 and current is not None:  # MAX
            alt, _, _ = (satellite - location).at(ti).altaz()
            current["max_elevation_deg"] = round(alt.degrees, 2)

        elif event == 2 and current is not None:  # LOS
            current["end_time"] = t_local.isoformat()
            windows.append(current)
            current = None

    return windows
