import json
import itertools
import os

REGISTRY_FILE = "data/active_fus.json"
SCHEDULE_FILE = "data/schedule.json"
ASSIGN_FILE = "data/assignments.json"


def assign_passes():
    if not os.path.exists(SCHEDULE_FILE):
        print("[ASSIGNER] Missing schedule.json")
        return

    if not os.path.exists(REGISTRY_FILE):
        print("[ASSIGNER] Missing active_fus.json")
        return

    with open(SCHEDULE_FILE) as f:
        schedule_data = json.load(f)

    with open(REGISTRY_FILE) as f:
        fus = json.load(f)

    fu_ids = list(fus.keys())
    if not fu_ids:
        print("[ASSIGNER] No active FUs found")
        return

    # Flatten all passes across all FUs / satellites
    all_passes = []
    for fu_block in schedule_data.values():
        all_passes.extend(fu_block.get("schedule", []))

    if not all_passes:
        print("[ASSIGNER] No passes to assign")
        return

    assignments = {fid: [] for fid in fu_ids}
    cycle = itertools.cycle(fu_ids)

    for p in all_passes:
        assigned_fu = next(cycle)
        assignments[assigned_fu].append(p)

    os.makedirs(os.path.dirname(ASSIGN_FILE), exist_ok=True)
    with open(ASSIGN_FILE, "w") as f:
        json.dump(assignments, f, indent=4)

    print(
        f"[ASSIGNER] Assigned {len(all_passes)} passes "
        f"to {len(fu_ids)} FUs"
    )
