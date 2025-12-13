import json
from pathlib import Path
from log_utils import log_event

SAT_NAME_FILE = Path("data/satellite_name.json")


def get_satellite_name():

    print("=== Satellite Fetch Utility ===")
    sat_name = "NOAA 15"

    if not sat_name:
        print("[ERROR] Satellite name cannot be empty")
        return None

    return sat_name


def save_satellite_name(name):

    SAT_NAME_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SAT_NAME_FILE.open("w") as f:
        json.dump({"satellite_name": name}, f, indent=4)

    log_event(f"Satellite name '{name}' saved to {SAT_NAME_FILE}")


if __name__ == "__main__":
    satellite_name = get_satellite_name()

    if satellite_name:
        save_satellite_name(satellite_name)
        print(
            f"[INFO] Satellite '{satellite_name}' saved. Ready for scheduling.")

    else:
        print("[ABORTED] No satellite name  provided")
