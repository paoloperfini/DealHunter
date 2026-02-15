from __future__ import annotations
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  target_name TEXT NOT NULL,
  source TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  total_eur REAL,
  price_eur REAL,
  shipping_eur REAL,
  condition TEXT,
  seller TEXT,
  location TEXT
);
CREATE INDEX IF NOT EXISTS idx_offers_target_ts ON offers(target_name, ts_utc);
CREATE INDEX IF NOT EXISTS idx_offers_url_ts ON offers(url, ts_utc);
"""

@dataclass
class Stats:
    count: int
    min_30d: Optional[float]
    avg_30d: Optional[float]
    min_drop_window: Optional[float]  # e.g. min in last 48h

def connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(SCHEMA)
    return conn

def insert_offer(conn: sqlite3.Connection, *, ts_utc: datetime, target_name: str, source: str, title: str, url: str,
                 total_eur: Optional[float], price_eur: Optional[float], shipping_eur: Optional[float],
                 condition: Optional[str], seller: Optional[str], location: Optional[str]) -> None:
    conn.execute(
        """INSERT INTO offers(ts_utc,target_name,source,title,url,total_eur,price_eur,shipping_eur,condition,seller,location)
             VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (ts_utc.isoformat(), target_name, source, title, url, total_eur, price_eur, shipping_eur, condition, seller, location)
    )

def compute_stats(conn: sqlite3.Connection, *, target_name: str, window_days: int = 30, drop_hours: int = 48) -> Stats:
    now = datetime.utcnow()
    t0 = now - timedelta(days=window_days)
    t1 = now - timedelta(hours=drop_hours)

    # Only consider rows with a real total_eur
    cur = conn.execute(
        """SELECT COUNT(*), MIN(total_eur), AVG(total_eur)
             FROM offers
             WHERE target_name=? AND ts_utc>=? AND total_eur IS NOT NULL""",
        (target_name, t0.isoformat())
    )
    count, min_30d, avg_30d = cur.fetchone()

    cur = conn.execute(
        """SELECT MIN(total_eur)
             FROM offers
             WHERE target_name=? AND ts_utc>=? AND total_eur IS NOT NULL""",
        (target_name, t1.isoformat())
    )
    (min_drop_window,) = cur.fetchone()
    return Stats(count=int(count or 0),
                 min_30d=float(min_30d) if min_30d is not None else None,
                 avg_30d=float(avg_30d) if avg_30d is not None else None,
                 min_drop_window=float(min_drop_window) if min_drop_window is not None else None)

def best_new_reference(conn: sqlite3.Connection, *, target_name: str, window_days: int = 7) -> Optional[float]:
    """Reference price for used scoring: minimum 'new' seen recently.
    We approximate by excluding Subito sources (ingest/imap) and condition containing 'used'.
    """
    now = datetime.utcnow()
    t0 = now - timedelta(days=window_days)
    cur = conn.execute(
        """SELECT MIN(total_eur)
             FROM offers
             WHERE target_name=? AND ts_utc>=? AND total_eur IS NOT NULL
               AND source NOT IN ('subito_ingest','subito_imap')""",
        (target_name, t0.isoformat())
    )
    (m,) = cur.fetchone()
    return float(m) if m is not None else None
