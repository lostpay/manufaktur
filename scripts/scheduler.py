"""Pipe queue scheduler: turns backlog rows into a per-machine sequence,
plus the delivery timeline that sequence implies.

See docs/manufaktur-queue-design.md for the full design.
Run: python scripts/scheduler.py [--mode shortest|fill|both]
"""
import argparse
import csv
import os
from collections import defaultdict

MOLD_CHANGE_DAYS = 0.5
WORKDAY_HOURS = 8
RECONFIG_DAYS = 1 / WORKDAY_HOURS
DELIVERY_BATCH_KG = 8000     # a truck leaves once this much finished product is ready

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

# Tie-break order applied at every level (size group, thickness sub-group,
# job). Grouping by size/thickness is mandatory in both modes; this only
# decides the order of the groups and of the jobs inside them.
MODES = {
    "shortest": lambda days, kg: days,        # shortest first: small orders clear early
    "fill":     lambda days, kg: -kg / days,  # heaviest kg/day first: hit the next 8 t sooner
}


def load_jobs(csv_path):
    """Read a rebuilt schedule CSV, keep round non-fulfilled orders only.
    Each job carries `days` = qty / rate and `kg` (finished weight, taken
    as the raw material weight — no forming loss assumed)."""
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
                "kg": berat_total,
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


def build_machine_schedule(jobs, mode="shortest"):
    """Order one machine's jobs: size groups -> thickness sub-groups -> job,
    every level ordered by the mode's key over (total days, total kg)."""
    key = MODES[mode]

    def group_key(group):
        return key(sum(j["days"] for j in group), sum(j["kg"] for j in group))

    by_size = defaultdict(list)
    for j in jobs:
        by_size[j["size"]].append(j)

    ordered = []
    for size in sorted(by_size, key=lambda s: group_key(by_size[s])):
        by_thickness = defaultdict(list)
        for j in by_size[size]:
            by_thickness[j["thickness"]].append(j)
        for thickness in sorted(by_thickness, key=lambda t: group_key(by_thickness[t])):
            ordered.extend(sorted(by_thickness[thickness], key=lambda j: key(j["days"], j["kg"])))
    return ordered


def _event(mesin, po_no, size, thickness, qty, kg, start_day, end_day, event_type):
    return {
        "mesin": mesin, "po_no": po_no, "size": size, "thickness": thickness,
        "qty": qty, "kg": kg, "start_day": round(start_day, 3), "end_day": round(end_day, 3),
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
            events.append(_event(mesin, "", j["size"], "", "", "", day, day + MOLD_CHANGE_DAYS, "mold_change"))
            day += MOLD_CHANGE_DAYS
        if prev_thickness is not None and j["thickness"] != prev_thickness:
            events.append(_event(mesin, "", j["size"], "", "", "", day, day + RECONFIG_DAYS, "reconfig"))
            day += RECONFIG_DAYS

        events.append(_event(mesin, j["po_no"], j["size"], j["thickness"], round(j["qty"], 2),
                              round(j["kg"], 1), day, day + j["days"], "production"))
        day += j["days"]
        prev_size, prev_thickness = j["size"], j["thickness"]
    return events


def compute_deliveries(events, batch_kg=DELIVERY_BATCH_KG):
    """Days on which cumulative finished weight (all machines, one shared
    clock) crosses each multiple of batch_kg. Each production event is taken
    to produce its kg evenly between start_day and end_day."""
    prod = [(float(e["start_day"]), float(e["end_day"]), float(e["kg"]))
            for e in events if e["event_type"] == "production"]
    if not prod:
        return []
    breakpoints = sorted({t for s, e, _ in prod for t in (s, e)})
    total = sum(kg for _, _, kg in prod)

    deliveries, cum, next_no = [], 0.0, 1
    for t0, t1 in zip(breakpoints, breakpoints[1:]):
        rate = sum(kg / (e - s) for s, e, kg in prod if s <= t0 and e >= t1 and e > s)
        if rate == 0:
            continue
        cum_end = cum + rate * (t1 - t0)
        while next_no * batch_kg <= cum_end + 1e-9:
            day = t0 + (next_no * batch_kg - cum) / rate
            deliveries.append({"delivery_no": next_no, "day": round(day, 2),
                               "cumulative_kg": next_no * batch_kg, "batch_kg": batch_kg})
            next_no += 1
        cum = cum_end

    leftover = total - (next_no - 1) * batch_kg
    deliveries.append({"delivery_no": "leftover", "day": round(breakpoints[-1], 2),
                       "cumulative_kg": round(total), "batch_kg": round(leftover)})
    return deliveries


def schedule_year(csv_path, mode="shortest"):
    """Full pipeline: CSV path -> list of event dicts across all machines."""
    jobs = load_jobs(csv_path)
    jobs = resolve_machine_assignment(jobs)
    by_machine = defaultdict(list)
    for j in jobs:
        by_machine[j["mesin"]].append(j)

    all_events = []
    for mesin in sorted(by_machine):
        ordered = build_machine_schedule(by_machine[mesin], mode)
        all_events.extend(compute_events(mesin, ordered))
    return all_events


EVENT_FIELDS = ["mesin", "po_no", "size", "thickness", "qty", "kg", "start_day", "end_day", "event_type"]
DELIVERY_FIELDS = ["delivery_no", "day", "cumulative_kg", "batch_kg"]


def write_csv(rows, fields, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_modes(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=[*MODES, "both"], default="both",
                        help="tie-break order: shortest job first, fill 8 t batches first, or both (default)")
    args = parser.parse_args(argv)
    return list(MODES) if args.mode == "both" else [args.mode]


def main(argv=None):
    os.makedirs("output", exist_ok=True)
    for mode in parse_modes(argv):
        for year in ("2025", "2026"):
            events = schedule_year(f"{year}.csv", mode)
            deliveries = compute_deliveries(events)
            write_csv(events, EVENT_FIELDS, f"output/{year}_{mode}_schedule.csv")
            write_csv(deliveries, DELIVERY_FIELDS, f"output/{year}_{mode}_deliveries.csv")
            trucks = [d for d in deliveries if d["delivery_no"] != "leftover"]
            first = f"first truck day {trucks[0]['day']}" if trucks else "no full truck"
            print(f"{year} {mode:8s}: {len(events)} events, {len(trucks)} deliveries ({first}), "
                  f"{deliveries[-1]['batch_kg']} kg left over -> output/{year}_{mode}_*.csv")


if __name__ == "__main__":
    main()
