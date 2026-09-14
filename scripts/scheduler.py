"""Pipe queue scheduler: turns backlog rows into a per-machine sequence.

See docs/manufaktur-queue-design.md for the full design.
Run: python scripts/scheduler.py
"""
import csv
import os
from collections import defaultdict

MOLD_CHANGE_DAYS = 0.5
WORKDAY_HOURS = 8
RECONFIG_DAYS = 1 / WORKDAY_HOURS

# size -> (machine, pieces per day). Machine None = shared between MESIN 4
# and MESIN 6, resolved per dataset in resolve_machine_assignment().
# Any size missing here makes load_jobs() fail loudly — add it, don't guess.
SIZES = {
    '1/2"':   ("MESIN 2", 130),
    '5/8"':   ("MESIN 2", 130),
    '3/4"':   ("MESIN 1", 130),
    '1"':     (None,      100),
    '1 1/4"': ("MESIN 3", 100),
    '1 1/2"': ("MESIN 5", 100),
    '2"':     ("MESIN 4", 100),
    '2 1/2"': ("MESIN 7", 100),
    '3"':     ("MESIN 7", 100),
}
SPLIT_SIZE = '1"'
SPLIT_MACHINES = ("MESIN 4", "MESIN 6")


def load_jobs(csv_path):
    """Read a rebuilt schedule CSV, keep round non-fulfilled orders only.
    Each job carries `days` = qty / rate so every later step orders by time."""
    jobs, unknown = [], set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            size = row["size"].replace("-", " ").strip()
            if "X" in size:
                continue  # square/rect, out of v1 scope
            berat_total = float(row["berat_total"] or 0)
            if berat_total <= 0:
                continue  # already fulfilled
            if size not in SIZES:
                unknown.add(size)
                continue
            qty = berat_total / float(row["berat_per_pcs"])
            jobs.append({
                "po_no": row["po_no"],
                "thickness": float(row["thickness"]),
                "size": size,
                "qty": qty,
                "days": qty / SIZES[size][1],
            })
    if unknown:
        raise ValueError(f"unknown size(s) {sorted(unknown)} in {csv_path} — add them to SIZES in scheduler.py")
    return jobs


def resolve_machine_assignment(jobs):
    """Assign each job a `mesin`. Fixed sizes come straight from SIZES; 1" jobs
    are balanced between MESIN 4 and MESIN 6, with MESIN 4 pre-loaded with its
    own 2" work plus one mold change so the balance only sends 1" work there
    when that half-day changeover actually pays for itself."""
    split_jobs = [j for j in jobs if j["size"] == SPLIT_SIZE]
    fixed_jobs = [j for j in jobs if j["size"] != SPLIT_SIZE]

    for j in fixed_jobs:
        j["mesin"] = SIZES[j["size"]][0]

    mesin4_days = sum(j["days"] for j in fixed_jobs if j["mesin"] == "MESIN 4")
    load = {
        "MESIN 4": mesin4_days + (MOLD_CHANGE_DAYS if mesin4_days else 0),
        "MESIN 6": 0.0,
    }
    for j in sorted(split_jobs, key=lambda j: -j["days"]):
        target = min(load, key=load.get)
        j["mesin"] = target
        load[target] += j["days"]

    return fixed_jobs + split_jobs


def build_machine_schedule(jobs):
    """Order one machine's jobs: size groups -> thickness sub-groups -> job,
    every level ascending by total days."""
    by_size = defaultdict(list)
    for j in jobs:
        by_size[j["size"]].append(j)
    ordered_sizes = sorted(by_size, key=lambda s: sum(j["days"] for j in by_size[s]))

    ordered = []
    for size in ordered_sizes:
        by_thickness = defaultdict(list)
        for j in by_size[size]:
            by_thickness[j["thickness"]].append(j)
        ordered_thicknesses = sorted(by_thickness, key=lambda t: sum(j["days"] for j in by_thickness[t]))
        for thickness in ordered_thicknesses:
            ordered.extend(sorted(by_thickness[thickness], key=lambda j: j["days"]))
    return ordered


def _event(mesin, po_no, size, thickness, qty, start_day, end_day, event_type):
    return {
        "mesin": mesin, "po_no": po_no, "size": size, "thickness": thickness,
        "qty": qty, "start_day": round(start_day, 3), "end_day": round(end_day, 3),
        "event_type": event_type,
    }


def compute_events(mesin, ordered_jobs):
    """Walk one machine's ordered jobs, emitting production + changeover
    events with day offsets."""
    events = []
    day = 0.0
    prev_size = prev_thickness = None
    for j in ordered_jobs:
        if prev_size is not None and j["size"] != prev_size:
            events.append(_event(mesin, "", j["size"], "", "", day, day + MOLD_CHANGE_DAYS, "mold_change"))
            day += MOLD_CHANGE_DAYS
        if prev_thickness is not None and j["thickness"] != prev_thickness:
            events.append(_event(mesin, "", j["size"], "", "", day, day + RECONFIG_DAYS, "reconfig"))
            day += RECONFIG_DAYS

        events.append(_event(mesin, j["po_no"], j["size"], j["thickness"], round(j["qty"], 2),
                              day, day + j["days"], "production"))
        day += j["days"]
        prev_size, prev_thickness = j["size"], j["thickness"]
    return events


def schedule_year(csv_path):
    """Full pipeline: CSV path -> list of event dicts across all machines."""
    jobs = load_jobs(csv_path)
    jobs = resolve_machine_assignment(jobs)
    by_machine = defaultdict(list)
    for j in jobs:
        by_machine[j["mesin"]].append(j)

    all_events = []
    for mesin in sorted(by_machine):
        ordered = build_machine_schedule(by_machine[mesin])
        all_events.extend(compute_events(mesin, ordered))
    return all_events


EVENT_FIELDS = ["mesin", "po_no", "size", "thickness", "qty", "start_day", "end_day", "event_type"]


def write_schedule_csv(events, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EVENT_FIELDS)
        writer.writeheader()
        writer.writerows(events)


def main():
    os.makedirs("output", exist_ok=True)
    for year, csv_in, csv_out in [
        ("2025", "2025.csv", "output/2025_schedule.csv"),
        ("2026", "2026.csv", "output/2026_schedule.csv"),
    ]:
        events = schedule_year(csv_in)
        write_schedule_csv(events, csv_out)
        print(f"{year}: {len(events)} events -> {csv_out}")


if __name__ == "__main__":
    main()
