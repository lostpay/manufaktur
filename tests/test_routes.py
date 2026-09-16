"""Run: python tests/test_routes.py  (uses a temp DB and upload dir)"""
import io, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(tmp, "t.db")
os.environ["UPLOAD_DIR"] = os.path.join(tmp, "up")

from fastapi.testclient import TestClient
from app.main import app
from tests.test_ingest import synthetic_workbook

client = TestClient(app)


def workbook_bytes():
    buf = io.BytesIO(); synthetic_workbook().save(buf); return buf.getvalue()


def test_empty_db_redirects_to_upload():
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/upload"


def test_upload_preview_confirm_dashboard_machine_log_settings():
    r = client.post("/upload", files={"file": ("sisa.xlsx", workbook_bytes())})
    assert r.status_code == 200 and "Sisa PO Sept 2026" in r.text and "2027" in r.text
    assert "20X20" in r.text                                    # unknown size surfaced
    upload_id = r.text.split('action="/upload/')[1].split("/")[0]

    r = client.post(f"/upload/{upload_id}/confirm", data={
        "sheets": ["Sisa PO Sept 2026", "2027"], "unk_size_0": "20X20", "unk_action_0": "ignore"},
        follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"

    r = client.get("/")
    assert r.status_code == 200 and "MESIN 2" in r.text and "sisa.xlsx" in r.text
    assert 'class="event-bar"' in r.text

    r = client.get("/machine/MESIN 2")
    assert r.status_code == 200 and "PO 001" in r.text and "PO 003" in r.text
    order_id = r.text.split('name="order_id" value="')[1].split('"')[0]

    r = client.post("/machine/MESIN 2/log", data={"order_id": order_id, "kg": "40"}, follow_redirects=False)
    assert r.status_code == 303
    assert "40" in client.get("/").text                        # "40 kg logged since"

    r = client.get("/settings?lang=id")
    assert "Pengaturan" in r.text
    form = {"mold_change_days": "0.5", "reconfig_hours": "1", "workday_hours": "8", "batch_kg": "8000",
            "machines": "MESIN 1, MESIN 2, MESIN 3, MESIN 4, MESIN 5, MESIN 6, MESIN 7",
            "ignored_sizes": "20X20", "size_0": '1/2"', "machines_0": "MESIN 2", "rate_0": "65"}
    r = client.post("/settings", data=form, follow_redirects=False)
    assert r.status_code == 303
    assert '1/2&#34;' in client.get("/machine/MESIN 2").text    # still scheduled, now at 65/day (Jinja escapes the inch mark)

    r = client.get("/lang/id", headers={"referer": "/"}, follow_redirects=False)
    assert r.status_code == 303 and "lang=id" in r.headers["set-cookie"]
    assert "Dasbor" in client.get("/").text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"OK: {name}")
