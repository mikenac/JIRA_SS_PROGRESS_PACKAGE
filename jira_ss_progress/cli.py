"""
Command-line entry point for the Jira → Smartsheet sync.
"""
from __future__ import annotations
import logging
import argparse

from jira_ss_progress.config import load_config
from jira_ss_progress.sync import run_sync

def main():
    parser = argparse.ArgumentParser(description="Sync Jira progress/status & dates with Smartsheet")
    parser.add_argument("--log-level", default=None, help="Override LOG_LEVEL (e.g., DEBUG)")
    args = parser.parse_args()

    cfg = load_config()
    level = (args.log_level or cfg.log_level).upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    res = run_sync(cfg)

    if cfg.dry_run:
        w = {"issue": 18, "typ": 7, "metric": 9, "comp": 10, "tot": 10,
             "exist": 10, "new": 10, "final": 10, "status_e": 12, "status_n": 12, "status_f": 12,
             "s_old": 12, "s_new": 12, "s_fin": 12, "e_old": 12, "e_new": 12, "e_fin": 12, "prot": 9}
        print("\nJira rows (existing → new → final) with status, dates & protection:")
        print(f"{'Issue':<{w['issue']}} {'Type':<{w['typ']}} {'Metric':<{w['metric']}} "
              f"{'Done':>{w['comp']}} {'Total':>{w['tot']}} {'Existing':>{w['exist']}} "
              f"{'New':>{w['new']}} {'Final':>{w['final']}} "
              f"{'Stat(Old)':<{w['status_e']}} {'Stat(New)':<{w['status_n']}} {'Stat(Final)':<{w['status_f']}} "
              f"{'Start(Old)':<{w['s_old']}} {'Start(New)':<{w['s_new']}} {'Start(Final)':<{w['s_fin']}} "
              f"{'End(Old)':<{w['e_old']}} {'End(New)':<{w['e_new']}} {'End(Final)':<{w['e_fin']}} "
              f"{'Protected':>{w['prot']}}")
        print("-" * (sum(w.values()) + 13))
        for r in sorted(res.preview, key=lambda x: (x.type, x.issue_key)):
            comp = f"{r.completed:.2f}" if r.metric == "points" else f"{int(r.completed)}"
            tot  = f"{r.total:.2f}" if r.metric == "points" else f"{int(r.total)}"
            print(f"{r.issue_key:<{w['issue']}} {r.type:<{w['typ']}} {r.metric:<{w['metric']}} "
                  f"{comp:>{w['comp']}} {tot:>{w['tot']}} {r.existing_pct:>{w['exist']}.2f}% "
                  f"{r.new_pct:>{w['new']}.2f}% {r.final_pct:>{w['final']}.2f}% "
                  f"{(r.existing_status or '-'):<{w['status_e']}} {(r.new_status or '-'):<{w['status_n']}} {(r.final_status or '-'):<{w['status_f']}} "
                  f"{(r.start_old or '-'):<{w['s_old']}} {(r.start_new or '-'):<{w['s_new']}} {(r.start_final or '-'):<{w['s_fin']}} "
                  f"{(r.end_old or '-'):<{w['e_old']}} {(r.end_new or '-'):<{w['e_new']}} {(r.end_final or '-'):<{w['e_fin']}} "
                  f"{str(r.protected):>{w['prot']}}")
    else:
        print(f"Updated {res.updated_rows} Smartsheet rows (+ pushed any Jira date changes).")

if __name__ == "__main__":
    main()
