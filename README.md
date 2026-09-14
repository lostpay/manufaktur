# manufaktur

Production queue scheduler for a 7-machine steel pipe line: turns the open
PO backlog into a per-machine, day-by-day sequence that minimizes mold and
thickness changeovers, and renders it as a Gantt chart.

- `scripts/build_csv.py` — flattens the source workbook to CSV
- `scripts/scheduler.py` — the scheduling algorithm; one `SIZES` table holds each size's machine and rate
- `scripts/gantt.py` — renders the schedule as a self-contained HTML Gantt chart
- `output/` — generated schedules (CSV) and charts (HTML), one pair per year

## Run

Needs Python 3.13+ and `openpyxl`. Place the source workbook in the project
root (it's git-ignored), then:

```
python scripts/run.py
```

Tests: `python scripts/test_scheduler.py && python scripts/test_gantt.py`
