"""
Core sync logic that ties Jira and Smartsheet together.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
import logging

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

@dataclass
class SyncResult:
    updated_rows: int
    preview: List[PreviewRow]

def run_sync(cfg: Config) -> SyncResult:
    """Execute the sync based on the provided configuration."""
    # Connect clients
    jira = JU.connect(cfg.jira_base_url, cfg.jira_email, cfg.jira_api_token)
    ids = JU.resolve_field_ids(jira)
    log.info("Story Point fields detected: %s; Epic Link: %s", ids.story_points, ids.epic_link)

    ss = SU.client(cfg.smartsheet_token)
    sheet = SU.get_sheet(ss, cfg.sheet_id)

    jira_col = SU.column_id_by_title(sheet, cfg.jira_col_title)
    prog_col = SU.column_id_by_title(sheet, cfg.progress_col_title)

    # Collect rows (row_id, key, existing)
    row_info: List[tuple[int, str, Optional[float]]] = []
    for row in sheet.rows:
        cell_jira = next((c for c in row.cells if c.column_id == jira_col), None)
        cell_prog = next((c for c in row.cells if c.column_id == prog_col), None)
        key = SU.extract_jira_key(cell_jira) if cell_jira else None
        if key:
            existing = SU.parse_percent_cell(cell_prog)
            row_info.append((row.id, key, existing))
    log.info("Found %d Jira keys in sheet %s.", len(row_info), cfg.sheet_id)

    updates: List[Row] = []
    preview: List[PreviewRow] = []

    epic_cache: Dict[str, Tuple[Optional[float], dict]] = {}
    type_cache: Dict[str, str] = {}

    for rid, key, existing in row_info:
        # Classify issue type once
        if key not in type_cache:
            i = jira.issue(key, fields="issuetype")
            type_cache[key] = i.fields.issuetype.name.lower()

        # Compute new progress fraction
        if type_cache[key] == "epic":
            prog, details = epic_cache.get(key, (None, {}))
            if prog is None:
                prog, details = JU.epic_progress_details(jira, key, ids.story_points)
                epic_cache[key] = (prog, details)
            metric = details.get("metric", "count")
            if metric == "points":
                completed, total = details["done_sp"], details["total_sp"]
            else:
                completed, total = details["done_cnt"], details["total_cnt"]
            new_prog = (prog or 0.0)
            row_type = "epic"
        else:
            new_prog, sdetails = JU.story_progress_details(jira, key, include_subtasks=cfg.include_subtasks)
            metric = sdetails["metric"]
            completed, total = sdetails["completed"], sdetails["total"]
            row_type = "story"

        # Protect existing non-zero from being overwritten by 0
        protected = False
        final_prog = new_prog
        if cfg.protect_existing_nonzero and new_prog == 0.0 and (existing or 0.0) > 0.0:
            final_prog = existing or 0.0
            protected = True

        # Preview row
        preview.append(PreviewRow(
            issue_key=key, type=row_type, metric=metric,
            completed=completed, total=total,
            existing_pct=(existing or 0.0)*100.0,
            new_pct=new_prog*100.0,
            final_pct=(final_prog or 0.0)*100.0,
            protected=protected
        ))

        # Only enqueue update if value actually changes
        if (existing is None) or (abs((existing or 0.0) - (final_prog or 0.0)) > 1e-9):
            c = Cell(); c.column_id = prog_col; c.value = float(max(0.0, min(1.0, final_prog or 0.0)))
            r = Row(); r.id = rid; r.cells = [c]
            updates.append(r)

    # Write updates if not dry-run
    if not cfg.dry_run and updates:
        for batch in SU.chunk(updates, 400):
            ss.Sheets.update_rows(cfg.sheet_id, batch)

    return SyncResult(updated_rows=len(updates) if not cfg.dry_run else 0, preview=preview)
