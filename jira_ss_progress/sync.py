"""
Core sync logic that ties Jira and Smartsheet together, including Status and Date updates.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
import logging
from jira.exceptions import JIRAError

from smartsheet.models import Row, Cell  # type: ignore

from .config import Config
from . import jira_utils as JU
from . import smartsheet_utils as SU

log = logging.getLogger(__name__)

@dataclass
class PreviewRow:
    issue_key: str
    type: str                # 'epic' or 'story'
    metric: str              # 'points'|'count'|'story'|'subtasks'
    completed: float | int
    total: float | int
    existing_pct: float      # 0..100
    new_pct: float           # 0..100
    final_pct: float         # 0..100
    protected: bool
    # Status preview (strings)
    existing_status: Optional[str]
    new_status: Optional[str]
    final_status: Optional[str]
    # Date preview
    start_old: Optional[str]
    start_new: Optional[str]
    start_final: Optional[str]
    end_old: Optional[str]
    end_new: Optional[str]
    end_final: Optional[str]

@dataclass
class SyncResult:
    updated_rows: int
    preview: List[PreviewRow]

def _label_from_cat(cat_key: str) -> str:
    """Map Jira statusCategory key → Smartsheet status label."""
    ck = (cat_key or "").lower()
    if ck == "done":
        return "Complete"
    if ck == "indeterminate":
        return "In Progress"
    return "Not Started"  # 'new' or unknown

def run_sync(cfg: Config) -> SyncResult:
    """Execute the sync based on the provided configuration."""
    jira = JU.connect(cfg.jira_base_url, cfg.jira_email, cfg.jira_api_token)
    ids = JU.resolve_field_ids(jira)
    log.info("Story Point fields detected: %s; Epic Link: %s", ids.story_points, ids.epic_link)

    start_field_key = JU.resolve_configured_field(jira, cfg.jira_start_field)
    end_field_key = JU.resolve_configured_field(jira, cfg.jira_end_field)
    log.info("Using Jira date fields → start=%r end=%r", start_field_key, end_field_key)

    ss = SU.client(cfg.smartsheet_token)
    sheet = SU.get_sheet(ss, cfg.sheet_id)

    jira_col = SU.column_id_by_title(sheet, cfg.jira_col_title)
    prog_col = SU.column_id_by_title(sheet, cfg.progress_col_title)

    status_col: Optional[int] = None
    try:
        status_col = SU.column_id_by_title(sheet, cfg.status_col_title)
        log.info("Status column found: %s", cfg.status_col_title)
    except Exception:
        log.info("Status column not found; skipping status updates. (Looked for: %s)", cfg.status_col_title)

    start_col: Optional[int] = None
    end_col: Optional[int] = None
    try:
        start_col = SU.column_id_by_title(sheet, cfg.start_col_title)
        log.info("Start column found: %s", cfg.start_col_title)
    except Exception:
        log.info("Start column not found; skipping date start updates. (Looked for: %s)", cfg.start_col_title)
    try:
        end_col = SU.column_id_by_title(sheet, cfg.end_col_title)
        log.info("End column found: %s", cfg.end_col_title)
    except Exception:
        log.info("End column not found; skipping date end updates. (Looked for: %s)", cfg.end_col_title)

    row_info: List[tuple[int, str, Optional[float], Optional[str], Optional[str], Optional[str]]] = []
    for row in sheet.rows:
        cell_jira = next((c for c in row.cells if c.column_id == jira_col), None)
        key = SU.extract_jira_key(cell_jira) if cell_jira else None
        if not key:
            continue
        cell_prog = next((c for c in row.cells if c.column_id == prog_col), None)
        existing = SU.parse_percent_cell(cell_prog)
        cell_status = next((c for c in row.cells if status_col is not None and c.column_id == status_col), None) if status_col is not None else None
        existing_status = SU.text_cell_value(cell_status) if cell_status is not None else None
        start_iso = None
        end_iso = None
        if start_col is not None:
            sc = next((c for c in row.cells if c.column_id == start_col), None)
            start_iso = SU.date_cell_iso(sc)
        if end_col is not None:
            ec = next((c for c in row.cells if c.column_id == end_col), None)
            end_iso = SU.date_cell_iso(ec)
        row_info.append((row.id, key, existing, existing_status, start_iso, end_iso))

    log.info("Found %d Jira keys in sheet %s.", len(row_info), cfg.sheet_id)

    updates: List[Row] = []
    preview: List[PreviewRow] = []

    epic_cache: Dict[str, Tuple[Optional[float], dict]] = {}
    type_cache: Dict[str, str] = {}

    for rid, key, existing, existing_status, start_iso, end_iso in row_info:
        # Ensure we know the Jira issue type (epic/story) — cache lookups.
        if key not in type_cache:
            try:
                i = jira.issue(key, fields="issuetype")
                type_cache[key] = i.fields.issuetype.name.lower()
            except JIRAError as e:
                status = getattr(e, "status_code", None)
                if status == 404:
                    log.warning("Jira issue %s not found (404). It may have been deleted; skipping.", key)
                    continue
                raise

        issue_type = type_cache[key]

        # Compute progress/status based on type
        if issue_type == "epic":
            # cache epic computations to avoid repeated queries
            if key not in epic_cache:
                epic_cache[key] = epic_progress_details = JU.epic_progress_details(jira, key, ids.story_points)
            completed, details = epic_cache[key]
            metric = details.get("metric", "count")
            total = details.get("total", 0)
            new_pct = (completed / total * 100) if total else 0.0
            new_status = details.get("status")  # expected to be like 'Complete'/'In Progress'/'Not Started'
        else:
            completed, details = JU.story_progress_details(jira, key, include_subtasks=cfg.include_subtasks)
            metric = details.get("metric", "story")
            total = details.get("total", 1)
            new_pct = (completed / total * 100) if total else 0.0
            new_status = details.get("status")

        # Protection: do not overwrite an existing non-zero Smartsheet percent with a Jira 0%
        protected = False
        final_pct = new_pct
        if cfg.protect_existing_nonzero and existing is not None and existing > 0 and new_pct == 0:
            protected = True
            final_pct = existing * 100.0  # existing is 0..1 from Smartsheet

        # Date handling (preview values)
        jira_dates = JU.get_issue_dates(jira, key, start_field_key, end_field_key)
        start_old = start_iso or jira_dates.get("start")
        end_old = end_iso or jira_dates.get("end")
        start_new = start_iso  # what we'd push (if any)
        end_new = end_iso

        # Status handling: preserve special manual statuses like "Blocked"
        #  - If the sheet already shows "Blocked", don't remove it
        #  - If protection prevents a downgrade to "Not Started", keep existing_status
        #  - If progress is 100%, always set status to "Complete"
        final_status = new_status
        if existing_status:
            if existing_status.strip().lower() == "blocked":
                final_status = existing_status  # always preserve Blocked
            elif cfg.protect_existing_nonzero and protected and (new_status == "Not Started"):
                # avoid downgrading to Not Started when progress protection kept a non-zero %
                final_status = existing_status
        
        # Force Complete status if progress is 100%
        if final_pct == 100.0:
            final_status = "Complete"

        # Build preview row
        preview.append(PreviewRow(
            issue_key=key,
            type=issue_type,
            metric=metric,
            completed=completed,
            total=total,
            existing_pct=(existing * 100.0) if existing is not None else 0.0,
            new_pct=new_pct,
            final_pct=final_pct,
            protected=protected,
            existing_status=existing_status,
            new_status=new_status,
            final_status=final_status,
            start_old=start_old,
            start_new=start_new,
            start_final=(start_old if (cfg.protect_existing_dates and not start_new) else (start_new or start_old)),
            end_old=end_old,
            end_new=end_new,
            end_final=(end_old if (cfg.protect_existing_dates and not end_new) else (end_new or end_old)),
        ))

        # Only prepare a Smartsheet row update when not a dry run and when something changed.
        if not cfg.dry_run:
            row_update_needed = False
            cells = []

            # Percent cell
            if final_pct is not None:
                # Smartsheet percent column expects 0..1 floats
                new_val = round(final_pct / 100.0, 6)
                if existing is None or abs((existing or 0.0) - new_val) > 0.000001:
                    c = Cell()
                    c.column_id = prog_col
                    c.value = new_val
                    cells.append(c)
                    row_update_needed = True

            # Status cell — do not overwrite "Blocked"
            if status_col is not None and final_status is not None:
                if not (existing_status and existing_status.strip().lower() == "blocked"):
                    if existing_status != final_status:
                        c = Cell()
                        c.column_id = status_col
                        c.value = final_status
                        cells.append(c)
                        row_update_needed = True
                else:
                    log.debug("Preserving existing 'Blocked' status for %s; skipping status update.", key)

            # Dates: respect PROTECT_EXISTING_DATES
            if start_col is not None:
                if start_new is not None or (not cfg.protect_existing_dates):
                    if start_old != start_new:
                        c = Cell()
                        c.column_id = start_col
                        c.value = start_new
                        cells.append(c)
                        row_update_needed = True
            if end_col is not None:
                if end_new is not None or (not cfg.protect_existing_dates):
                    if end_old != end_new:
                        c = Cell()
                        c.column_id = end_col
                        c.value = end_new
                        cells.append(c)
                        row_update_needed = True

            if row_update_needed:
                r = Row()
                r.id = rid
                r.cells = cells
                updates.append(r)

    if updates and not cfg.dry_run:
        for batch in SU.chunk(updates, 400):
            ss.Sheets.update_rows(cfg.sheet_id, batch)

    return SyncResult(updated_rows=len(updates) if not cfg.dry_run else 0, preview=preview)
