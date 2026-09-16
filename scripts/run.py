"""End-to-end: rebuild CSVs from the raw workbook, compute schedules and
delivery timelines, render Gantt charts.

Run (from the manufaktur project root):
    python scripts/run.py                 # both ordering modes
    python scripts/run.py --mode shortest # or: --mode fill
"""
import build_csv
import scheduler
import gantt

if __name__ == "__main__":
    build_csv.main()
    scheduler.main()
    gantt.main()
