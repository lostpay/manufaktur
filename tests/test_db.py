"""Run: python tests/test_db.py"""
import copy
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import db
from app.engine import DEFAULT_SETTINGS


def row(po_no, size, kg, thickness=0.8, bpp=1.0):
    return {"po_no": po_no, "size": size, "thickness": thickness, "berat_per_pcs": bpp,
            "berat_total": kg, "mesin": "", "mesin_size": ""}


def fresh():
    return db.connect(":memory:")


def test_settings_roundtrip_with_defaults():
    c = fresh()
    assert db.get_settings(c) == DEFAULT_SETTINGS
    s = copy.deepcopy(DEFAULT_SETTINGS); s["batch_kg"] = 5000
    db.save_settings(c, s)
    assert db.get_settings(c)["batch_kg"] == 5000


def test_reconcile_counts_new_updated_closed_and_resets_progress():
    c = fresh()
    u1 = db.record_upload(c, "a.xlsx", "S", "2026-09-01")
    assert db.reconcile(c, u1, "S", [row("PO 1", '1/2"', 100), row("PO 2", '3/4"', 50)]) == {"new": 2, "updated": 0, "closed": 0}
    o = {x["po_no"]: x for x in db.open_orders(c)}
    db.log_production(c, o["PO 1"]["order_id"], 40, "MESIN 2")
    assert {x["po_no"]: x["remaining_kg"] for x in db.open_orders(c)} == {"PO 1": 60, "PO 2": 50}
    assert db.kg_logged_since_upload(c) == 40

    u2 = db.record_upload(c, "b.xlsx", "S", "2026-09-08")
    assert db.reconcile(c, u2, "S", [row("PO 1", '1/2"', 90), row("PO 3", '1"', 0)]) == {"new": 1, "updated": 1, "closed": 1}
    orders = {x["po_no"]: x for x in db.open_orders(c)}
    assert orders["PO 1"]["remaining_kg"] == 90                     # workbook wins, progress reset
    assert "PO 2" not in orders                                     # closed
    assert orders["PO 3"]["remaining_kg"] == 0                      # open with nothing remaining
    assert db.kg_logged_since_upload(c) == 0
    assert db.latest_upload(c)["sheet"] == "S" and db.latest_upload(c)["n_closed"] == 1


def test_same_po_on_two_sheets_are_different_orders():
    c = fresh()
    db.reconcile(c, db.record_upload(c, "a", "2025", ""), "2025", [row("PO 1", '1/2"', 10)])
    db.reconcile(c, db.record_upload(c, "a", "2026", ""), "2026", [row("PO 1", '1/2"', 20)])
    assert sorted(x["remaining_kg"] for x in db.open_orders(c)) == [10, 20]


def test_unknown_sizes_excludes_known_and_ignored():
    s = copy.deepcopy(DEFAULT_SETTINGS); s["ignored_sizes"] = ["20X20"]
    rows = [row("a", '1/2"', 1), row("b", "20X20", 1), row("c", "25X25", 1), row("d", "25X25", 1)]
    assert db.unknown_sizes(rows, s) == ["25X25"]


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t(); print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests passed")
