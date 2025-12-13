from skyfield.api import EarthSatellite, load


ts = load.timescale()


def load_tle(json_path):
    import json
    from pathlib import Path

    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"TLE File not found: {json_path}")

    with path.open("r") as f:
        return json.load(f)


def create_satellite(line1, line2):
    print(f"[DEBUG] Line1 ({len(line1)}): {repr(line1)}")
    print(f"[DEBUG] Line2 ({len(line2)}): {repr(line2)}")
    return EarthSatellite(line1, line2, name="NOAA 15", ts=ts)
