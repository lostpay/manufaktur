"""SQLite storage: settings, uploads, orders, production log. Schedules are
never stored — see the spec's reconciliation rule for what is."""
import copy
import datetime
import json
import os
import sqlite3

from app.engine import DEFAULT_SETTINGS

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS uploads(id INTEGER PRIMARY KEY, filename TEXT, sheet TEXT, snapshot_date TEXT,
    uploaded_at TEXT, n_new INTEGER DEFAULT 0, n_updated INTEGER DEFAULT 0, n_closed INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, sheet TEXT, po_no TEXT, size TEXT, thickness REAL,
    berat_per_pcs REAL, kg_workbook REAL, kg_logged REAL DEFAULT 0, status TEXT DEFAULT 'open',
    upload_id INTEGER, UNIQUE(sheet, po_no, size, thickness));
CREATE TABLE IF NOT EXISTS production_log(id INTEGER PRIMARY KEY, order_id INTEGER, kg REAL, machine TEXT,
    note TEXT, logged_at TEXT);
"""


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def connect(path=None):
    path = path or os.environ.get("DB_PATH", "data/manufaktur.db")
    if path != ":memory:":
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def get_settings(conn):
    row = conn.execute("SELECT value FROM settings WHERE key='settings'").fetchone()
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    if row:
        settings.update(json.loads(row["value"]))
    return settings


def save_settings(conn, settings):
    conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES('settings', ?)", (json.dumps(settings),))
    conn.commit()


def record_upload(conn, filename, sheet, snapshot_date):
    cur = conn.execute("INSERT INTO uploads(filename, sheet, snapshot_date, uploaded_at) VALUES(?,?,?,?)",
                       (filename, sheet, snapshot_date, now()))
    conn.commit()
    return cur.lastrowid


def unknown_sizes(rows, settings):
    known = set(settings["sizes"]) | set(settings["ignored_sizes"])
    return sorted({r["size"] for r in rows} - known)


def reconcile(conn, upload_id, sheet, rows):
    """Workbook wins: matching orders reset to the workbook figure with
    progress zeroed, new rows inserted, rows absent from this upload closed."""
    seen, counts = set(), {"new": 0, "updated": 0, "closed": 0}
    for r in rows:
        key = (sheet, r["po_no"], r["size"], round(float(r["thickness"] or 0), 3))
        seen.add(key)
        existing = conn.execute("SELECT id FROM orders WHERE sheet=? AND po_no=? AND size=? AND thickness=?", key).fetchone()
        if existing:
            conn.execute("UPDATE orders SET berat_per_pcs=?, kg_workbook=?, kg_logged=0, status='open', upload_id=? WHERE id=?",
                         (r["berat_per_pcs"], r["berat_total"], upload_id, existing["id"]))
            counts["updated"] += 1
        else:
            conn.execute("INSERT INTO orders(sheet, po_no, size, thickness, berat_per_pcs, kg_workbook, upload_id) VALUES(?,?,?,?,?,?,?)",
                         (*key, r["berat_per_pcs"], r["berat_total"], upload_id))
            counts["new"] += 1
    for o in conn.execute("SELECT id, po_no, size, thickness FROM orders WHERE sheet=? AND status='open'", (sheet,)).fetchall():
        if (sheet, o["po_no"], o["size"], round(o["thickness"], 3)) not in seen:
            conn.execute("UPDATE orders SET status='closed' WHERE id=?", (o["id"],))
            counts["closed"] += 1
    conn.execute("UPDATE uploads SET n_new=?, n_updated=?, n_closed=? WHERE id=?",
                 (counts["new"], counts["updated"], counts["closed"], upload_id))
    conn.commit()
    return counts


def log_production(conn, order_id, kg, machine, note=""):
    conn.execute("INSERT INTO production_log(order_id, kg, machine, note, logged_at) VALUES(?,?,?,?,?)",
                 (order_id, kg, machine, note, now()))
    conn.execute("UPDATE orders SET kg_logged = kg_logged + ? WHERE id=?", (kg, order_id))
    conn.commit()


def open_orders(conn):
    return [{"order_id": o["id"], "sheet": o["sheet"], "po_no": o["po_no"], "size": o["size"],
             "thickness": o["thickness"], "berat_per_pcs": o["berat_per_pcs"],
             "remaining_kg": max(o["kg_workbook"] - o["kg_logged"], 0)}
            for o in conn.execute("SELECT * FROM orders WHERE status='open' ORDER BY sheet, po_no, size").fetchall()]


def latest_upload(conn):
    return conn.execute("SELECT * FROM uploads ORDER BY id DESC LIMIT 1").fetchone()


def kg_logged_since_upload(conn):
    return conn.execute("SELECT COALESCE(SUM(kg_logged), 0) FROM orders WHERE status='open'").fetchone()[0]
