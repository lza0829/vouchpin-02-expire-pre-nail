from __future__ import annotations
from datetime import date, datetime, timedelta
from app.db import connect, init_db


def seed_if_empty() -> None:
    init_db()
    conn = connect()
    try:
        n = conn.execute("SELECT COUNT(*) c FROM campaigns").fetchone()["c"]
        if n:
            return
        today = date.today().isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES('business_day', ?)",
            (today,),
        )
        # expire_window_hours：0 = 无过期窗
        campaigns = [
            ("NEW10", "新人立减10", 10.0, 30.0, 24.0),
            ("VIP20", "会员满减20", 20.0, 100.0, 48.0),
            ("TEA5", "茶饮立减5", 5.0, 15.0, 0.0),
        ]
        for code, title, face, mn, win in campaigns:
            conn.execute(
                "INSERT INTO campaigns(code, title, face_value, min_spend, expire_window_hours) VALUES(?,?,?,?,?)",
                (code, title, face, mn, win),
            )
        # issue + redeem events for today and yesterday
        yday = (date.today() - timedelta(days=1)).isoformat()
        old = (date.today() - timedelta(days=3)).isoformat()
        rows = [
            ("issue", "C-1001", "NEW10", 0, today, f"{today}T09:00:00"),
            ("issue", "C-1002", "VIP20", 0, today, f"{today}T09:10:00"),
            ("issue", "C-1003", "TEA5", 0, today, f"{today}T09:20:00"),
            ("redeem", "C-1001", "NEW10", 10, today, f"{today}T12:00:00"),
            ("redeem", "C-1002", "VIP20", 20, today, f"{today}T12:30:00"),
            ("issue", "C-0901", "NEW10", 0, yday, f"{yday}T10:00:00"),
            ("redeem", "C-0901", "NEW10", 10, yday, f"{yday}T18:00:00"),
            # 未核过期：发放于 3 天前、至今无核销，等待过期扫描作废
            ("issue", "C-0801", "NEW10", 0, old, f"{old}T09:00:00"),
            ("issue", "C-0802", "VIP20", 0, old, f"{old}T09:30:00"),
            # 无过期窗活动：发放再久也不作废
            ("issue", "C-0803", "TEA5", 0, old, f"{old}T10:00:00"),
        ]
        for et, cc, camp, amt, day, at in rows:
            cur = conn.execute(
                "INSERT INTO coupon_events(event_type, coupon_code, campaign_code, amount, business_day, occurred_at) VALUES(?,?,?,?,?,?)",
                (et, cc, camp, amt, day, at),
            )
            if et == "redeem":
                conn.execute(
                    "INSERT INTO redeem_facts(coupon_code, campaign_code, amount, business_day, event_id, status) VALUES(?,?,?,?,?, 'open')",
                    (cc, camp, amt, day, cur.lastrowid),
                )
        conn.commit()
    finally:
        conn.close()
