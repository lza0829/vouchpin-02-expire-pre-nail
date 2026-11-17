from __future__ import annotations
from typing import Any
from app.db import connect
from app.repositories import settings as settings_repo
from app.repositories import facts as fact_repo
from app.repositories import batches as batch_repo
from app.repositories import events as event_repo
from app.repositories import expire as expire_repo
from app.services import expire_service


def dashboard() -> dict[str, Any]:
    conn = connect()
    try:
        day = settings_repo.get(conn, "business_day")
        facts = fact_repo.list_facts(conn, day)
        open_n = sum(1 for f in facts if f["status"] == "open")
        sealed_n = sum(1 for f in facts if f["status"] == "sealed")
        total = round(sum(float(f["amount"]) for f in facts), 2)
        events = event_repo.list_events(conn, day)
        batches = batch_repo.list_batches(conn)
        sealed_today = fact_repo.day_is_sealed(conn, day)
        last_scan = expire_repo.latest_scan(conn)
        return {
            "business_day": day,
            "event_count": len(events),
            "fact_count": len(facts),
            "open_fact_count": open_n,
            "sealed_fact_count": sealed_n,
            "redeem_total_today": total,
            "batch_count": len(batches),
            "day_sealed": sealed_today,
            "voided_total": expire_repo.voided_count(conn),
            "pending_expire_count": len(expire_service.pending_expired(conn)),
            "last_scan_at": last_scan["ran_at"] if last_scan else None,
        }
    finally:
        conn.close()
