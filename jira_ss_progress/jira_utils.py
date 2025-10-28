"""
Jira utilities for connecting, querying, progress/status computation, and date updates.
"""
from __future__ import annotations
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
import logging

from jira import JIRA  # type: ignore

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class JiraFieldIds:
    story_points: List[str]
    epic_link: Optional[str]

def connect(server: str, email: str, api_token: str) -> JIRA:
    """Create an authenticated Jira client (Cloud)."""
    return JIRA(server=server, basic_auth=(email, api_token))

def resolve_field_ids(jira: JIRA) -> JiraFieldIds:
    """Discover Story Points fields and the legacy 'Epic Link' field id."""
    sp_ids: List[str] = []
    epic_link: Optional[str] = None
    for f in jira.fields():
        name = (f.get("name") or "").strip().lower()
        if name in {"story points", "story point estimate"}:
            sp_ids.append(f["id"])
        if name == "epic link":
            epic_link = f["id"]
    return JiraFieldIds(story_points=sp_ids, epic_link=epic_link)

def _field_id_by_name(jira: JIRA, name: str) -> Optional[str]:
    """Case-insensitive lookup of a field ID by its display name."""
    target = name.strip().lower()
    for f in jira.fields():
        if (f.get("name") or "").strip().lower() == target:
            return f["id"]
    return None

def resolve_configured_field(jira: JIRA, configured: str) -> Optional[str]:
    """
    Accepts:
      - customfield id (e.g., 'customfield_12345')  → returned as-is
      - 'duedate' (built-in)                         → returned as-is
      - field display name (case-insensitive)        → resolved to its id
    Returns the field key/id to use in issue.update(fields={...}).
    """
    key = (configured or "").strip()
    if not key:
        return None
    if key.lower() == "duedate" or key.startswith("customfield_"):
        return key
    fid = _field_id_by_name(jira, key)
    if fid:
        return fid
    log.warning("Jira field not found by name: %r", configured)
    return None

def get_issue_dates(jira: JIRA, issue_key: str, start_field: Optional[str], end_field: Optional[str]) -> Dict[str, Optional[str]]:
    """Fetch current values for start/end date fields from Jira (ISO yyyy-mm-dd if present)."""
    want = []
    if start_field: want.append(start_field)
    if end_field:
        want.append("duedate" if end_field == "duedate" else end_field)
    fields = ",".join(want) if want else "none"
    issue = jira.issue(issue_key, fields=fields)
    vals: Dict[str, Optional[str]] = {"start": None, "end": None}
    if start_field:
        vals["start"] = getattr(issue.fields, start_field, None)
    if end_field:
        vals["end"] = getattr(issue.fields, "duedate", None) if end_field == "duedate" else getattr(issue.fields, end_field, None)
    return vals

def update_issue_dates(jira: JIRA, issue_key: str, start_field: Optional[str], end_field: Optional[str],
                       start_value: Optional[str], end_value: Optional[str]) -> None:
    """
    Update Jira issue date fields with ISO 'YYYY-MM-DD' strings.
    Only non-None values are sent (no clearing unless explicitly provided).
    """
    payload: Dict[str, Optional[str]] = {}
    if start_field and start_value is not None:
        payload[start_field] = start_value
    if end_field and end_field == "duedate" and end_value is not None:
        payload["duedate"] = end_value
    elif end_field and end_value is not None:
        payload[end_field] = end_value
    if not payload:
        return
    jira.issue(issue_key).update(fields=payload)

# -------- Progress & status helpers --------

def search_all(jira: JIRA, jql: str, fields: List[str]) -> List:
    """Run a JQL and return ALL issues (python-jira paginates for us)."""
    return list(jira.search_issues(jql, maxResults=False, fields=",".join(fields)))

def epic_children(jira: JIRA, epic_key: str, fields: List[str]) -> List:
    """Children for an epic: prefer parentEpic, fallback to 'Epic Link'."""
    for jql in (
        f'parentEpic = "{epic_key}" AND issuetype in standardIssueTypes()',
        f'"Epic Link" = "{epic_key}" AND issuetype in standardIssueTypes()',
    ):
        issues = search_all(jira, jql, fields)
        if issues:
            return issues
    return []

