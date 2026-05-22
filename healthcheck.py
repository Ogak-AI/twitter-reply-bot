#!/usr/bin/env python3
"""
healthcheck.py — Production health check script.
Run manually or hook into a monitoring cron job.

Usage:
  python healthcheck.py           → print status
  python healthcheck.py --json    → JSON output (for monitoring tools)
"""

import sys
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def check_health() -> dict:
    results = {}

    # 1. Database accessible and has recent activity
    try:
        import sqlite3
        db_path = "data/bot.db"
        if not Path(db_path).exists():
            results["database"] = {"ok": False, "msg": "DB file not found"}
        else:
            conn = sqlite3.connect(db_path)
            total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            recent_cutoff = (datetime.utcnow() - timedelta(hours=6)).isoformat()
            recent = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE status='posted' AND created_at > ?",
                (recent_cutoff,)
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE status='failed' AND created_at > ?",
                (recent_cutoff,)
            ).fetchone()[0]
            conn.close()
            results["database"] = {
                "ok": True,
                "total_posts": total,
                "posts_last_6h": recent,
                "failures_last_6h": failed
            }
    except Exception as e:
        results["database"] = {"ok": False, "msg": str(e)}

    # 2. Log file exists and has recent entries
    try:
        log_path = Path("logs/bot.log")
        if not log_path.exists():
            results["logs"] = {"ok": False, "msg": "Log file not found"}
        else:
            stat = log_path.stat()
            age_mins = (datetime.utcnow().timestamp() - stat.st_mtime) / 60
            # Log should have been written to in the last 10 minutes if bot is healthy
            results["logs"] = {
                "ok": age_mins < 10,
                "last_write_mins_ago": round(age_mins, 1),
                "size_kb": round(stat.st_size / 1024, 1)
            }
    except Exception as e:
        results["logs"] = {"ok": False, "msg": str(e)}

    # 3. Groq health check
    try:
        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        results["groq"] = {
            "ok": bool(groq_key),
            "msg": "GROQ_API_KEY set" if groq_key else "GROQ_API_KEY not set"
        }
    except Exception as e:
        results["groq"] = {"ok": False, "msg": str(e)}

    # 4. Buffer API reachable
    try:
        import requests
        r = requests.get("https://api.buffer.com", timeout=10)
        results["buffer_api"] = {"ok": r.status_code in (200, 400, 401), "status": r.status_code}
    except Exception as e:
        results["buffer_api"] = {"ok": False, "msg": str(e)}

    # Overall health
    critical = ["database", "logs"]
    results["healthy"] = all(results.get(k, {}).get("ok", False) for k in critical)
    results["checked_at"] = datetime.utcnow().isoformat() + "Z"
    return results


if __name__ == "__main__":
    health = check_health()

    if "--json" in sys.argv:
        print(json.dumps(health, indent=2))
    else:
        print("\n[Health Check]\n")
        for key, val in health.items():
            if key in ("healthy", "checked_at"):
                continue
            ok = val.get("ok", False)
            icon = "[OK]" if ok else "[FAIL]"
            details = {k: v for k, v in val.items() if k != "ok"}
            detail_str = "  |  " + "  ".join(f"{k}: {v}" for k, v in details.items()) if details else ""
            print(f"  {icon}  {key:<15}{detail_str}")

        print()
        overall = "HEALTHY" if health["healthy"] else "UNHEALTHY"
        print(f"  Overall: {overall}")
        print(f"  Checked: {health['checked_at']}\n")

    sys.exit(0 if health["healthy"] else 1)
