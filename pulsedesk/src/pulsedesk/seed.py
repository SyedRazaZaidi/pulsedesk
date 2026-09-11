from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from pulsedesk.config import SEED
from pulsedesk.db import connect, init_db

STORES = [
    (1, "Harbor Market", "Karachi"),
    (2, "Midtown Mart", "Karachi"),
]

SKUS = [
    (1, "MLK-1L", "Fresh milk 1L", "Dairy", 180, 2),
    (2, "BRD-WHT", "White bread", "Bakery", 90, 1),
    (3, "EGG-12", "Eggs dozen", "Dairy", 320, 2),
    (4, "RIC-5K", "Basmati rice 5kg", "Staples", 1450, 5),
    (5, "OIL-1L", "Cooking oil 1L", "Staples", 520, 4),
    (6, "DET-1K", "Detergent 1kg", "Home", 410, 5),
    (7, "SOD-330", "Cola 330ml", "Bev", 70, 3),
    (8, "YOG-400", "Yogurt 400g", "Dairy", 140, 2),
    (9, "CHK-1K", "Chicken 1kg", "Fresh", 620, 1),
    (10, "APL-1K", "Apples 1kg", "Fresh", 280, 2),
    (11, "DIA-M", "Diapers M", "Baby", 890, 6),
    (12, "COF-200", "Coffee 200g", "Bev", 750, 5),
]


def seed(days: int = 420) -> None:
    init_db()
    rng = np.random.default_rng(SEED)
    start = date(2024, 8, 1)
    with connect() as con:
        con.execute("DELETE FROM decisions")
        con.execute("DELETE FROM recommendations")
        con.execute("DELETE FROM forecasts")
        con.execute("DELETE FROM observations")
        con.execute("DELETE FROM skus")
        con.execute("DELETE FROM stores")
        con.executemany("INSERT INTO stores VALUES (?,?,?)", STORES)
        con.executemany("INSERT INTO skus VALUES (?,?,?,?,?,?)", SKUS)
        rows = []
        for store_id, _, _ in STORES:
            store_scale = 1.15 if store_id == 1 else 0.85
            for sku_id, sku, _, cat, _, _ in SKUS:
                base = {
                    "Dairy": 46,
                    "Bakery": 38,
                    "Staples": 12,
                    "Home": 9,
                    "Bev": 55,
                    "Fresh": 22,
                    "Baby": 8,
                }[cat]
                on_hand = float(base * 4)
                for d in range(days):
                    day = start + timedelta(days=d)
                    dow = day.weekday()
                    week = 1.25 if dow >= 5 else 1.0
                    promo = int(rng.random() < 0.08)
                    lift = 1.35 if promo else 1.0
                    noise = rng.lognormal(0, 0.18)
                    units = max(0.0, base * store_scale * week * lift * noise)
                    if cat == "Fresh" and dow == 0:
                        units *= 0.7
                    on_hand = max(0.0, on_hand - units + rng.integers(0, 8))
                    if on_hand < units * 2:
                        on_hand += units * 3
                    rows.append(
                        (store_id, sku_id, day.isoformat(), round(units, 2), promo, round(on_hand, 2))
                    )
        con.executemany(
            "INSERT INTO observations VALUES (?,?,?,?,?,?)",
            rows,
        )
    print(f"seeded {len(rows)} daily rows -> {len(SKUS)} SKUs x {len(STORES)} stores")
