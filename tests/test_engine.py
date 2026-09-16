"""Run: python tests/test_engine.py"""
import copy
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.engine import (DEFAULT_SETTINGS, make_job, assign_machines, order_machine,
                        machine_events, schedule, deliveries)

S = DEFAULT_SETTINGS


def order(po_no, size, remaining_kg, thickness=0.8, berat_per_pcs=1.0, order_id=None):
    return {"order_id": order_id or po_no, "po_no": po_no, "size": size, "thickness": thickness,
            "berat_per_pcs": berat_per_pcs, "remaining_kg": remaining_kg}


def job(po_no, size, qty, thickness=0.8, kg_per_pc=1.0):
    return make_job(order(po_no, size, qty * kg_per_pc, thickness, kg_per_pc), S)


def prod(start, end, kg, mesin="MESIN 1"):
    return {"mesin": mesin, "start_day": start, "end_day": end, "kg": kg, "event_type": "production"}


def test_make_job_derives_qty_and_days_and_filters():
    j = make_job(order("PO 1", '1/2"', 130, berat_per_pcs=1.0), S)
    assert (j["qty"], j["days"], j["kg"]) == (130, 1.0, 130)
    assert make_job(order("PO 2", '20X20', 100), S) is None          # not in sizes
    assert make_job(order("PO 3", '1/2"', 0), S) is None             # nothing remaining
    s = copy.deepcopy(S); s["ignored_sizes"] = ['1/2"']
    assert make_job(order("PO 4", '1/2"', 10), s) is None            # explicitly ignored


def test_fixed_sizes_go_to_their_machine():
    assert assign_machines([job("PO 1", '3/4"', 10)], S)[0]["mesin"] == "MESIN 1"


def test_small_shared_backlog_stays_off_a_busy_machine():
    jobs = [job("PO 1", '2"', 50), job("PO 2", '1"', 10)]
    by_po = {j["po_no"]: j["mesin"] for j in assign_machines(jobs, S)}
    assert by_po == {"PO 1": "MESIN 4", "PO 2": "MESIN 6"}


def test_large_shared_backlog_is_split_despite_other_work():
    jobs = [job("PO 1", '2"', 50)] + [job(f"PO {i}", '1"', 1000) for i in "ABC"]
    by_po = {j["po_no"]: j["mesin"] for j in assign_machines(jobs, S)}
    assert {by_po["PO A"], by_po["PO B"], by_po["PO C"]} == {"MESIN 4", "MESIN 6"}


def test_shared_size_across_three_machines():
    s = copy.deepcopy(S)
    s["sizes"]['1"']["machines"] = ["MESIN 4", "MESIN 6", "MESIN 7"]
    jobs = [job(f"PO {i}", '1"', 1000) for i in "ABC"]
    assert {j["mesin"] for j in assign_machines(jobs, s)} == {"MESIN 4", "MESIN 6", "MESIN 7"}


def test_shortest_mode_orders_by_days():
    jobs = [job("A", '1/2"', 30), job("B", '1/2"', 10), job("C", '5/8"', 5)]
    assert [j["po_no"] for j in order_machine(jobs, "shortest")] == ["C", "B", "A"]


def test_fill_mode_orders_by_kg_per_day():
    jobs = [job("A", '1/2"', 30, kg_per_pc=1.0), job("B", '1/2"', 10, kg_per_pc=1.5), job("C", '5/8"', 5, kg_per_pc=1.8)]
    ordered = order_machine(jobs, "fill")
    assert [j["po_no"] for j in ordered] == ["C", "B", "A"]
    sizes = [j["size"] for j in ordered]
    assert sum(a != b for a, b in zip(sizes, sizes[1:])) == 1


def test_events_charge_mold_change_and_reconfig():
    ev = machine_events("MESIN 2", [job("A", '1/2"', 65), job("B", '5/8"', 65, thickness=1.0)], S)
    assert [e["event_type"] for e in ev] == ["production", "mold_change", "reconfig", "production"]
    assert ev[0]["end_day"] == 0.5 and ev[1]["end_day"] == 1.0 and ev[2]["end_day"] == 1.125
    assert ev[3]["start_day"] == 1.125 and ev[3]["order_id"] == "B"


def test_schedule_runs_every_machine():
    ev = schedule([job("A", '3/4"', 10), job("B", '1/2"', 10), job("C", '1"', 10)], S, "shortest")
    assert {e["mesin"] for e in ev} == {"MESIN 1", "MESIN 2", "MESIN 4"}


def test_deliveries_cross_batches_on_shared_clock():
    d = deliveries([prod(0, 6, 6000), prod(0, 12, 6000, "MESIN 2")], 8000)
    assert [x["delivery_no"] for x in d] == [1, "leftover"]
    assert d[0]["day"] == 5.33
    assert d[1] == {"delivery_no": "leftover", "day": 12, "cumulative_kg": 12000, "batch_kg": 4000}


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t(); print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests passed")
