"""Export locally stored uncertain-route task events to CSV.
Run: python export_data.py
Optional: ROUTE_STUDY_DB=/path/to/route_study.sqlite python export_data.py
"""
import csv
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("ROUTE_STUDY_DB", "data/route_study_fixed_v4.sqlite"))
OUT_PATH = Path(os.environ.get("ROUTE_STUDY_EXPORT", "data/route_study_events.csv"))

if not DB_PATH.exists():
    raise SystemExit(f"No study database found at: {DB_PATH}")

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(DB_PATH) as con, OUT_PATH.open("w", newline="", encoding="utf-8") as f:
    cur = con.execute("SELECT * FROM events ORDER BY participant_id, trial, elapsed_seconds, wallclock_utc")
    writer = csv.writer(f)
    writer.writerow([x[0] for x in cur.description])
    writer.writerows(cur)
print(f"Exported {OUT_PATH}")
