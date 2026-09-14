"""End-to-end: rebuild CSVs from the raw workbook, compute schedules,
render Gantt charts.

Run (from the manufaktur project root): python scripts/run.py
"""
import build_csv
import scheduler
import gantt

if __name__ == "__main__":
    build_csv.main()
    scheduler.main()
    gantt.main()
