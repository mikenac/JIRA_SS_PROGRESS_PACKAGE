# Jira → Smartsheet Progress Sync (modular)

A small, modular tool to sync Jira progress into a Smartsheet **Percent** column.

- **Epic rows** → writes Epic completion (Story Points first; fallback to counts).
- **Story/Task/Bug rows** → writes 100% when **Done** (status category), else 0%.
  - Optional: make story progress fractional from **subtasks**.
- **Protection**: if Smartsheet already has **> 0%**, we do **not overwrite with 0%** from Jira.

---

## Quick Start with `uv`

[`uv`](https://github.com/astral-sh/uv) makes setup and running simple — no virtualenv juggling.

```bash
# 1) Create & sync environment from pyproject.toml
uv sync

# 2) Run the CLI (from the project root)
DRY_RUN=1 uv run jira-ss-sync --log-level INFO

# Alternatively, run the module directly
DRY_RUN=1 uv run -m jira_ss_progress.cli --log-level INFO

# 3) When ready to write updates (remove DRY_RUN)
uv run jira-ss-sync --log-level INFO

# Add or upgrade deps later
uv add <package>           # adds to [project.dependencies]
uv lock --upgrade          # refreshes the lock file
```

Notes:
- The console script `jira-ss-sync` is exposed by `[project.scripts]` in `pyproject.toml`.
- `uv sync` will create a `.venv` and install the dependencies from `pyproject.toml`.
- Set your environment via `.env` or shell vars (see `.env.example`).

---

## Install (pip, alternative)

If you prefer `pip`:

```bash
pip install jira smartsheet-python-sdk python-dotenv
```

## Run (CLI, alternative)

```bash
# In the folder containing the package:
python -m jira_ss_progress.cli --log-level INFO
```

Or set `PYTHONPATH` to include this folder, then run the same command.

---

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
DRY_RUN=1                           # Preview; don’t write
PROTECT_EXISTING_NONZERO=1          # Keep non-zero Smartsheet value if Jira says 0
INCLUDE_SUBTASKS=0                  # 1 → Stories use done_subtasks/total_subtasks

# Optional
LOG_LEVEL=INFO
ENV_FILE=/path/to/another.env
```

> The **Smartsheet percent** column must be type **Percent** and uses **0.0–1.0** values.

---

## How it works

1. Load config from env (`jira_ss_progress.config.load_config`).
2. Connect to Jira & Smartsheet.
3. For each row with a Jira key in the Jira column:
   - If the key is an **Epic**: compute Epic progress via `jira_ss_progress.jira_utils.epic_progress_details`
     - Prefer **Story Points** (Done SP / Total SP) if any estimates exist.
     - Otherwise use **counts** (Done / Total).
     - Children are limited to **standard issue types** (subtasks excluded).
   - If the key is **not an Epic**: compute Story progress via `jira_ss_progress.jira_utils.story_progress_details`
     - Default **binary** (Done=100%, else 0%).
     - If `INCLUDE_SUBTASKS=1`: **done_subtasks / total_subtasks**.
   - Apply **protection** so 0% from Jira will not replace an existing non-zero Smartsheet value.
4. Write updates (unless `DRY_RUN=1`).

---

## Packaging (optional)

If you want to install as a package, add a `pyproject.toml` with a console entry,
or run directly via `python -m jira_ss_progress.cli`.

---

## Troubleshooting

- 401/403 from Jira → check tenant URL, email, API token.
- Smartsheet write errors → ensure output column is **Percent** and you write **0.0–1.0** floats.
- No progress for an Epic → verify children exist and are standard issue types; check Story Points field names.

