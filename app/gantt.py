"""Self-contained HTML Gantt chart from schedule events.

Machines as rows, days on the x-axis (all machines start at day 0 on one
shared clock), one bar per event, a dashed line at each delivery. No
charting library -- plain inline SVG. Labels come from app.i18n.
"""
from app.i18n import t

COLORS = {
    "production": "#4C78A8",
    "mold_change": "#E45756",
    "reconfig": "#F2B701",
}
SHORT_LABEL = {"mold_change": "MC", "reconfig": "RC"}
DELIVERY_COLOR = "#2CA02C"

ROW_HEIGHT = 44
DAY_WIDTH = 26
LEFT_MARGIN = 100
RIGHT_MARGIN = 60
TOP_MARGIN = 80          # room for title, caption, legend and delivery labels above the grid
BOTTOM_MARGIN = 28       # room for day-axis labels below the chart grid


def _tick_interval(max_day):
    if max_day <= 15:
        return 1
    if max_day <= 40:
        return 5
    return 10


def _fitted_text(text, width_px, font_px=10, char_px=6, pad_px=8):
    """Return text truncated to fit width_px, or '' if there's no room at all."""
    max_chars = int((width_px - pad_px) / char_px)
    if max_chars < 2:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _bar_tooltip(e):
    if e["event_type"] == "production":
        return (f'{e["po_no"]} — {e["size"]} @ {e["thickness"]}mm — '
                f'{float(e["qty"]):.0f} pcs / {float(e["kg"]):.0f} kg — day {float(e["start_day"]):.2f}'
                f'–{float(e["end_day"]):.2f}')
    kind = "Mold change" if e["event_type"] == "mold_change" else "Reconfig"
    return (f'{kind} → next size {e["size"]} — '
            f'day {float(e["start_day"]):.2f}–{float(e["end_day"]):.2f}')


