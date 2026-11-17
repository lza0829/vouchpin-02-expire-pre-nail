from __future__ import annotations
from datetime import datetime
from typing import Any
from fastapi import HTTPException
from app.db import connect
from app.repositories import settings as settings_repo
from app.repositories import facts as fact_repo
from app.repositories import batches as batch_repo
from app.repositories import expire as expire_repo
from app.services import expire_service


def list_facts(business_day: str | None = None) -> list[dict[str, Any]]:
    conn = connect()
    try:
        day = business_day or settings_repo.get(conn, "business_day")
        return fact_repo.list_facts(conn, day)
    finally:
        conn.close()


def preview(business_day: str | None = None) -> dict[str, Any]:
    conn = connect()
    try:
        day = business_day or settings_repo.get(conn, "business_day")
        opens = fact_repo.open_facts_for_day(conn, day)  # 已排除作废券码
        total = round(sum(float(f["amount"]) for f in opens), 2)
        pending = expire_service.pending_expired(conn)
        return {
            "business_day": day,
            "open_count": len(opens),
            "open_total": total,
            "already_sealed": fact_repo.day_is_sealed(conn, day),
            "pending_expire_count": len(pending),
            "pending_expire": pending,
            "voided_total": expire_repo.voided_count(conn),
            "facts": opens,
        }
    finally:
        conn.close()


def seal(body: dict[str, Any]) -> dict[str, Any]:
    conn = connect(immediate=True)
    try:
        day = body.get("business_day") or settings_repo.get(conn, "business_day")
        if fact_repo.day_is_sealed(conn, day):
            raise HTTPException(409, f"业务日 {day} 已有 sealed 钉扎批")
        # 钉扎前同一事务内先跑过期扫描：过期未核券即刻作废，open 集合随之排除
        scan = expire_service.run_scan(conn, business_day=day, note="pre-seal")
        opens = fact_repo.open_facts_for_day(conn, day)
        if not opens:
            raise HTTPException(400, "无可钉扎的 open 核销事实")
        total = round(sum(float(f["amount"]) for f in opens), 2)
        voided_total = expire_repo.voided_count(conn)
        bid = batch_repo.create_batch(
            conn,
            business_day=day,
            status="sealed",
            fact_count=len(opens),
            total_amount=total,
            sealed_at=datetime.now().replace(microsecond=0).isoformat(),
            note=body.get("note") or "",
            scan_id=scan["scan_id"],
            scan_voided=scan["voided_count"],
            voided_at_seal=voided_total,
        )
        fact_repo.mark_batched(conn, [int(f["id"]) for f in opens], bid)
        conn.commit()
        return {
            "batch_id": bid,
            "business_day": day,
            "fact_count": len(opens),
            "total_amount": total,
            "status": "sealed",
            "scan_id": scan["scan_id"],
            "scan_voided": scan["voided_count"],
            "voided_at_seal": voided_total,
        }
    finally:
        conn.close()


def list_batches() -> list[dict[str, Any]]:
    conn = connect()
    try:
        return batch_repo.list_batches(conn)
    finally:
        conn.close()
