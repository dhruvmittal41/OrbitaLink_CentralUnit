"""
sat_tracker.py
Simple TLE -> az/el tracker that sends az:.. el:.. commands to Arduino over serial.

Usage:
 - Edit USER_* below with your groundstation values and COM port.
 - Run: python sat_tracker.py
 - Input either a NORAD ID (e.g. 25544) or paste two-line TLE when prompted.
"""

import time
import requests
import serial
import sys
import math
from skyfield.api import Loader, EarthSatellite, wgs84, N, S, E, W
from datetime import datetime, timezone

# ===== USER CONFIG =====
# Windows example: 'COM3'. On Linux/mac use '/dev/ttyUSB0' or '/dev/ttyACM0'
SERIAL_PORT = 'COM13'
SERIAL_BAUD = 115200
UPDATE_INTERVAL = 1.0     # seconds between updates (1.0 is okay)
MIN_AZ_CHANGE = 0.1       # degrees: only send if az changed by more than this
MIN_EL_CHANGE = 0.1       # degrees

# Ground station location: set to your site
USER_LAT_DEG = 28.6139    # example: New Delhi
USER_LON_DEG = 77.2090
USER_ELEV_M = 216       # meters above mean sea level

# ===== End user config =====

load = Loader('.', expire=False)
ts = load.timescale()


def fetch_tle_from_celestrak(norad_id):
    # Celestrak TLE by NORAD ID can be got from https://celestrak.com/NORAD/elements/gp.php?CATNR=xxxx
    url = f'https://celestrak.com/NORAD/elements/gp.php?CATNR={int(norad_id)}'
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to fetch TLE (HTTP {r.status_code})")
    # result includes header line; parse lines with length > 0
    lines = [ln.strip() for ln in r.text.splitlines() if ln.strip()]
    if len(lines) >= 2:
        # If only two lines returned use them; if three, assume first is name
        if len(lines) == 2:
            return lines[0], lines[1]
        else:
            return lines[-2], lines[-1]
    raise RuntimeError("Unexpected TLE format from celestrak")


def get_satellite_from_input():
    # Ask user for either NORAD id or TLE
    print("Enter NORAD ID (e.g. 25544) OR paste two-line TLE (enter blank line after TLE):")
    user = input().strip()
    if user.isdigit():
        norad = int(user)
        print(f"Fetching TLE for NORAD ID {norad} ...")
        line1, line2 = fetch_tle_from_celestrak(norad)
        name = f"CAT{norad}"
    else:
        # treat first line as name (optional) then read two-line TLE
        name = user if user and (not user.startswith('1 ')) else "SAT"
        # if first input is TLE line1 (starts with '1 '), then treat that as line1
        if user.startswith('1 '):
            line1 = user
            print("Enter TLE line 2:")
            line2 = input().strip()
        else:
            # not NORAD and not TLE line: ask for two TLE lines explicitly
            print("Enter TLE line 1:")
            line1 = input().strip()
            print("Enter TLE line 2:")
            line2 = input().strip()
    # Validate crude TLE format
    if not (line1.startswith('1 ') and line2.startswith('2 ')):
        print("Warning: TLE lines don't start with '1 ' and '2 '. Proceeding anyway.")
    return name, line1, line2


def az_el_from_sat(ts, sat, observer):
    """
    Return (az_deg, el_deg, timestamp) for the satellite `sat` as seen from
    `observer` (a wgs84.latlon object). Uses ts.now() for current time.
    """
    # use skyfield timescale now() (timezone-aware internally)
    t = ts.now()

    # compute topocentric position of satellite relative to observer:
    # (sat - observer).at(t) gives topocentric position for that time
    topocentric = (sat - observer).at(t)

    # altaz returns (altitude, azimuth, distance)
    alt, az, distance = topocentric.altaz()

    az_deg = az.degrees % 360.0
    el_deg = alt.degrees

    # return az, el and a python datetime (UTC)
    return az_deg, el_deg, t.utc_datetime()


