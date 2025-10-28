# Jira → Smartsheet Progress Sync (modular)

A small, modular tool to sync Jira progress into a Smartsheet **Percent** column,
optionally set a **Status** column, and push **Start/End** dates from Smartsheet into Jira.

- **Epic rows** → writes Epic completion (Story Points first; fallback to counts).
- **Story/Task/Bug rows** → writes 100% when **Done** (status category), else 0%.
  - Optional: fractional story progress from **subtasks**.
- **Protection**: if Smartsheet already has **> 0%**, we do **not overwrite with 0%** from Jira.
- **Status column** (optional): sets **Not Started / In Progress / Complete** based on Jira category (or Epic children).
- **Date sync** (optional): reads **Start/End** from Smartsheet and updates Jira date fields.

## Install & Run with `uv`

```bash
# 0) (optional) install uv
# curl -LsSf https://astral.sh/uv/install.sh | sh

# 1) From the project root (where pyproject.toml lives)
uv sync

# 2) Dry-run preview (no writes)
DRY_RUN=1 uv run jira-ss-sync --log-level INFO

# 3) Real run
uv run jira-ss-sync --log-level INFO
```

## Environment

Create `.env` next to your code (or set env vars directly):

```ini
# Jira Cloud
JIRA_BASE_URL=https://<your-tenant>.atlassian.net
JIRA_EMAIL=you@your.org
JIRA_API_TOKEN=********

# Smartsheet
SMARTSHEET_ACCESS_TOKEN=********
SS_SHEET_ID=1234567890123456

# Optional overrides
SS_JIRA_COL=Jira
SS_PROG_COL=% Complete
SS_STATUS_COL=Status
SS_START_COL=Start
SS_END_COL=End

# Jira field mapping for dates
JIRA_START_FIELD=Start date      # or customfield_10015
JIRA_END_FIELD=duedate           # or End date / customfield_10016

# Behavior
DRY_RUN=1
PROTECT_EXISTING_NONZERO=1
INCLUDE_SUBTASKS=0
PROTECT_EXISTING_DATES=1
LOG_LEVEL=INFO
```

> The **Smartsheet percent** column must be type **Percent** and uses **0.0–1.0** values.

## How it works

1. Load config from env (`jira_ss_progress.config.load_config`).
2. Connect to Jira & Smartsheet.
3. For each row with a Jira key in the Jira column:
   - If the key is an **Epic**: compute Epic progress via `jira_ss_progress.jira_utils.epic_progress_details`
     - Prefer **Story Points** (Done SP / Total SP) if any estimates exist;
       else use **counts** (Done / Total).
     - Children are limited to **standard issue types** (subtasks excluded).
   - If the key is **not an Epic**: compute Story progress via `jira_ss_progress.jira_utils.story_progress_details`
     - Default **binary** (Done=100%, else 0%).
     - If `INCLUDE_SUBTASKS=1`: **done_subtasks / total_subtasks**.
   - Apply **protection** so 0% from Jira will not replace an existing non-zero Smartsheet value.
   - Optionally set **Status** in Smartsheet from Jira category (or Epic children state).
   - Optionally update **Start/End** Jira fields from Smartsheet date columns.
4. Write updates (unless `DRY_RUN=1`).

### Status mapping
- Jira status category **To Do** → **Not Started**
- Jira status category **In Progress** → **In Progress**
- Jira status category **Done** → **Complete**
- Epics use children: all Done → Complete; any started/done → In Progress; else Not Started.
- If progress protection is active (keeping a non-zero Smartsheet value when Jira computed 0%), the tool also
  avoids downgrading the **Status** to “Not Started.”

### Date syncing
- Smartsheet → Jira:
  - Reads `SS_START_COL` / `SS_END_COL` and normalizes to `YYYY-MM-DD`.
  - Maps to Jira fields `JIRA_START_FIELD` and `JIRA_END_FIELD` (supports `duedate` or customfield IDs or display names).
  - If `PROTECT_EXISTING_DATES=1`, blank Smartsheet cells do **not** clear Jira dates.
- DRY RUN preview shows **Start/End Old/New/Final** alongside progress & status.

## Troubleshooting

- 401/403 from Jira → check tenant URL, email, API token.
- Smartsheet write errors → ensure output column is **Percent** and you write **0.0–1.0** floats.
- No progress for an Epic → verify children exist and are standard issue types; check Story Points field names.
