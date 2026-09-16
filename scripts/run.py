"""Offline CLI: read the workbook, schedule every matching sheet in both
modes, write CSVs + Gantt charts into output/. Same engine as the web app.

Run (from the project root): python scripts/run.py [workbook.xlsx]
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import ingest
from app.engine import DEFAULT_SETTINGS, MODES, make_job, schedule, deliveries
from app.gantt import render_gantt_html

EVENT_FIELDS = ["mesin", "po_no", "size", "thickness", "qty", "kg", "start_day", "end_day", "event_type"]
DELIVERY_FIELDS = ["delivery_no", "day", "cumulative_kg", "batch_kg"]


def write_csv(rows, fields, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows)


def main(path="UPDATE SISA  PO PIPA TISCO TAHUN 2025.xlsx"):
    os.makedirs("output", exist_ok=True)
    settings = DEFAULT_SETTINGS
    wb = ingest.load(path)
    for s in ingest.scan_workbook(wb):
        rows = ingest.extract_sheet(wb[s["sheet"]], s["header_row"])
        orders = [{"order_id": i, "remaining_kg": r["berat_total"], **r} for i, r in enumerate(rows)]
        jobs = [j for j in (make_job(o, settings) for o in orders) if j]
        for mode in MODES:
            events = schedule(jobs, settings, mode)
            delivs = deliveries(events, settings["batch_kg"])
            stem = f"output/{s['sheet']}_{mode}"
            write_csv(events, EVENT_FIELDS, f"{stem}_schedule.csv")
            write_csv(delivs, DELIVERY_FIELDS, f"{stem}_deliveries.csv")
            with open(f"{stem}_gantt.html", "w", encoding="utf-8") as f:
                f.write(render_gantt_html(events, f"Manufaktur Queue {s['sheet']} — {mode}", delivs, "en",
                                          settings["batch_kg"], settings["machines"]))
            trucks = [d for d in delivs if d["delivery_no"] != "leftover"]
            print(f"{s['sheet']} {mode:8s}: {len(events)} events, {len(trucks)} deliveries -> {stem}_*")


if __name__ == "__main__":
    main(*sys.argv[1:])
