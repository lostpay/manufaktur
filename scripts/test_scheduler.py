"""Plain-assert tests for scheduler.py.

Run: python scripts/test_scheduler.py
"""
from scheduler import (
    SIZES,
    resolve_machine_assignment,
    build_machine_schedule,
    compute_events,
)


def job(po_no, size, qty, thickness=0.8):
    return {"po_no": po_no, "size": size, "qty": qty, "thickness": thickness, "days": qty / SIZES[size][1]}


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


def test_build_machine_schedule_groups_and_sorts():
    jobs = [job("PO A", '1/2"', 30), job("PO B", '1/2"', 10), job("PO C", '5/8"', 5)]
    ordered = build_machine_schedule(jobs)
    # smaller total-days size group (5/8") goes before the larger (1/2")
    assert [j["po_no"] for j in ordered] == ["PO C", "PO B", "PO A"]


def test_compute_events_adds_mold_change_between_sizes():
    ordered = [job("PO A", '1/2"', 65), job("PO B", '5/8"', 65)]
    events = compute_events("MESIN 2", ordered)
    assert [e["event_type"] for e in events] == ["production", "mold_change", "production"]
    assert events[0]["end_day"] == 0.5     # 65 / 130 pcs/day
    assert events[1]["start_day"] == 0.5
    assert events[1]["end_day"] == 1.0     # +0.5 day mold change
    assert events[2]["start_day"] == 1.0


def test_compute_events_adds_reconfig_for_thickness_change_same_size():
    ordered = [job("PO A", '1/2"', 13, thickness=0.8), job("PO B", '1/2"', 13, thickness=1.0)]
    events = compute_events("MESIN 2", ordered)
    assert [e["event_type"] for e in events] == ["production", "reconfig", "production"]
    assert events[1]["end_day"] - events[1]["start_day"] == 0.125   # 1hr / 8hr day


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests passed")
