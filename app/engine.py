"""Scheduling engine: pure functions over job dicts and a settings dict.
Rules: docs/manufaktur-queue-design.md. No I/O, no module constants —
everything tunable is in `settings` (see DEFAULT_SETTINGS)."""
from collections import defaultdict

DEFAULT_SETTINGS = {
    "mold_change_days": 0.5,
    "reconfig_hours": 1.0,
    "workday_hours": 8.0,
    "batch_kg": 8000,
    "machines": [f"MESIN {i}" for i in range(1, 8)],
    # size -> machines that can mold it (2+ = shared, balanced at schedule time), pieces/day
    "sizes": {
        '1/2"':   {"machines": ["MESIN 2"], "rate": 130},
        '5/8"':   {"machines": ["MESIN 2"], "rate": 130},
        '3/4"':   {"machines": ["MESIN 1"], "rate": 130},
        '1"':     {"machines": ["MESIN 4", "MESIN 6"], "rate": 100},
        '1 1/4"': {"machines": ["MESIN 3"], "rate": 100},
        '1 1/2"': {"machines": ["MESIN 5"], "rate": 100},
        '2"':     {"machines": ["MESIN 4"], "rate": 100},
        '2 1/2"': {"machines": ["MESIN 7"], "rate": 100},
        '3"':     {"machines": ["MESIN 7"], "rate": 100},
    },
    "ignored_sizes": [],   # sizes deliberately not scheduled (square sections until they get rates)
}

# tie-break key applied at every grouping level; grouping itself is fixed
MODES = {
    "shortest": lambda days, kg: days,        # shortest first: small orders clear early
    "fill":     lambda days, kg: -kg / days,  # heaviest kg/day first: reach the next batch sooner
}


def make_job(order, settings):
    """Order (with remaining_kg) -> job dict, or None if it can't be scheduled."""
    size = order["size"]
    if (size in settings["ignored_sizes"] or size not in settings["sizes"]
            or order["remaining_kg"] <= 0 or order["berat_per_pcs"] <= 0):
        return None
    qty = order["remaining_kg"] / order["berat_per_pcs"]
    return {**order, "qty": qty, "kg": order["remaining_kg"], "days": qty / settings["sizes"][size]["rate"]}


def assign_machines(jobs, settings):
    """Fixed sizes go to their one machine. A shared size is balanced across
    its machines: each starts at its fixed-size load plus one mold change if
    that load is non-zero, jobs go largest-first to the lowest load."""
    sizes = settings["sizes"]
    fixed = [j for j in jobs if len(sizes[j["size"]]["machines"]) == 1]
    shared = defaultdict(list)
    for j in jobs:
        if len(sizes[j["size"]]["machines"]) > 1:
            shared[j["size"]].append(j)

    load = defaultdict(float)
    for j in fixed:
        j["mesin"] = sizes[j["size"]]["machines"][0]
        load[j["mesin"]] += j["days"]

    for size, group in shared.items():
        machines = sizes[size]["machines"]
        seeded = {m: load[m] + (settings["mold_change_days"] if load[m] else 0.0) for m in machines}
        for j in sorted(group, key=lambda j: -j["days"]):
            j["mesin"] = min(seeded, key=seeded.get)
            seeded[j["mesin"]] += j["days"]
        for m in machines:
            load[m] = seeded[m]
    return jobs


def order_machine(jobs, mode="shortest"):
    """size groups -> thickness sub-groups -> jobs, every level by the mode key."""
    key = MODES[mode]

    def group_key(group):
        return key(sum(j["days"] for j in group), sum(j["kg"] for j in group))

    by_size = defaultdict(list)
    for j in jobs:
        by_size[j["size"]].append(j)
    ordered = []
    for size in sorted(by_size, key=lambda s: group_key(by_size[s])):
        by_t = defaultdict(list)
        for j in by_size[size]:
            by_t[j["thickness"]].append(j)
        for t in sorted(by_t, key=lambda t: group_key(by_t[t])):
            ordered.extend(sorted(by_t[t], key=lambda j: key(j["days"], j["kg"])))
    return ordered


def _event(mesin, j, start, end, event_type):
    is_prod = event_type == "production"
    return {"mesin": mesin, "order_id": j["order_id"] if is_prod else "", "po_no": j["po_no"] if is_prod else "",
            "size": j["size"], "thickness": j["thickness"] if is_prod else "",
            "qty": round(j["qty"], 2) if is_prod else "", "kg": round(j["kg"], 1) if is_prod else "",
            "start_day": round(start, 3), "end_day": round(end, 3), "event_type": event_type}


def machine_events(mesin, ordered_jobs, settings):
    mold, reconfig = settings["mold_change_days"], settings["reconfig_hours"] / settings["workday_hours"]
    events, day, prev_size, prev_t = [], 0.0, None, None
    for j in ordered_jobs:
        if prev_size is not None and j["size"] != prev_size:
            events.append(_event(mesin, j, day, day + mold, "mold_change")); day += mold
        if prev_t is not None and j["thickness"] != prev_t:
            events.append(_event(mesin, j, day, day + reconfig, "reconfig")); day += reconfig
        events.append(_event(mesin, j, day, day + j["days"], "production")); day += j["days"]
        prev_size, prev_t = j["size"], j["thickness"]
    return events


def schedule(jobs, settings, mode="shortest"):
    """All jobs -> events across every machine, machines in settings order."""
    by_machine = defaultdict(list)
    for j in assign_machines(jobs, settings):
        by_machine[j["mesin"]].append(j)
    events = []
    for mesin in sorted(by_machine, key=lambda m: (settings["machines"] + [m]).index(m)):
        events.extend(machine_events(mesin, order_machine(by_machine[mesin], mode), settings))
    return events


def deliveries(events, batch_kg):
    """Days on which cumulative finished kg (all machines, one clock) crosses
    each multiple of batch_kg; kg accrues evenly along each production bar."""
    prod = [(float(e["start_day"]), float(e["end_day"]), float(e["kg"]))
            for e in events if e["event_type"] == "production"]
    if not prod:
        return []
    points = sorted({t for s, e, _ in prod for t in (s, e)})
    total = sum(kg for _, _, kg in prod)
    out, cum, n = [], 0.0, 1
    for t0, t1 in zip(points, points[1:]):
        rate = sum(kg / (e - s) for s, e, kg in prod if s <= t0 and e >= t1 and e > s)
        if rate == 0:
            continue
        cum_end = cum + rate * (t1 - t0)
        while n * batch_kg <= cum_end + 1e-9:
            out.append({"delivery_no": n, "day": round(t0 + (n * batch_kg - cum) / rate, 2),
                        "cumulative_kg": n * batch_kg, "batch_kg": batch_kg})
            n += 1
        cum = cum_end
    out.append({"delivery_no": "leftover", "day": round(points[-1], 2),
                "cumulative_kg": round(total), "batch_kg": round(total - (n - 1) * batch_kg)})
    return out
