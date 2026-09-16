# manufaktur

Production queue scheduler for a 7-machine steel pipe line: turns the open
PO backlog into a per-machine, day-by-day sequence that minimizes mold and
thickness changeovers, predicts when each 8 t delivery batch is ready, and
renders it all as a Gantt chart. Runs as a small web app or as an offline CLI.

- `app/engine.py` — the scheduling algorithm and delivery timeline, pure functions over a settings dict
- `app/ingest.py` — reads any version of the PO workbook (sheet names and column positions are detected)
- `app/db.py` — SQLite: settings, uploads, orders, production log; workbook-wins reconciliation
- `app/gantt.py` — renders a schedule as a self-contained HTML Gantt chart
- `app/i18n.py` — UI strings, English and Bahasa Indonesia
- `app/main.py` + `app/templates/` — the FastAPI web app
- `scripts/run.py` — offline CLI on the same modules
- `output/` — generated files, one set per sheet and per ordering mode:
  `<sheet>_<mode>_schedule.csv`, `<sheet>_<mode>_deliveries.csv`, `<sheet>_<mode>_gantt.html`

## Ordering modes

Jobs are always grouped by size, then thickness, to avoid changeovers. The
mode only decides the order *within* that structure:

- `shortest` — shortest job first, so small orders clear early
- `fill` — heaviest kg/day first, so each 8 t delivery batch is reached sooner

## Run the web app

    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8080      # http://localhost:8080

Upload the PO workbook on the Upload page — any sheet that has the
TICKNES / SIZE / BERAT/PCS / NO PO header row is offered for import.
Between uploads, mark work done on each machine's page; the plan re-flows
from what's left. Factory settings (rates, changeover times, batch size,
which machine molds which size) are under Settings. Language toggle in the
header (English / Bahasa Indonesia).

Hosted: `fly deploy` (see `fly.toml`; SQLite and uploads live on the `/data` volume).

## Offline CLI

    python scripts/run.py [workbook.xlsx]     # writes output/<sheet>_<mode>_{schedule,deliveries,gantt}.*

## Tests

    for f in tests/test_*.py; do python $f; done
