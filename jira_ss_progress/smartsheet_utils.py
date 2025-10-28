"""
Smartsheet helpers: client connection, column utilities, and cell parsing.
"""
from __future__ import annotations
from typing import Optional, Iterable, Iterator
import logging
import re

import smartsheet  # type: ignore

log = logging.getLogger(__name__)

JIRA_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

def client(token: str):
    """Return an authenticated Smartsheet client."""
    return smartsheet.Smartsheet(token)

def get_sheet(ss, sheet_id: int):
    """Fetch and return a full sheet by ID."""
    return ss.Sheets.get_sheet(sheet_id)

def column_id_by_title(sheet, title: str) -> int:
    """Find a column by title (case-insensitive) and return its ID."""
    t = title.strip().lower()
    for c in sheet.columns:
        if c.title.strip().lower() == t:
            return c.id
    raise KeyError(f"Column not found: {title}")

def extract_jira_key(cell) -> Optional[str]:
    """
    Extract a Jira key from a Smartsheet cell, preferring hyperlink URL.
    Accepts plain 'ABC-123' in value/display_value as a fallback.
    """
    if getattr(cell, "hyperlink", None) and getattr(cell.hyperlink, "type", None) == "URL":
        m = JIRA_KEY_RE.search(cell.hyperlink.url or "")
        if m: return m.group(1)
    for attr in ("value", "display_value"):
        v = getattr(cell, attr, None)
        if isinstance(v, str):
            m = JIRA_KEY_RE.search(v)
            if m: return m.group(1)
    return None

def parse_percent_cell(cell) -> Optional[float]:
    """Convert a Percent cell into 0..1 float (supports display like '25%')."""
    if cell is None:
        return None
    v = getattr(cell, "value", None)
    if isinstance(v, (int, float)):
        try:
            return float(v)
        except Exception:
            pass
    dv = getattr(cell, "display_value", None)
    if isinstance(dv, str) and dv.strip().endswith("%"):
        s = dv.strip().rstrip("%").strip()
        try:
            return float(s) / 100.0
        except Exception:
            return None
    return None

def text_cell_value(cell) -> Optional[str]:
    """Return a cell's text value (value or display_value) if any."""
    if cell is None:
        return None
    v = getattr(cell, "value", None)
    if isinstance(v, str) and v.strip():
        return v
    dv = getattr(cell, "display_value", None)
    if isinstance(dv, str) and dv.strip():
        return dv
    return None

def date_cell_iso(cell) -> Optional[str]:
    """
    Return a date-like cell as ISO 'YYYY-MM-DD' string for Jira.
    Prefers the underlying value (Smartsheet yields ISO-8601) and strips any time.
    """
    if cell is None:
        return None
    v = getattr(cell, "value", None)
    if isinstance(v, str) and v:
        s = v.strip()
        if "T" in s:
            s = s.split("T", 1)[0]
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return s
        return s  # attempt anyway
    dv = getattr(cell, "display_value", None)
    if isinstance(dv, str) and dv.strip():
        s = dv.strip()
        if "/" in s and len(s) in (8, 9, 10):
            parts = s.split("/")
            if len(parts) == 3:
                mm, dd, yy = parts
                if len(yy) == 2:
                    yy = ("20" + yy) if int(yy) < 70 else ("19" + yy)
                return f"{yy.zfill(4)}-{mm.zfill(2)}-{dd.zfill(2)}"
        if "-" in s and len(s) >= 10:
            return s[:10]
    return None

def chunk(it: Iterable, n: int) -> Iterator[list]:
    """Yield fixed-size batches from an iterable (last batch may be smaller)."""
    buf = []
    for x in it:
        buf.append(x)
        if len(buf) == n:
            yield buf; buf = []
    if buf:
        yield buf
