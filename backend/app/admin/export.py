"""CSV and Excel export: one row per volunteer with total hours, plus totals by Mandal and Mandal Type."""

import csv
import io
import tempfile
from collections.abc import Iterator
from datetime import datetime

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font

from ..config import get_settings
from ..enums import MANDAL_NAMES, MANDAL_TYPES
from ..reports.timecalc import decimal_hours, format_hm_short

HEADERS = [
    "Rank",
    "Volunteer Name",
    "Username",
    "Mandal Name",
    "Mandal Type",
    "Sessions",
    "Total Hours (h m)",
    "Total Hours",
]


def _safe(value):
    """Neutralise spreadsheet formula injection in text cells."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def volunteer_rows(totals: dict, users: dict) -> list[list]:
    """One row per volunteer with their total hours, most hours first (ties by name).

    `totals` maps user_id to {"seconds", "sessions"}; `users` maps user_id to the user document.
    """
    def name(uid) -> str:
        return users.get(uid, {}).get("full_name", "Unknown")

    ranked = sorted(totals.items(), key=lambda kv: (-kv[1]["seconds"], name(kv[0]).lower()))
    rows = []
    for rank, (uid, t) in enumerate(ranked, start=1):
        u = users.get(uid, {})
        rows.append([
            rank,
            _safe(name(uid)),
            _safe(u.get("username", "")),
            u.get("mandal_name", ""),
            u.get("mandal_type", ""),
            t["sessions"],
            format_hm_short(t["seconds"]),
            float(decimal_hours(t["seconds"])),
        ])
    return rows


def summary_rows(label: str, total: dict, by_mandal: dict, by_type: dict, generated_at: datetime) -> list[list]:
    def line(name: str, t: dict) -> list:
        return [name, t["sessions"], format_hm_short(t["seconds"]), float(decimal_hours(t["seconds"]))]

    empty = {"seconds": 0, "sessions": 0}

    def ranked(names, totals: dict) -> list[list]:
        # Most hours first; stable, so ties keep the standard order. Rank and share columns follow the hours.
        order = sorted(names, key=lambda n: -totals.get(n, empty)["seconds"])
        group_total = sum(totals.get(n, empty)["seconds"] for n in names)
        rows = []
        for rank, n in enumerate(order, start=1):
            t = totals.get(n, empty)
            share = round(100 * t["seconds"] / group_total, 1) if group_total else 0.0
            rows.append([*line(n, t), rank, share])
        return rows

    rows: list[list] = [
        ["Report", label],
        ["Generated", generated_at.astimezone(get_settings().tz).strftime("%Y-%m-%d %I:%M %p %Z")],
        ["Each volunteer appears once with their total hours. Sessions still in progress are excluded unless the Active filter is set."],
        [],
        ["Total", "Sessions", "Hours (h m)", "Hours"],
        line("All sessions", total),
        [],
        ["Mandal Name", "Sessions", "Hours (h m)", "Hours", "Rank", "% of total"],
        *ranked(MANDAL_NAMES, by_mandal),
        [],
        ["Mandal Type", "Sessions", "Hours (h m)", "Hours", "Rank", "% of total"],
        *ranked(MANDAL_TYPES, by_type),
    ]
    return rows


def _csv_line(row: list) -> str:
    buf = io.StringIO()
    csv.writer(buf).writerow(row)
    return buf.getvalue()


def stream_csv(rows: list[list], summary: list[list]) -> Iterator[str]:
    yield "﻿"  # BOM so Excel opens UTF-8 correctly
    yield _csv_line(HEADERS)
    for row in rows:
        yield _csv_line(row)
    yield "\r\n"
    for r in summary:
        yield _csv_line(r)


def build_xlsx(rows: list[list], summary: list[list]) -> tempfile.SpooledTemporaryFile:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Volunteers")
    bold = Font(bold=True)
    def header(cells: list) -> list:
        out = []
        for c in cells:
            cell = WriteOnlyCell(ws, value=c)
            cell.font = bold
            out.append(cell)
        return out

    ws.append(header(HEADERS))
    for row in rows:
        ws.append(row)

    ss = wb.create_sheet("Summary")
    for r in summary:
        ss.append(r)

    f = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
    wb.save(f)
    f.seek(0)
    return f


def iter_file(f, chunk: int = 64 * 1024) -> Iterator[bytes]:
    try:
        while data := f.read(chunk):
            yield data
    finally:
        f.close()
