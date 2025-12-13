import requests
import json


def fetch_all_tles():
    url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"

    print("[INFO] Fetching TLE data from Celestrak...")
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fecth TLE data: {response.status_code}")

    tle_text = response.text.strip().splitlines()
    tle_data = {}

    print("[INFO] Parsing TLE entries..")
    for i in range(0, len(tle_text), 3):
        if i+2 >= len(tle_text):
            print("[INFO] Incomplete TLE set at lines {i}-{i+2}, skipping.")
            continue
        name = tle_text[i].strip()
        line1 = tle_text[i+1].strip()
        line2 = tle_text[i+2].strip()
        tle_data[name] = {
            "line1": line1,
            "line2": line2
        }

    print(f"[INFO] Parsed {len(tle_data)} satellites. Saving to JSON...")
    with open("satellites.json", "w") as f:
        json.dump(tle_data, f, indent=2)

    print("[SUCCESS] TLE data saved to satellites.json")


if __name__ == "__main__":
    fetch_all_tles()
