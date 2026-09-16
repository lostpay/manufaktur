"""FastAPI app: upload → preview → confirm; dashboard; machine work orders
with progress logging; settings; language toggle."""
import os
import uuid

from fastapi import FastAPI, HTTPException, Request, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import db, ingest
from app.engine import MODES, make_job, schedule, deliveries as compute_deliveries
from app.gantt import render_gantt_html
from app.i18n import LANGS, t

app = FastAPI(title="Manufaktur")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "data/uploads")
conn = db.connect()


def lang_of(request):
    q = request.query_params.get("lang")
    return q if q in LANGS else (request.cookies.get("lang") if request.cookies.get("lang") in LANGS else "en")


def render(request, template, **ctx):
    lang = lang_of(request)
    settings = db.get_settings(conn)
    up = db.latest_upload(conn)
    based_on = t(lang, "based_on", filename=up["filename"], sheet=up["sheet"], date=up["snapshot_date"] or "—",
                 when=up["uploaded_at"], kg=f"{db.kg_logged_since_upload(conn):.0f}") if up else ""
    return templates.TemplateResponse(request, template, {
        "t": lambda key, **kw: t(lang, key, **kw), "lang": lang, "settings": settings,
        "based_on": based_on, "machines": settings["machines"], **ctx})


def current_schedule(mode):
    settings = db.get_settings(conn)
    jobs = [j for j in (make_job(o, settings) for o in db.open_orders(conn)) if j]
    events = schedule(jobs, settings, mode)
    return settings, events, compute_deliveries(events, settings["batch_kg"])


@app.get("/lang/{code}")
def set_lang(code: str, request: Request):
    resp = RedirectResponse(request.headers.get("referer", "/"), status_code=303)
    if code in LANGS:
        resp.set_cookie("lang", code, max_age=10**8)
    return resp


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, mode: str = "shortest"):
    if not db.open_orders(conn):
        return RedirectResponse("/upload", status_code=303)
    mode = mode if mode in MODES else "shortest"
    settings, events, delivs = current_schedule(mode)
    lang = lang_of(request)
    gantt = render_gantt_html(events, f'{t(lang, "app")} — {t(lang, "mode_" + mode)}', delivs, lang,
                              settings["batch_kg"], settings["machines"])
    totals = {m: max((float(e["end_day"]) for e in events if e["mesin"] == m), default=0) for m in settings["machines"]}
    return render(request, "dashboard.html", mode=mode, modes=list(MODES), gantt=gantt, deliveries=delivs, totals=totals)


@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request):
    return render(request, "upload.html")


@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    upload_id = uuid.uuid4().hex
    path = os.path.join(UPLOAD_DIR, f"{upload_id}.xlsx")
    with open(path, "wb") as f:
        f.write(await file.read())
    with open(os.path.join(UPLOAD_DIR, f"{upload_id}.name"), "w", encoding="utf-8") as f:
        f.write(file.filename or "workbook.xlsx")
    wb = ingest.load(path)
    settings = db.get_settings(conn)
    sheets = ingest.scan_workbook(wb)
    unknown = set()
    for s in sheets:
        s["unknown"] = db.unknown_sizes(ingest.extract_sheet(wb[s["sheet"]], s["header_row"]), settings)
        unknown |= set(s["unknown"])
    return render(request, "preview.html", upload_id=upload_id, sheets=sheets, unknown=sorted(unknown))


@app.post("/upload/{upload_id}/confirm")
async def confirm(upload_id: str, request: Request):
    form = await request.form()
    settings = db.get_settings(conn)
    i = 0
    while f"unk_size_{i}" in form:                       # resolve unknown sizes first
        size, action = form[f"unk_size_{i}"], form.get(f"unk_action_{i}", "ignore")
        if action == "assign":
            machines = [m.strip() for m in form.get(f"unk_machines_{i}", "").split(",") if m.strip()]
            rate = float(form.get(f"unk_rate_{i}") or 0)
            if not machines or rate <= 0 or any(m not in settings["machines"] for m in machines):
                raise HTTPException(400, f"{size}: machines {machines}, rate {rate}")
            settings["sizes"][size] = {"machines": machines, "rate": rate}
        elif size not in settings["ignored_sizes"]:
            settings["ignored_sizes"].append(size)
        i += 1
    db.save_settings(conn, settings)
    path = os.path.join(UPLOAD_DIR, f"{upload_id}.xlsx")
    filename = open(os.path.join(UPLOAD_DIR, f"{upload_id}.name"), encoding="utf-8").read()
    wb = ingest.load(path)
    for s in ingest.scan_workbook(wb):
        if s["sheet"] in form.getlist("sheets"):
            rows = ingest.extract_sheet(wb[s["sheet"]], s["header_row"])
            uid = db.record_upload(conn, filename, s["sheet"], s["snapshot_date"])
            db.reconcile(conn, uid, s["sheet"], rows)
    return RedirectResponse("/", status_code=303)


@app.get("/machine/{name}", response_class=HTMLResponse)
def machine(name: str, request: Request, mode: str = "shortest"):
    mode = mode if mode in MODES else "shortest"
    _, events, _ = current_schedule(mode)
    rows = [e for e in events if e["mesin"] == name]
    return render(request, "machine.html", name=name, mode=mode, rows=rows)


@app.post("/machine/{name}/log")
def log(name: str, order_id: int = Form(...), kg: float = Form(...), mode: str = Form("shortest")):
    db.log_production(conn, order_id, kg, name)
    return RedirectResponse(f"/machine/{name}?mode={mode}", status_code=303)


@app.get("/settings", response_class=HTMLResponse)
def settings_form(request: Request, saved: int = 0, error: str = ""):
    return render(request, "settings.html", saved=saved, error=error)


@app.post("/settings")
async def settings_save(request: Request):
    form = await request.form()
    s = db.get_settings(conn)
    try:
        for key in ("mold_change_days", "reconfig_hours", "workday_hours", "batch_kg"):
            s[key] = float(form[key])
        s["machines"] = [m.strip() for m in form["machines"].split(",") if m.strip()]
        s["ignored_sizes"] = [x.strip() for x in form.get("ignored_sizes", "").split(",") if x.strip()]
        sizes, i = {}, 0
        while f"size_{i}" in form:
            size = form[f"size_{i}"].strip()
            if size:
                machines = [m.strip() for m in form[f"machines_{i}"].split(",") if m.strip()]
                rate = float(form[f"rate_{i}"])
                if not machines or rate <= 0 or any(m not in s["machines"] for m in machines):
                    raise ValueError(f"{size}: machines {machines}, rate {rate}")
                sizes[size] = {"machines": machines, "rate": rate}
            i += 1
        s["sizes"] = sizes
    except (KeyError, ValueError) as e:
        return RedirectResponse(f"/settings?error={e}", status_code=303)
    db.save_settings(conn, s)
    return RedirectResponse("/settings?saved=1", status_code=303)
