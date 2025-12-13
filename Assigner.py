import json
import itertools

REGISTRY_FILE = "data/active_fus.json"
SCHEDULE_FILE = "data/schedule.json"
ASSIGN_FILE = "data/assignments.json"

def assign_passes():
    with open(SCHEDULE_FILE) as f:
        schedule = json.load(f)
    with open(REGISTRY_FILE) as f:
        fus = json.load(f)

    if not fus:
        print("[WARN] No active FUs found.")
        return

    fu_ids = list(fus.keys())
    assignments = {fid: [] for fid in fu_ids}
    cycle = itertools.cycle(fu_ids)

    for entry in schedule:
        assigned_fu = next(cycle)
        assignments[assigned_fu].append(entry)

    with open(ASSIGN_FILE, "w") as f:
        json.dump(assignments, f, indent=4)

    print(f"[ASSIGNER] Assigned {len(schedule)} passes to {len(fu_ids)} FUs")

if __name__ == "__main__":
    assign_passes()