def open_serial(port, baud=115200, timeout=1.0):
    try:
        ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(1.0)  # allow Arduino reset if it does on open
        # flush any startup text
        ser.flushInput()
        ser.flushOutput()
        return ser
    except Exception as e:
        raise RuntimeError(f"Cannot open serial port {port}: {e}")


def main():

    print("Select mode:")
    print("  A - Automatic satellite tracking")
    print("  M - Manual az/el control")
    mode = input("Mode [A/M]: ").strip().lower()

    print(f"Opening serial {SERIAL_PORT} @ {SERIAL_BAUD}...")
    ser = open_serial(SERIAL_PORT, SERIAL_BAUD)

    if mode == 'm':
        manual_control(ser)
        ser.close()
        return
    # get satellite
    name, line1, line2 = get_satellite_from_input()
    print("Using TLE:")
    print(line1)
    print(line2)

    sat = EarthSatellite(line1, line2, name, ts)

    # observer location
    lat = USER_LAT_DEG
    lon = USER_LON_DEG
    elev = USER_ELEV_M
    observer = wgs84.latlon(lat, lon, elevation_m=elev)

    # open serial
    print(f"Opening serial {SERIAL_PORT} @ {SERIAL_BAUD}...")
    ser = open_serial(SERIAL_PORT, SERIAL_BAUD)

    last_az = None
    last_el = None

    print("Tracking started. Press Ctrl+C to stop.")
    try:
        while True:
            az_deg, el_deg, dt = az_el_from_sat(ts, sat, observer)
            # Skyfield alt can be negative (below horizon). Convert logic: clamp or still send?
            # We'll send clamped EL in range 0..180 as your Arduino code expects 0..90 and flip for >90..180
            # Keep el in [-90, 180) to allow flip maneuver for >90 if desired.
            # But to avoid huge negative values, clamp to -10..180
            if el_deg < -10:

                el_deg = -1 * el_deg
                # clamp to max 179.9
                el_send = max(min(el_deg, 179.9), -10.0)
                az_send = az_deg
                # only send if change big enough
                send = False
                if last_az is None or abs(az_send - last_az) >= MIN_AZ_CHANGE:
                    send = True
                if last_el is None or abs(el_send - last_el) >= MIN_EL_CHANGE:
                    send = True
                if send:
                    cmd = f"az:{az_send:.2f} el:{el_send:.2f}\n"
                    ser.write(cmd.encode('utf-8'))
                    # optional: read Arduino response if any
                    time.sleep(0.02)
                    if ser.in_waiting:
                        out = ser.read(ser.in_waiting).decode(errors='ignore')
                        print("ARDUINO:", out.strip())
                    print(f"{dt.isoformat()} -> SENT: {cmd.strip()}")
                    last_az = az_send
                    last_el = el_send
            time.sleep(UPDATE_INTERVAL)
    except KeyboardInterrupt:
        print("Stopping tracking.")
    finally:
        try:
            ser.close()
        except:
            pass


def manual_control(ser):
    """
    Manual mode: user types az el values directly.
    Example input: 180 45
    Type 'q' to quit manual mode.
    """
    print("\nMANUAL MODE")
    print("Enter az el (degrees), e.g.: 180 45")
    print("Type 'q' to quit manual mode\n")

    while True:
        user = input("AZ EL > ").strip().lower()
        if user in ('q', 'quit', 'exit'):
            print("Exiting manual mode.")
            break

        try:
            az, el = map(float, user.split())
            az = az % 360.0
            el = max(min(el, 179.9), -10.0)

            cmd = f"az:{az:.2f} el:{el:.2f}\n"
            ser.write(cmd.encode('utf-8'))
            time.sleep(0.02)

            if ser.in_waiting:
                out = ser.read(ser.in_waiting).decode(errors='ignore')
                print("ARDUINO:", out.strip())

            print(f"SENT: {cmd.strip()}")

        except ValueError:
            print("Invalid input. Format: az el (e.g. 123.4 56.7)")


if __name__ == "__main__":
    main()
