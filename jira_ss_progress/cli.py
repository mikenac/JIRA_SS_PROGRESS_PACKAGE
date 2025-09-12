"""
Command-line entry point for the Jira → Smartsheet sync.
"""
from __future__ import annotations
import logging
import argparse

from .config import load_config
from .sync import run_sync

def main():
    # Minimal CLI: mostly to allow overriding log level at runtime
    parser = argparse.ArgumentParser(description="Sync Jira progress into Smartsheet")
    parser.add_argument("--log-level", default=None, help="Override LOG_LEVEL (e.g., DEBUG)")
    args = parser.parse_args()

    cfg = load_config()
    level = (args.log_level or cfg.log_level).upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    res = run_sync(cfg)

    # Pretty-print DRY RUN table (or a short summary if not dry-run)
    if cfg.dry_run:
        w = {"issue": 18, "typ": 7, "metric": 9, "comp": 10, "tot": 10, "exist": 10, "new": 10, "final": 10, "prot": 9}
        print("\nJira rows (existing → new → final) with protection:")
        print(f"{'Issue':<{w['issue']}} {'Type':<{w['typ']}} {'Metric':<{w['metric']}} "
              f"{'Done':>{w['comp']}} {'Total':>{w['tot']}} {'Existing':>{w['exist']}} "
              f"{'New':>{w['new']}} {'Final':>{w['final']}} {'Protected':>{w['prot']}}")
        print("-" * (sum(w.values()) + 7))
        for r in sorted(res.preview, key=lambda x: (x.type, x.issue_key)):
            comp = f"{r.completed:.2f}" if r.metric == "points" else f"{int(r.completed)}"
            tot  = f"{r.total:.2f}" if r.metric == "points" else f"{int(r.total)}"
            print(f"{r.issue_key:<{w['issue']}} {r.type:<{w['typ']}} {r.metric:<{w['metric']}} "
                  f"{comp:>{w['comp']}} {tot:>{w['tot']}} {r.existing_pct:>{w['exist']}.2f}% "
                  f"{r.new_pct:>{w['new']}.2f}% {r.final_pct:>{w['final']}.2f}% {str(r.protected):>{w['prot']}}")
    else:
        print(f"Updated {res.updated_rows} rows.")

if __name__ == "__main__":
    main()
