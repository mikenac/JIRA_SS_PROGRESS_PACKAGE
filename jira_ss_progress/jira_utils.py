"""
Jira utilities for connecting, querying, and computing progress.
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

def is_done(issue) -> bool:
    """Status category is Done → treat as complete (robust across custom names)."""
    st = getattr(issue.fields, "status", None)
    cat = getattr(st, "statusCategory", None)
    key = (getattr(cat, "key", "") or "").lower()
    name = (getattr(cat, "name", "") or "").lower()
    return key == "done" or name == "done"

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
    'details' includes metric ('points' or 'count') and totals for diagnostics.
    """
    fields = ["status"] + sp_ids
    children = epic_children(jira, epic_key, fields)
    details = {"metric": "count", "total_sp": 0.0, "done_sp": 0.0, "total_cnt": 0, "done_cnt": 0}
    if not children:
        return None, details

    total_sp = done_sp = 0.0
    any_sp = False
    for it in children:
        sp = get_story_points(it, sp_ids)
        if sp is not None:
            any_sp = True
            total_sp += sp
            if is_done(it):
                done_sp += sp

    total_cnt = len(children)
    done_cnt = sum(1 for it in children if is_done(it))

    if any_sp and total_sp > 0:
        details.update({"metric": "points", "total_sp": total_sp, "done_sp": done_sp,
                        "total_cnt": total_cnt, "done_cnt": done_cnt})
        return max(0.0, min(1.0, done_sp / total_sp)), details

    details.update({"metric": "count", "total_sp": total_sp, "done_sp": done_sp,
                    "total_cnt": total_cnt, "done_cnt": done_cnt})
    return (max(0.0, min(1.0, done_cnt / total_cnt)) if total_cnt else None), details

def story_progress_details(jira: JIRA, issue_key: str, include_subtasks: bool=False) -> Tuple[float, Dict]:
    """
    Non-epic progress:
      - Default: binary → Done = 1.0 else 0.0
      - If include_subtasks=True: fraction from subtasks (done/total)
    """
    fields = "status,subtasks" if include_subtasks else "status"
    issue = jira.issue(issue_key, fields=fields)

    if not include_subtasks:
        prog = 1.0 if is_done(issue) else 0.0
        return prog, {"metric":"story","completed": 1 if prog==1.0 else 0, "total":1}

    subs = getattr(issue.fields, "subtasks", []) or []
    if not subs:
        prog = 1.0 if is_done(issue) else 0.0
        return prog, {"metric":"story","completed": 1 if prog==1.0 else 0, "total":1}

    done = 0
    for s in subs:
        si = jira.issue(s.key, fields="status")
        if is_done(si):
            done += 1
    total = len(subs)
    prog = done/total if total else (1.0 if is_done(issue) else 0.0)
    return prog, {"metric":"subtasks","completed":done,"total":total}
