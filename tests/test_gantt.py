"""Run: python tests/test_gantt.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.gantt import render_gantt_html

EVENTS = [
    {"mesin": "MESIN 1", "order_id": 1, "po_no": "PO A", "size": '3/4"', "thickness": "0.8",
     "qty": "10", "kg": "22", "start_day": "0", "end_day": "1", "event_type": "production"},
    {"mesin": "MESIN 1", "order_id": "", "po_no": "", "size": '1"', "thickness": "",
     "qty": "", "kg": "", "start_day": "1", "end_day": "1.5", "event_type": "mold_change"},
]
DELIVERIES = [{"delivery_no": 1, "day": 0.8, "cumulative_kg": 8000, "batch_kg": 8000},
              {"delivery_no": "leftover", "day": 1, "cumulative_kg": 9000, "batch_kg": 1000}]


def test_bars_lines_and_labels_english():
    html = render_gantt_html(EVENTS, "Test", DELIVERIES, "en")
    assert html.count('class="event-bar"') == 2 and html.count('class="delivery"') == 1
    assert "D1 · day 0.8" in html and "MESIN 7" in html and "working days from start" in html


def test_labels_indonesian_and_custom_machines():
    html = render_gantt_html(EVENTS, "Tes", DELIVERIES, "id", machines=["MESIN 1", "MESIN 9"])
    assert "hari kerja sejak mulai" in html and "Ganti mold" in html and "MESIN 9" in html and "MESIN 7" not in html


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"OK: {name}")
