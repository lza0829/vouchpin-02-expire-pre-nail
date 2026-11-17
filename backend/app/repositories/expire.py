from __future__ import annotations
import sqlite3
from typing import Any


def issue_index(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """每个券码的首次发放事件（occurred_at 最早者）。"""
    rows = conn.execute(
        "SELECT * FROM coupon_events WHERE event_type='issue' ORDER BY occurred_at, id"
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        out.setdefault(d["coupon_code"], d)
    return out


def redeemed_events(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """每个券码的首次核销事件。"""
    rows = conn.execute(
        "SELECT * FROM coupon_events WHERE event_type='redeem' ORDER BY occurred_at, id"
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        out.setdefault(d["coupon_code"], d)
    return out


def voided_map(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute("SELECT * FROM coupon_voids ORDER BY voided_at, coupon_code").fetchall()
    return {dict(r)["coupon_code"]: dict(r) for r in rows}


def list_voids(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM coupon_voids ORDER BY voided_at DESC, coupon_code").fetchall()
    return [dict(r) for r in rows]


def insert_void(conn: sqlite3.Connection, **fields: Any) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO coupon_voids(coupon_code, campaign_code, issue_event_id, void_event_id, issued_at, expired_at, voided_at, scan_id, source)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (
            fields["coupon_code"],
            fields["campaign_code"],
            fields.get("issue_event_id"),
            int(fields["void_event_id"]),
            fields.get("issued_at"),
            fields.get("expired_at"),
            fields["voided_at"],
            fields.get("scan_id"),
            fields.get("source") or "scan",
        ),
    )


def insert_scan(conn: sqlite3.Connection, **fields: Any) -> int:
    cur = conn.execute(
        "INSERT INTO expire_scans(ran_at, business_day, scanned_issues, expired_count, voided_count, already_void, redeemed_skip, note)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (
            fields["ran_at"],
            fields["business_day"],
            int(fields.get("scanned_issues") or 0),
            int(fields.get("expired_count") or 0),
            int(fields.get("voided_count") or 0),
            int(fields.get("already_void") or 0),
            int(fields.get("redeemed_skip") or 0),
            fields.get("note") or "",
        ),
    )
    return int(cur.lastrowid)


def update_scan_counts(conn: sqlite3.Connection, scan_id: int, **counts: int) -> None:
    conn.execute(
        "UPDATE expire_scans SET scanned_issues=?, expired_count=?, voided_count=?, already_void=?, redeemed_skip=? WHERE id=?",
        (
            int(counts.get("scanned_issues") or 0),
            int(counts.get("expired_count") or 0),
            int(counts.get("voided_count") or 0),
            int(counts.get("already_void") or 0),
            int(counts.get("redeemed_skip") or 0),
            int(scan_id),
        ),
    )


def list_scans(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM expire_scans ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def latest_scan(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM expire_scans ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def voided_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) c FROM coupon_voids").fetchone()["c"])