def status_category_key(issue) -> str:
    """
    Return Jira statusCategory key normalized to: 'new'|'indeterminate'|'done'.
    Jira UI labels are typically 'To Do'|'In Progress'|'Done'.
    """
    st = getattr(issue.fields, "status", None)
    cat = getattr(st, "statusCategory", None)
    key = (getattr(cat, "key", "") or "").lower()
    if key in {"new", "indeterminate", "done"}:
        return key
    # Fallback by name
    name = (getattr(cat, "name", "") or "").lower()
    if "progress" in name:
        return "indeterminate"
    if "done" in name or "complete" in name:
        return "done"
    return "new"

def is_done(issue) -> bool:
    """Status category is Done → treat as complete (robust across custom names)."""
    return status_category_key(issue) == "done"

def get_story_points(issue, sp_ids: List[str]) -> Optional[float]:
    """Return numeric Story Points from the first matching field, if any."""
    for spid in sp_ids:
        v = getattr(issue.fields, spid, None)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    return None

def epic_progress_details(jira: JIRA, epic_key: str, sp_ids: List[str]) -> Tuple[Optional[float], Dict]:
    """
    Compute epic progress and return (progress_fraction, details).
    'details' includes metric ('points' or 'count') and totals for diagnostics, plus
    category counts: todo_cnt, inprog_cnt, done_cnt.
    """
    fields = ["status"] + sp_ids
    children = epic_children(jira, epic_key, fields)
    details = {"metric": "count", "total_sp": 0.0, "done_sp": 0.0,
               "total_cnt": 0, "done_cnt": 0, "todo_cnt": 0, "inprog_cnt": 0}
    if not children:
        return None, details

    total_sp = done_sp = 0.0
    any_sp = False
    todo = inprog = done = 0

    for it in children:
        cat = status_category_key(it)
        if cat == "new":
            todo += 1
        elif cat == "indeterminate":
            inprog += 1
        elif cat == "done":
            done += 1

        sp = get_story_points(it, sp_ids)
        if sp is not None:
            any_sp = True
            total_sp += sp
            if cat == "done":
                done_sp += sp

    total_cnt = len(children)
    details.update({"todo_cnt": todo, "inprog_cnt": inprog, "done_cnt": done, "total_cnt": total_cnt})

    if any_sp and total_sp > 0:
        details.update({"metric": "points", "total_sp": total_sp, "done_sp": done_sp})
        return max(0.0, min(1.0, done_sp / total_sp)), details

    details.update({"total_sp": total_sp, "done_sp": done_sp})
    return (max(0.0, min(1.0, done / total_cnt)) if total_cnt else None), details

def story_progress_details(jira: JIRA, issue_key: str, include_subtasks: bool=False) -> Tuple[float, Dict]:
    """
    Non-epic progress:
      - Default: binary → Done = 1.0 else 0.0
      - If include_subtasks=True: fraction from subtasks (done/total)
    Returns details with 'metric','completed','total','status_cat'.
    """
    fields = "status,subtasks" if include_subtasks else "status"
    issue = jira.issue(issue_key, fields=fields)
    status_cat = status_category_key(issue)

    if not include_subtasks:
        prog = 1.0 if status_cat == "done" else 0.0
        return prog, {"metric":"story","completed": 1 if prog==1.0 else 0, "total":1, "status_cat": status_cat}

    subs = getattr(issue.fields, "subtasks", []) or []
    if not subs:  # no subtasks → fallback to binary
        prog = 1.0 if status_cat == "done" else 0.0
        return prog, {"metric":"story","completed": 1 if prog==1.0 else 0, "total":1, "status_cat": status_cat}

    done = 0
    for s in subs:
        si = jira.issue(s.key, fields="status")
        if status_category_key(si) == "done":
            done += 1
    total = len(subs)
    prog = done/total if total else (1.0 if status_cat == "done" else 0.0)
    return prog, {"metric":"subtasks","completed":done,"total":total, "status_cat": status_cat}
