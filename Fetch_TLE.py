#!/usr/bin/env python3
"""
update_tles.py — Fetch and update ALL active satellite TLEs from Celestrak.

Runs periodically (e.g. once every 24 hours via APScheduler).
"""

import os
import json
import requests

# ==============================
# CONFIGURATION
# ==============================
SATELLITES_FILE = "data/satellites.json"

# Source of TLE data
# (You can change this to 'https://celestrak.org/NORAD/elements/gp.php?GROUP=all&FORMAT=tle'
# if you want every single object, not just active ones.)
TLE_SOURCE_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"

# ==============================
# FETCH ALL TLEs
# ==============================


def fetch_all_tles():
    """Fetch all active satellite TLEs from Celestrak and store locally."""
    os.makedirs(os.path.dirname(SATELLITES_FILE), exist_ok=True)

    print(f"[INFO] Fetching TLE data from {TLE_SOURCE_URL} ...")
    try:
        response = requests.get(TLE_SOURCE_URL, timeout=20)
        response.raise_for_status()
        text = response.text.strip()
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch TLEs: {e}")
        return

    lines = text.splitlines()
    satellites = {}
    count = 0

    # Parse TLEs (3 lines per satellite)
    for i in range(0, len(lines), 3):
        if i + 2 >= len(lines):
            break
        name = lines[i].strip()
        line1 = lines[i + 1].strip()
        line2 = lines[i + 2].strip()
        if line1.startswith("1 ") and line2.startswith("2 "):
            satellites[name] = {"line1": line1, "line2": line2}
            count += 1

    # Save to JSON
    with open(SATELLITES_FILE, "w") as f:
        json.dump(satellites, f, indent=2)

    print(f"\n✅ Saved {count} satellites to {SATELLITES_FILE}")


if __name__ == "__main__":
    fetch_all_tles()
