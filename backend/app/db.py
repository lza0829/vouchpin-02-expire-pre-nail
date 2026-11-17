from __future__ import annotations
import sqlite3
from app.config import DB_PATH

SCHEMA = '''
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS campaigns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  face_value REAL NOT NULL,
  min_spend REAL NOT NULL DEFAULT 0,
  expire_window_hours REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS coupon_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type TEXT NOT NULL,
  coupon_code TEXT NOT NULL,
  campaign_code TEXT NOT NULL,
  amount REAL NOT NULL DEFAULT 0,
  business_day TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS redeem_facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  coupon_code TEXT NOT NULL UNIQUE,
  campaign_code TEXT NOT NULL,
  amount REAL NOT NULL,
  business_day TEXT NOT NULL,
  event_id INTEGER NOT NULL,
  batch_id INTEGER,
  status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS redeem_batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  business_day TEXT NOT NULL,
  status TEXT NOT NULL,
  fact_count INTEGER NOT NULL DEFAULT 0,
  total_amount REAL NOT NULL DEFAULT 0,
  sealed_at TEXT,
  note TEXT NOT NULL DEFAULT '',
  scan_id INTEGER,
  scan_voided INTEGER NOT NULL DEFAULT 0,
  voided_at_seal INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS expire_scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ran_at TEXT NOT NULL,
  business_day TEXT NOT NULL,
  scanned_issues INTEGER NOT NULL DEFAULT 0,
  expired_count INTEGER NOT NULL DEFAULT 0,
  voided_count INTEGER NOT NULL DEFAULT 0,
  already_void INTEGER NOT NULL DEFAULT 0,
  redeemed_skip INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS coupon_voids (
  coupon_code TEXT PRIMARY KEY,
  campaign_code TEXT NOT NULL,
  issue_event_id INTEGER,
  void_event_id INTEGER NOT NULL,
  issued_at TEXT,
  expired_at TEXT,
  voided_at TEXT NOT NULL,
  scan_id INTEGER,
  source TEXT NOT NULL DEFAULT 'scan'
);
'''

# 旧库迁移：CREATE TABLE IF NOT EXISTS 不会补列，逐列 ALTER
_MIGRATIONS = [
    ("campaigns", "expire_window_hours",
     "ALTER TABLE campaigns ADD COLUMN expire_window_hours REAL NOT NULL DEFAULT 0"),
    ("redeem_batches", "scan_id",
     "ALTER TABLE redeem_batches ADD COLUMN scan_id INTEGER"),
    ("redeem_batches", "scan_voided",
     "ALTER TABLE redeem_batches ADD COLUMN scan_voided INTEGER NOT NULL DEFAULT 0"),
    ("redeem_batches", "voided_at_seal",
     "ALTER TABLE redeem_batches ADD COLUMN voided_at_seal INTEGER NOT NULL DEFAULT 0"),
]


def connect(immediate: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if immediate:
        conn.execute("BEGIN IMMEDIATE")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        for table, column, ddl in _MIGRATIONS:
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                conn.execute(ddl)
        conn.commit()
    finally:
        conn.close()
