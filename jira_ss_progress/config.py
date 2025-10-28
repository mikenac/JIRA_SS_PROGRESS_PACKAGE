"""
Configuration loading for the Jira → Smartsheet sync.
Reads environment variables (optionally from a .env via python-dotenv).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import os
import logging

try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency, but recommended
    load_dotenv = None  # type: ignore
    find_dotenv = None  # type: ignore

log = logging.getLogger(__name__)

def _as_bool(val: str | None, default: bool=False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1","true","yes","y","on"}

@dataclass(frozen=True)
class Config:
    # Jira
    jira_base_url: str
    jira_email: str
    jira_api_token: str

    # Smartsheet
    smartsheet_token: str
    sheet_id: int

    # Columns
    jira_col_title: str = "Jira"
    progress_col_title: str = "% Complete"
    status_col_title: str = "Status"            # optional
    start_col_title: str = "Start"              # Smartsheet Start column
    end_col_title: str = "End"                  # Smartsheet End column

    # Jira date fields (name, 'duedate', or 'customfield_XXXXX')
    jira_start_field: str = "Start date"
    jira_end_field: str = "Due date"            # 'duedate' built-in

    # Behavior
    dry_run: bool = False
    protect_existing_nonzero: bool = True       # keep non-zero progress if Jira=0
    include_subtasks: bool = False
    protect_existing_dates: bool = True         # don't clear Jira when Smartsheet blank

    # Logging
    log_level: str = "INFO"

def load_config() -> Config:
    """
    Load configuration from environment variables.
    If python-dotenv is present, load .env (or ENV_FILE) first.
    """
    if load_dotenv and find_dotenv:
        env_file = os.environ.get("ENV_FILE") or find_dotenv()
        if env_file:
            load_dotenv(env_file, override=False)

    # Required
    jira_base = (os.environ.get("JIRA_BASE_URL") or "").rstrip("/")
    jira_email = os.environ.get("JIRA_EMAIL") or ""
    jira_token = os.environ.get("JIRA_API_TOKEN") or ""

    ss_token = os.environ.get("SMARTSHEET_ACCESS_TOKEN") or ""
    sheet_id_str = os.environ.get("SS_SHEET_ID") or "0"

    # Validate basics early
    try:
        sheet_id = int(sheet_id_str)
    except ValueError:
        raise ValueError(f"SS_SHEET_ID must be an integer (got {sheet_id_str!r})")

    if not jira_base or not jira_email or not jira_token:
        raise ValueError("Missing Jira config: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN")
    if not ss_token or sheet_id <= 0:
        raise ValueError("Missing Smartsheet config: SMARTSHEET_ACCESS_TOKEN, SS_SHEET_ID")

    cfg = Config(
        jira_base_url=jira_base,
        jira_email=jira_email,
        jira_api_token=jira_token,
        smartsheet_token=ss_token,
        sheet_id=sheet_id,
        jira_col_title=os.environ.get("SS_JIRA_COL", "Jira"),
        progress_col_title=os.environ.get("SS_PROG_COL", "% Complete"),
        status_col_title=os.environ.get("SS_STATUS_COL", "Status"),
        start_col_title=os.environ.get("SS_START_COL", "Start"),
        end_col_title=os.environ.get("SS_END_COL", "End"),
        jira_start_field=os.environ.get("JIRA_START_FIELD", "Start date"),
        jira_end_field=os.environ.get("JIRA_END_FIELD", "Due date"),
        dry_run=_as_bool(os.environ.get("DRY_RUN"), False),
        protect_existing_nonzero=_as_bool(os.environ.get("PROTECT_EXISTING_NONZERO"), True),
        include_subtasks=_as_bool(os.environ.get("INCLUDE_SUBTASKS"), False),
        protect_existing_dates=_as_bool(os.environ.get("PROTECT_EXISTING_DATES"), True),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
    return cfg
