import json
from pathlib import Path

CACHE_FILE = Path("users_cache.json")


def save(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)


def load():
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return []
