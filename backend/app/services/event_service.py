from __future__ import annotations
from datetime import datetime
from typing import Any
from fastapi import HTTPException
from app.db import connect
from app.repositories import settings as settings_repo
from app.repositories import events as event_repo
from app.repositories import facts as fact_repo
from app.repositories import campaigns as camp_repo
from app.repositories import expire as expire_repo
from app.services import expire_service


def list_campaigns() -> list[dict[str, Any]]:
    conn = connect()
    try:
        return camp_repo.list_all(conn)
    finally:
        conn.close()


def list_events(business_day: str | None = None) -> list[dict[str, Any]]:
    conn = connect()
    try:
        day = business_day or settings_repo.get(conn, "business_day")
        return event_repo.list_events(conn, day)
    finally:
        conn.close()


def _check_redeem_expire_gate(conn, code: str) -> None:
    """过期闸（全局互斥·到期自动作废）：已作废或已过期的券码禁止核销。

    不依赖扫描是否已跑：作废标记直接拒；无标记但按发放时刻+过期窗已过期同样拒，
    杜绝「扫描显示已作废 / 已过期仍能核销进闸」。
    """
    voided = expire_repo.voided_map(conn)
    if code in voided:
        v = voided[code]
        raise HTTPException(
            409,
            f"券码 {code} 已作废（{v['source']} 作废于 {v['voided_at']}），禁止核销",
        )
    issue = expire_repo.issue_index(conn).get(code)
    if not issue:
        return  # 无发放事件，无过期依据，维持原放行
    windows = expire_service.window_map(conn)
    exp = expire_service.expired_at(issue, windows)
    if exp and datetime.now() > exp:
        raise HTTPException(
            409,
            f"券码 {code} 已过期（发放 {issue['occurred_at']}，过期 {exp.isoformat()}），"
            "禁止核销；请先运行过期扫描作废",
        )


def add_event(body: dict[str, Any]) -> dict[str, Any]:
    conn = connect(immediate=True)
    try:
        day = body.get("business_day") or settings_repo.get(conn, "business_day")
        et = body.get("event_type")
        if et not in {"issue", "redeem", "void"}:
            raise HTTPException(400, "event_type 须为 issue/redeem/void")
        code = (body.get("coupon_code") or "").strip()
        camp = (body.get("campaign_code") or "").strip()
        if not code or not camp:
            raise HTTPException(400, "coupon_code / campaign_code 必填")
        if et == "redeem" and fact_repo.day_is_sealed(conn, day):
            raise HTTPException(409, f"业务日 {day} 核销已钉扎，禁止再写入核销")
        if et == "redeem":
            _check_redeem_expire_gate(conn, code)
        amount = float(body.get("amount") or 0)
        if et == "redeem" and amount <= 0:
            # default face value from campaign
            camps = {c["code"]: c for c in camp_repo.list_all(conn)}
            if camp in camps:
                amount = float(camps[camp]["face_value"])
        occurred = body.get("occurred_at") or datetime.now().replace(microsecond=0).isoformat()
        if et == "void":
            # 手工作废与扫描作废同闸：已有核销事实的券不能作废
            if code in expire_repo.redeemed_events(conn):
                raise HTTPException(409, f"券码 {code} 已有核销事实，不能作废")
        eid = event_repo.insert_event(
            conn,
            event_type=et,
            coupon_code=code,
            campaign_code=camp,
            amount=amount,
            business_day=day,
            occurred_at=occurred,
            note=body.get("note") or "",
        )
        fact_id = None
        if et == "redeem":
            try:
                fact_id = fact_repo.insert_fact(
                    conn,
                    coupon_code=code,
                    campaign_code=camp,
                    amount=amount,
                    business_day=day,
                    event_id=eid,
                    status="open",
                )
            except Exception as e:
                raise HTTPException(409, f"核销事实写入失败（可能券码已核销）: {e}") from e
        if et == "void":
            # 事件湖与作废标记同步：手工 void 同样落 coupon_voids，核销闸即时生效
            issue = expire_repo.issue_index(conn).get(code)
            windows = expire_service.window_map(conn)
            exp = expire_service.expired_at(issue, windows) if issue else None
            expire_repo.insert_void(
                conn,
                coupon_code=code,
                campaign_code=camp,
                issue_event_id=int(issue["id"]) if issue else None,
                void_event_id=eid,
                issued_at=issue["occurred_at"] if issue else None,
                expired_at=exp.isoformat() if exp else None,
                voided_at=occurred,
                scan_id=None,
                source="manual",
            )
        conn.commit()
        return {"event_id": eid, "fact_id": fact_id, "business_day": day}
    finally:
        conn.close()
