"""Plain-assert test for gantt.py.

Run: python scripts/test_gantt.py
"""
from gantt import render_gantt_html


def test_render_gantt_html_contains_one_rect_per_event_and_delivery_lines():
    events = [
        {"mesin": "MESIN 1", "po_no": "PO A", "size": '3/4"', "thickness": "0.8",
         "qty": "10", "kg": "22", "start_day": "0", "end_day": "1", "event_type": "production"},
        {"mesin": "MESIN 1", "po_no": "", "size": '1"', "thickness": "",
         "qty": "", "kg": "", "start_day": "1", "end_day": "1.5", "event_type": "mold_change"},
    ]
    deliveries = [
        {"delivery_no": "1", "day": "0.8", "cumulative_kg": "8000", "batch_kg": "8000"},
        {"delivery_no": "leftover", "day": "1", "cumulative_kg": "9000", "batch_kg": "1000"},
    ]
    html = render_gantt_html(events, "Test", deliveries)
    assert html.count('class="event-bar"') == 2  # one rect per event, distinct from legend/stripe rects
    assert html.count('class="delivery"') == 1   # one line per full batch; the leftover row draws nothing
    assert "D1 · day 0.8" in html
    assert "MESIN 1" in html
    assert "MESIN 2" in html  # all 7 machine rows are always drawn, even with no events
    assert "Production" in html and "Mold change" in html and "Reconfig" in html  # legend present
    assert "working days" in html  # axis caption present


if __name__ == "__main__":
    test_render_gantt_html_contains_one_rect_per_event_and_delivery_lines()
    print("OK: test_render_gantt_html_contains_one_rect_per_event_and_delivery_lines")
