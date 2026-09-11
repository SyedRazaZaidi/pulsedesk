from __future__ import annotations

import pandas as pd

from pulsedesk.db import connect


def load_observations() -> pd.DataFrame:
    with connect() as con:
        frame = pd.read_sql_query(
            """
            SELECT o.store_id, o.sku_id, o.day, o.units, o.promo, o.on_hand,
                   s.sku, s.name, s.category, s.lead_days, st.name AS store
            FROM observations o
            JOIN skus s ON s.id = o.sku_id
            JOIN stores st ON st.id = o.store_id
            ORDER BY o.store_id, o.sku_id, o.day
            """,
            con,
        )
    frame["day"] = pd.to_datetime(frame["day"])
    return frame


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values(["store_id", "sku_id", "day"]).copy()
    g = out.groupby(["store_id", "sku_id"], group_keys=False)
    out["lag_1"] = g["units"].shift(1)
    out["lag_7"] = g["units"].shift(7)
    out["lag_14"] = g["units"].shift(14)
    out["roll_7"] = g["units"].shift(1).rolling(7, min_periods=3).mean()
    out["roll_28"] = g["units"].shift(1).rolling(28, min_periods=7).mean()
    out["dow"] = out["day"].dt.weekday
    out["week"] = out["day"].dt.isocalendar().week.astype(int)
    out["month"] = out["day"].dt.month
    out["promo_lag"] = g["promo"].shift(1).fillna(0)
    return out


FEATURE_COLS = [
    "lag_1",
    "lag_7",
    "lag_14",
    "roll_7",
    "roll_28",
    "dow",
    "week",
    "month",
    "promo",
    "promo_lag",
    "store_id",
    "sku_id",
]
