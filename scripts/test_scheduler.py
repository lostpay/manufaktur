"""Plain-assert tests for scheduler.py.

Run: python scripts/test_scheduler.py
"""
from scheduler import (
    SIZES,
    resolve_machine_assignment,
    build_machine_schedule,
    compute_events,
    compute_deliveries,
)


def job(po_no, size, qty, thickness=0.8, kg_per_pc=1.0):
    return {"po_no": po_no, "size": size, "qty": qty, "thickness": thickness,
            "kg": qty * kg_per_pc, "days": qty / SIZES[size][1]}


def prod(start, end, kg, mesin="MESIN 1"):
    return {"mesin": mesin, "start_day": start, "end_day": end, "kg": kg, "event_type": "production"}


def test_resolve_machine_assignment_fixed_sizes():
    resolved = resolve_machine_assignment([job("PO 001", '3/4"', 10)])
    assert resolved[0]["mesin"] == "MESIN 1"


def test_small_1inch_backlog_stays_on_mesin6_when_mesin4_has_2inch_work():
    # MESIN 4: 0.5 day of 2" + 0.5 day mold change = 1.0 seed; 1" backlog is only 0.1 day
    jobs = [job("PO 001", '2"', 50), job("PO 002", '1"', 10)]
    by_po = {j["po_no"]: j["mesin"] for j in resolve_machine_assignment(jobs)}
    assert by_po == {"PO 001": "MESIN 4", "PO 002": "MESIN 6"}


def test_large_1inch_backlog_is_shared_with_mesin4_despite_2inch_work():
    # MESIN 4 seed 1.0 day; 1" backlog is 3x 10 days -> worth paying the mold change
    jobs = [job("PO 001", '2"', 50), job("PO A", '1"', 1000), job("PO B", '1"', 1000), job("PO C", '1"', 1000)]
    by_po = {j["po_no"]: j["mesin"] for j in resolve_machine_assignment(jobs)}
    one_inch = {by_po["PO A"], by_po["PO B"], by_po["PO C"]}
    assert one_inch == {"MESIN 4", "MESIN 6"}


def test_1inch_splits_evenly_when_mesin4_idle():
    jobs = [job("PO 001", '1"', 100), job("PO 002", '1"', 10)]
    by_po = {j["po_no"]: j["mesin"] for j in resolve_machine_assignment(jobs)}
    assert {by_po["PO 001"], by_po["PO 002"]} == {"MESIN 4", "MESIN 6"}


def test_shortest_mode_groups_and_sorts_by_days():
    jobs = [job("PO A", '1/2"', 30), job("PO B", '1/2"', 10), job("PO C", '5/8"', 5)]
    ordered = build_machine_schedule(jobs, "shortest")
    # smaller total-days size group (5/8") goes before the larger (1/2")
    assert [j["po_no"] for j in ordered] == ["PO C", "PO B", "PO A"]


def test_fill_mode_puts_heaviest_kg_per_day_first():
    # same pcs/day everywhere, so kg/day is decided by kg_per_pc: heaviest group and job go first
    jobs = [job("PO A", '1/2"', 30, kg_per_pc=1.0), job("PO B", '1/2"', 10, kg_per_pc=1.5),
            job("PO C", '5/8"', 5, kg_per_pc=1.8)]
    ordered = build_machine_schedule(jobs, "fill")
    assert [j["po_no"] for j in ordered] == ["PO C", "PO B", "PO A"]
    # and the groups are still contiguous: only one size boundary
    sizes = [j["size"] for j in ordered]
    assert sum(1 for a, b in zip(sizes, sizes[1:]) if a != b) == 1


def test_compute_events_adds_mold_change_between_sizes():
    ordered = [job("PO A", '1/2"', 65), job("PO B", '5/8"', 65)]
    events = compute_events("MESIN 2", ordered)
    assert [e["event_type"] for e in events] == ["production", "mold_change", "production"]
    assert events[0]["end_day"] == 0.5     # 65 / 130 pcs/day
    assert events[1]["start_day"] == 0.5
    assert events[1]["end_day"] == 1.0     # +0.5 day mold change
    assert events[2]["start_day"] == 1.0
    assert events[0]["kg"] == 65.0         # kg carried onto the production row


def test_compute_events_adds_reconfig_for_thickness_change_same_size():
    ordered = [job("PO A", '1/2"', 13, thickness=0.8), job("PO B", '1/2"', 13, thickness=1.0)]
    events = compute_events("MESIN 2", ordered)
    assert [e["event_type"] for e in events] == ["production", "reconfig", "production"]
    assert events[1]["end_day"] - events[1]["start_day"] == 0.125   # 1hr / 8hr day


def test_deliveries_cross_batches_on_the_shared_clock():
    # two machines, 5000 kg over 10 days each -> 1000 kg/day combined -> 8 t at day 8, 2 t left over
    events = [prod(0, 10, 5000, "MESIN 1"), prod(0, 10, 5000, "MESIN 2")]
    d = compute_deliveries(events, batch_kg=8000)
    assert [x["delivery_no"] for x in d] == [1, "leftover"]
    assert d[0]["day"] == 8.0
    assert d[1]["batch_kg"] == 2000


def test_deliveries_handle_rate_changes_between_events():
    # A: 6000 kg days 0-6 (1000/day); B: 6000 kg days 0-12 (500/day)
    # combined 1500/day until day 6 -> 8000 kg at day 5.33; then 500/day, total 12000 -> no 2nd truck
    events = [prod(0, 6, 6000, "MESIN 1"), prod(0, 12, 6000, "MESIN 2")]
    d = compute_deliveries(events, batch_kg=8000)
    assert [x["delivery_no"] for x in d] == [1, "leftover"]
    assert d[0]["day"] == 5.33
    assert d[1] == {"delivery_no": "leftover", "day": 12, "cumulative_kg": 12000, "batch_kg": 4000}


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests passed")
