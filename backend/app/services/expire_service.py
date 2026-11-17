from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any
from app.db import connect
from app.repositories import settings as settings_repo
from app.repositories import campaigns as camp_repo
from app.repositories import events as event_repo
from app.repositories import expire as expire_repo

# 全局互斥策略（只此一种）：到期自动作废。
# 发放后超过 expire_window_hours 且仍无核销的券码：
#   过期扫描写 void 事件入湖 + coupon_voids 作废标记 → 核销入口拒核 → 钉扎 open 集合排除。


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def window_map(conn) -> dict[str, float]:
    return {c["code"]: float(c["expire_window_hours"] or 0) for c in camp_repo.list_all(conn)}


def expired_at(issue: dict[str, Any], windows: dict[str, float]) -> datetime | None:
    """券的过期时刻；活动无过期窗（<=0）时为 None。"""
    w = windows.get(issue["campaign_code"], 0.0)
    if w <= 0:
        return None
    return _parse(issue["occurred_at"]) + timedelta(hours=w)


def run_scan(conn, business_day: str, note: str = "") -> dict[str, Any]:
    """过期扫描（改写闸，非只读报表）：过期未核券写 void 事件 + 作废标记，结果落库。

    调用方持有连接与事务（seal 会在同一事务内先跑扫描再钉扎）。
    """
    now = _now()
    windows = window_map(conn)
    issues = expire_repo.issue_index(conn)
    redeemed = expire_repo.redeemed_events(conn)
    voided = expire_repo.voided_map(conn)

    scan_id = expire_repo.insert_scan(conn, ran_at=now.isoformat(), business_day=business_day, note=note)
    counts = {"scanned_issues": 0, "expired_count": 0, "voided_count": 0, "already_void": 0, "redeemed_skip": 0}
    items: list[dict[str, Any]] = []
    for code, issue in issues.items():
        exp = expired_at(issue, windows)
        if exp is None:
            continue  # 活动无过期窗
        counts["scanned_issues"] += 1
        if now <= exp:
            continue  # 未超过过期窗
        counts["expired_count"] += 1
        if code in redeemed:
            counts["redeemed_skip"] += 1
            continue  # 已核销，不作废
        if code in voided:
            counts["already_void"] += 1
            continue  # 已作废，幂等跳过
        eid = event_repo.insert_event(
            conn,
            event_type="void",
            coupon_code=code,
            campaign_code=issue["campaign_code"],
            amount=0,
            business_day=business_day,
            occurred_at=now.isoformat(),
            note=f"过期自动作废 scan#{scan_id}",
        )
        expire_repo.insert_void(
            conn,
            coupon_code=code,
            campaign_code=issue["campaign_code"],
            issue_event_id=int(issue["id"]),
            void_event_id=eid,
            issued_at=issue["occurred_at"],
            expired_at=exp.isoformat(),
            voided_at=now.isoformat(),
            scan_id=scan_id,
            source="scan",
        )
        counts["voided_count"] += 1
        items.append(
            {
                "coupon_code": code,
                "campaign_code": issue["campaign_code"],
                "issued_at": issue["occurred_at"],
                "expired_at": exp.isoformat(),
                "void_event_id": eid,
            }
        )
    expire_repo.update_scan_counts(conn, scan_id, **counts)
    return {"scan_id": scan_id, "ran_at": now.isoformat(), "business_day": business_day, **counts, "items": items}


def scan_now(body: dict[str, Any]) -> dict[str, Any]:
    conn = connect(immediate=True)
    try:
        day = settings_repo.get(conn, "business_day")
        result = run_scan(conn, business_day=day, note=(body.get("note") or "manual"))
        conn.commit()
        return result
    finally:
        conn.close()


def list_scans() -> list[dict[str, Any]]:
    conn = connect()
    try:
        return expire_repo.list_scans(conn)
    finally:
        conn.close()


def list_voids() -> list[dict[str, Any]]:
    conn = connect()
    try:
        return expire_repo.list_voids(conn)
    finally:
        conn.close()


def pending_expired(conn) -> list[dict[str, Any]]:
    """已过期、未核销、尚未作废的券（提示：钉扎前须跑扫描）。"""
    now = _now()
    windows = window_map(conn)
    redeemed = expire_repo.redeemed_events(conn)
    voided = expire_repo.voided_map(conn)
    out: list[dict[str, Any]] = []
    for code, issue in expire_repo.issue_index(conn).items():
        exp = expired_at(issue, windows)
        if exp is None or now <= exp:
            continue
        if code in redeemed or code in voided:
            continue
        out.append(
            {
                "coupon_code": code,
                "campaign_code": issue["campaign_code"],
                "issued_at": issue["occurred_at"],
                "expired_at": exp.isoformat(),
            }
        )
    return out


def reconcile() -> dict[str, Any]:
    """核对（两场景 + 防撕裂校验），全部应清零：

    1. 未核过期核对：过期未核但未作废 → 扫描漏作废（须跑扫描清零）。
    2. 过期后核销核对：核销时刻晚于过期时刻 → 核销闸被突破。
    3. 作废入闸核对：已作废券码仍出现在核销事实（open/sealed）→ 扫描与钉扎集合撕裂。
    """
    conn = connect()
    try:
        windows = window_map(conn)
        issues = expire_repo.issue_index(conn)
        redeemed = expire_repo.redeemed_events(conn)
        voided = expire_repo.voided_map(conn)

        pending = pending_expired(conn)

        late: list[dict[str, Any]] = []
        for code, red in redeemed.items():
            issue = issues.get(code)
            if not issue:
                continue
            exp = expired_at(issue, windows)
            if exp and _parse(red["occurred_at"]) > exp:
                late.append(
                    {
                        "coupon_code": code,
                        "campaign_code": red["campaign_code"],
                        "redeemed_at": red["occurred_at"],
                        "expired_at": exp.isoformat(),
                        "voided": code in voided,
                    }
                )

        breached: list[dict[str, Any]] = []
        if voided:
            marks = ",".join("?" for _ in voided)
            rows = conn.execute(
                f"SELECT id, coupon_code, campaign_code, business_day, status, batch_id FROM redeem_facts"
                f" WHERE coupon_code IN ({marks}) ORDER BY id",
                tuple(voided.keys()),
            ).fetchall()
            for r in rows:
                d = dict(r)
                d["voided_at"] = voided[d["coupon_code"]]["voided_at"]
                breached.append(d)

        checks = [
            {
                "key": "unredeemed_expired",
                "title": "未核过期核对",
                "rule": "过期未核券必须已被扫描作废",
                "ok": not pending,
                "count": len(pending),
                "items": pending,
            },
            {
                "key": "redeemed_after_expiry",
                "title": "过期后核销核对",
                "rule": "核销时刻不得晚于过期时刻",
                "ok": not late,
                "count": len(late),
                "items": late,
            },
            {
                "key": "voided_in_facts",
                "title": "作废入闸核对",
                "rule": "已作废券码不得出现在核销事实（open/sealed）",
                "ok": not breached,
                "count": len(breached),
                "items": breached,
            },
        ]
        return {
            "generated_at": _now().isoformat(),
            "ok": all(c["ok"] for c in checks),
            "checks": checks,
        }
    finally:
        conn.close()
