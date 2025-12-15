#!/usr/bin/env python3
"""
update_tles.py — Fetch and update TLEs for specific NORAD IDs
"""

import os
import json
import requests
from itertools import islice

# ==============================
# CONFIGURATION
# ==============================
INPUT_FILE = "data/users_cache.json"
OUTPUT_FILE = "data/tles.json"

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php"
BATCH_SIZE = 50  # Celestrak is happier with batches

# ==============================
# HELPERS
# ==============================


def chunked(iterable, size):
    """Yield successive chunks from iterable."""
    it = iter(iterable)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            return
        yield chunk


def load_norad_ids(path):
    """Extract unique NORAD IDs from your JSON structure."""
    with open(path, "r") as f:
        data = json.load(f)

    norad_ids = set()
    for entry in data:
        norad_ids.update(entry.get("satids", []))

    return sorted(norad_ids)


def fetch_tles_for_ids(norad_ids):
    """Fetch TLEs one NORAD ID at a time (most reliable)."""
    tles = {}

    for norad_id in norad_ids:
        url = f"{CELESTRAK_URL}?CATNR={norad_id}"

        print(f"[INFO] Fetching TLE for NORAD {norad_id}")
        response = requests.get(url, timeout=20)
        response.raise_for_status()

        lines = [l.rstrip() for l in response.text.splitlines() if l.strip()]

        if len(lines) < 3:
            print(f"[WARN] No TLE found for NORAD {norad_id}")
            continue

        # Expected format:
        # NAME
        # 1 xxxxx
        # 2 xxxxx
        name = lines[0]
        line1 = lines[1]
        line2 = lines[2]

        if not (line1.startswith("1 ") and line2.startswith("2 ")):
            print(f"[WARN] Invalid TLE format for NORAD {norad_id}")
            continue

        tles[norad_id] = {
            "name": name,
            "line1": line1,
            "line2": line2
        }

    return tles


# ==============================
# MAIN
# ==============================

def update_tles():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    norad_ids = load_norad_ids(INPUT_FILE)
    print(f"[INFO] Found {len(norad_ids)} unique NORAD IDs")

    tles = fetch_tles_for_ids(norad_ids)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(tles, f, indent=2)

    print(f"\n✅ Saved {len(tles)} TLEs to {OUTPUT_FILE}")


if __name__ == "__main__":
    update_tles()
