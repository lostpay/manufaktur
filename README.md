# manufaktur

Production queue scheduler for a 7-machine steel pipe line: turns the open
PO backlog into a per-machine, day-by-day sequence that minimizes mold and
thickness changeovers, predicts when each 8 t delivery batch is ready, and
renders it all as a Gantt chart.

- `scripts/build_csv.py` — flattens the source workbook to CSV
- `scripts/scheduler.py` — the scheduling algorithm and delivery timeline; one `SIZES` table holds each size's machine and rate
- `scripts/gantt.py` — renders the schedule as a self-contained HTML Gantt chart
- `output/` — generated files, one set per year and per ordering mode:
  `<year>_<mode>_schedule.csv`, `<year>_<mode>_deliveries.csv`, `<year>_<mode>_gantt.html`

## Ordering modes

Jobs are always grouped by size, then thickness, to avoid changeovers. The
mode only decides the order *within* that structure:

- `shortest` — shortest job first, so small orders clear early
- `fill` — heaviest kg/day first, so each 8 t delivery batch is reached sooner

## Run

Needs Python 3.13+ and `openpyxl`. Place the source workbook in the project
root (it's git-ignored), then:

```
python scripts/run.py                  # both modes
python scripts/run.py --mode shortest  # or --mode fill
```

Tests: `python scripts/test_scheduler.py && python scripts/test_gantt.py`
