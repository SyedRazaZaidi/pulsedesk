from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from pulsedesk.config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS stores (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS skus (
  id INTEGER PRIMARY KEY,
  sku TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  unit_cost REAL NOT NULL,
  lead_days INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
  store_id INTEGER NOT NULL,
  sku_id INTEGER NOT NULL,
  day TEXT NOT NULL,
  units REAL NOT NULL,
  promo INTEGER NOT NULL,
  on_hand REAL NOT NULL,
  PRIMARY KEY (store_id, sku_id, day)
);
CREATE TABLE IF NOT EXISTS forecasts (
  asof TEXT NOT NULL,
  store_id INTEGER NOT NULL,
  sku_id INTEGER NOT NULL,
  day TEXT NOT NULL,
  p10 REAL NOT NULL,
  p50 REAL NOT NULL,
  p90 REAL NOT NULL,
  baseline REAL NOT NULL,
  PRIMARY KEY (asof, store_id, sku_id, day)
);
CREATE TABLE IF NOT EXISTS recommendations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asof TEXT NOT NULL,
  store_id INTEGER NOT NULL,
  sku_id INTEGER NOT NULL,
  cover_days INTEGER NOT NULL,
  on_hand REAL NOT NULL,
  need_p50 REAL NOT NULL,
  need_p90 REAL NOT NULL,
  suggested_qty INTEGER NOT NULL,
  reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rec_id INTEGER NOT NULL,
  action TEXT NOT NULL,
  qty INTEGER,
  note TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eval_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  n_points INTEGER NOT NULL,
  mae_model REAL NOT NULL,
  mae_baseline REAL NOT NULL,
  mape_model REAL NOT NULL,
  coverage_80 REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory_moves (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  store_id INTEGER NOT NULL,
  sku_id INTEGER NOT NULL,
  qty REAL NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  detail TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with connect() as con:
        con.executescript(SCHEMA)