def render_gantt_html(events, title, deliveries=(), lang="en", batch_kg=8000, machines=None):
    machines = machines or [f"MESIN {i}" for i in range(1, 8)]
    tons = batch_kg // 1000
    labels = {"production": t(lang, "production"),
              "mold_change": f'{t(lang, "mold_change")} (0.5 d)',
              "reconfig": f'{t(lang, "reconfig")} (1 h)'}
    max_day = max((float(e["end_day"]) for e in events), default=1)
    n_rows = len(machines)
    grid_width = int(max_day + 1) * DAY_WIDTH
    width = LEFT_MARGIN + grid_width + RIGHT_MARGIN
    grid_bottom = TOP_MARGIN + n_rows * ROW_HEIGHT
    height = grid_bottom + BOTTOM_MARGIN

    svg_parts = []

    # --- title + legend, drawn above the chart grid ---
    svg_parts.append(f'<text x="{LEFT_MARGIN}" y="20" font-size="16" font-weight="600">{title}</text>')
    svg_parts.append(
        f'<text x="{LEFT_MARGIN}" y="36" font-size="11" fill="#666">'
        f'{t(lang, "gantt_caption", tons=tons)}</text>'
    )
    legend_x = LEFT_MARGIN
    for event_type, color in COLORS.items():
        svg_parts.append(f'<rect x="{legend_x}" y="46" width="12" height="12" fill="{color}" rx="2"/>')
        label = labels[event_type]
        svg_parts.append(f'<text x="{legend_x + 16}" y="55.5" font-size="11">{label}</text>')
        legend_x += 20 + len(label) * 6 + 18
    svg_parts.append(
        f'<line x1="{legend_x}" y1="46" x2="{legend_x}" y2="58" stroke="{DELIVERY_COLOR}" '
        f'stroke-width="2" stroke-dasharray="4,3"/>'
    )
    svg_parts.append(f'<text x="{legend_x + 8}" y="55.5" font-size="11">{t(lang, "gantt_delivery_legend", tons=tons)}</text>')

    # --- row backgrounds, machine labels, row separators ---
    for i, mesin in enumerate(machines):
        y = TOP_MARGIN + i * ROW_HEIGHT
        if i % 2 == 1:
            svg_parts.append(
                f'<rect class="row-stripe" x="{LEFT_MARGIN}" y="{y}" width="{grid_width}" '
                f'height="{ROW_HEIGHT}" fill="#f5f6f8"/>'
            )
        svg_parts.append(f'<text x="4" y="{y + ROW_HEIGHT / 2 + 4:.1f}" font-size="12" font-weight="600">{mesin}</text>')
        svg_parts.append(
            f'<line x1="{LEFT_MARGIN}" y1="{y + ROW_HEIGHT}" x2="{LEFT_MARGIN + grid_width}" y2="{y + ROW_HEIGHT}" '
            f'stroke="#ddd" stroke-width="1"/>'
        )

    # --- day-axis gridlines + labels ---
    interval = _tick_interval(max_day)
    day = 0
    while day <= max_day + interval:
        x = LEFT_MARGIN + day * DAY_WIDTH
        svg_parts.append(
            f'<line x1="{x:.1f}" y1="{TOP_MARGIN}" x2="{x:.1f}" y2="{grid_bottom}" '
            f'stroke="#e8e8e8" stroke-width="1" stroke-dasharray="2,2"/>'
        )
        svg_parts.append(f'<text x="{x:.1f}" y="{grid_bottom + 16}" font-size="10" fill="#666" text-anchor="middle">{day}</text>')
        day += interval
    svg_parts.append(f'<text x="{LEFT_MARGIN + grid_width / 2:.1f}" y="{height - 2}" font-size="10" fill="#666" text-anchor="middle">{t(lang, "gantt_axis")}</text>')

    # --- event bars ---
    row_end_day = {mesin: 0.0 for mesin in machines}
    for e in events:
        row = machines.index(e["mesin"])
        y = TOP_MARGIN + row * ROW_HEIGHT + 8
        bar_h = ROW_HEIGHT - 16
        start = float(e["start_day"])
        end = float(e["end_day"])
        x = LEFT_MARGIN + start * DAY_WIDTH
        w = max((end - start) * DAY_WIDTH, 2)
        color = COLORS[e["event_type"]]
        row_end_day[e["mesin"]] = max(row_end_day[e["mesin"]], end)

        svg_parts.append(
            f'<rect class="event-bar" x="{x:.1f}" y="{y}" width="{w:.1f}" height="{bar_h}" '
            f'fill="{color}" rx="2" stroke="#fff" stroke-width="0.5">'
            f'<title>{_bar_tooltip(e)}</title></rect>'
        )

        if e["event_type"] == "production":
            text = _fitted_text(f'{e["po_no"]} {e["size"]}', w)
            text_color = "#fff"
        else:
            text = _fitted_text(SHORT_LABEL[e["event_type"]], w, char_px=7)
            text_color = "#333"
        if text:
            svg_parts.append(
                f'<text x="{x + 4:.1f}" y="{y + bar_h / 2 + 3.5:.1f}" font-size="10" fill="{text_color}">{text}</text>'
            )

    # --- per-machine total elapsed time, printed after the last bar in each row ---
    for i, mesin in enumerate(machines):
        total = row_end_day[mesin]
        y = TOP_MARGIN + i * ROW_HEIGHT + ROW_HEIGHT / 2 + 4
        label = t(lang, "machine_total", days=f"{total:.1f}") if total > 0 else t(lang, "idle")
        x = LEFT_MARGIN + max(total * DAY_WIDTH, 0) + 6
        svg_parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="10" fill="#888">{label}</text>')

    # --- delivery lines, one per full batch, labeled just above the grid ---
    for d in deliveries:
        if d["delivery_no"] == "leftover":
            continue
        x = LEFT_MARGIN + float(d["day"]) * DAY_WIDTH
        svg_parts.append(
            f'<line class="delivery" x1="{x:.1f}" y1="{TOP_MARGIN - 4}" x2="{x:.1f}" y2="{grid_bottom}" '
            f'stroke="{DELIVERY_COLOR}" stroke-width="2" stroke-dasharray="4,3">'
            f'<title>Delivery {d["delivery_no"]}: {int(float(d["cumulative_kg"]))} kg reached on day {d["day"]}</title></line>'
        )
        svg_parts.append(
            f'<text x="{x + 3:.1f}" y="{TOP_MARGIN - 6}" font-size="10" fill="{DELIVERY_COLOR}" font-weight="600">'
            f'D{d["delivery_no"]} · {t(lang, "day").lower()} {float(d["day"]):.1f}</text>'
        )

    svg = (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="font-family:Arial,Helvetica,sans-serif;background:#fff">' + "".join(svg_parts) + "</svg>"
    )
    return (
        "<!doctype html><meta charset=\"utf-8\">"
        f"<title>{title}</title>"
        "<body style=\"margin:20px;background:#fff\">" + svg + "</body>"
    )
