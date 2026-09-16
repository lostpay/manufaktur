"""UI strings. `en` is the fallback for any key missing in another language."""
LANGS = ("en", "id")

STRINGS = {
    "en": {
        "app": "Manufaktur", "nav_dashboard": "Dashboard", "nav_upload": "Upload", "nav_settings": "Settings",
        "nav_machines": "Machines", "lang_other": "Bahasa Indonesia",
        "based_on": "Based on {filename} / {sheet} (snapshot {date}), imported {when}. {kg} kg logged since.",
        "no_data": "No orders yet — upload a workbook to start.",
        "upload_title": "Upload workbook", "upload_file": "Workbook (.xlsx)", "upload_btn": "Read workbook",
        "preview_title": "Preview", "sheet": "Sheet", "rows": "rows", "snapshot": "snapshot",
        "import_this": "Import", "counts": "{new} new · {updated} updated · {closed} closed",
        "unknown_sizes": "Unknown sizes — assign or ignore before importing",
        "size": "Size", "machines_csv": "Machines (comma separated)", "rate": "Pieces / day", "ignore": "Ignore",
        "confirm_btn": "Confirm import", "no_sheets": "No sheet in this file looks like a PO table.",
        "mode": "Order", "mode_shortest": "shortest job first", "mode_fill": "fill 8 t batches first",
        "deliveries": "Deliveries", "delivery": "Delivery", "day": "Day", "cumulative_kg": "Cumulative kg",
        "leftover": "left over (below one batch)", "machine_total": "{days} d total", "idle": "idle — no queued work",
        "queue_title": "{machine} — work order", "seq": "#", "po": "PO", "thickness": "Thickness",
        "remaining_pcs": "Remaining pcs", "remaining_kg": "Remaining kg", "start": "Start", "end": "End",
        "mold_change": "Mold change", "reconfig": "Thickness reconfig", "production": "Production",
        "done": "Done", "partial": "Log kg", "print": "Print",
        "settings_title": "Settings", "mold_change_days": "Mold change (days)", "reconfig_hours": "Thickness reconfig (hours)",
        "workday_hours": "Working day (hours)", "batch_kg": "Delivery batch (kg)", "machine_order": "Machines (display order, comma separated)",
        "sizes_table": "Sizes", "ignored_sizes": "Ignored sizes (comma separated)", "save": "Save",
        "settings_saved": "Settings saved.", "error": "Error",
        "gantt_caption": "All machines start at day 0. A truck leaves each time {tons} t of finished product is ready, from any mix of machines and POs.",
        "gantt_delivery_legend": "Delivery ({tons} t reached)", "gantt_axis": "working days from start",
    },
    "id": {
        "app": "Manufaktur", "nav_dashboard": "Dasbor", "nav_upload": "Unggah", "nav_settings": "Pengaturan",
        "nav_machines": "Mesin", "lang_other": "English",
        "based_on": "Berdasarkan {filename} / {sheet} (per tanggal {date}), diimpor {when}. {kg} kg dicatat sejak itu.",
        "no_data": "Belum ada PO — unggah workbook untuk mulai.",
        "upload_title": "Unggah workbook", "upload_file": "Workbook (.xlsx)", "upload_btn": "Baca workbook",
        "preview_title": "Pratinjau", "sheet": "Sheet", "rows": "baris", "snapshot": "per tanggal",
        "import_this": "Impor", "counts": "{new} baru · {updated} diperbarui · {closed} ditutup",
        "unknown_sizes": "Ukuran belum dikenal — tentukan mesin atau abaikan sebelum impor",
        "size": "Ukuran", "machines_csv": "Mesin (pisahkan dengan koma)", "rate": "Batang / hari", "ignore": "Abaikan",
        "confirm_btn": "Konfirmasi impor", "no_sheets": "Tidak ada sheet yang berbentuk tabel PO.",
        "mode": "Urutan", "mode_shortest": "pekerjaan tersingkat dulu", "mode_fill": "isi batch 8 ton dulu",
        "deliveries": "Pengiriman", "delivery": "Pengiriman", "day": "Hari", "cumulative_kg": "Kumulatif kg",
        "leftover": "sisa (di bawah satu batch)", "machine_total": "total {days} hari", "idle": "menganggur — tidak ada antrean",
        "queue_title": "{machine} — perintah kerja", "seq": "#", "po": "PO", "thickness": "Tebal",
        "remaining_pcs": "Sisa batang", "remaining_kg": "Sisa kg", "start": "Mulai", "end": "Selesai",
        "mold_change": "Ganti mold", "reconfig": "Setel tebal", "production": "Produksi",
        "done": "Selesai", "partial": "Catat kg", "print": "Cetak",
        "settings_title": "Pengaturan", "mold_change_days": "Ganti mold (hari)", "reconfig_hours": "Setel tebal (jam)",
        "workday_hours": "Jam kerja per hari", "batch_kg": "Batch pengiriman (kg)", "machine_order": "Mesin (urutan tampil, pisahkan dengan koma)",
        "sizes_table": "Ukuran", "ignored_sizes": "Ukuran diabaikan (pisahkan dengan koma)", "save": "Simpan",
        "settings_saved": "Pengaturan tersimpan.", "error": "Kesalahan",
        "gantt_caption": "Semua mesin mulai di hari 0. Truk berangkat setiap {tons} ton produk jadi siap, dari mesin dan PO mana pun.",
        "gantt_delivery_legend": "Pengiriman ({tons} t tercapai)", "gantt_axis": "hari kerja sejak mulai",
    },
}


def t(lang, key, **kw):
    text = STRINGS.get(lang, {}).get(key) or STRINGS["en"][key]
    return text.format(**kw) if kw else text
