from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from pulsedesk.config import ARTIFACTS, HORIZON, TRAIN_FRAC
from pulsedesk.db import connect, init_db
from pulsedesk.features import add_features, load_observations
from pulsedesk.models import load_models, predict, seasonal_naive, train_models


def _cutoff(frame: pd.DataFrame) -> pd.Timestamp:
    days = sorted(frame["day"].unique())
    idx = int(len(days) * TRAIN_FRAC)
    return pd.Timestamp(days[idx])


def train() -> None:
    init_db()
    raw = load_observations()
    feat = add_features(raw).dropna(subset=["lag_1", "lag_7", "roll_7"])
    cut = _cutoff(feat)
    train_df = feat[feat["day"] < cut]
    valid = feat[feat["day"] >= cut]
    models = train_models(train_df)
    scored = predict(models, valid)
    mae_m = float(np.mean(np.abs(scored["p50"] - scored["units"])))
    base = []
    for row in scored.itertuples(index=False):
        hist = raw[(raw.store_id == row.store_id) & (raw.sku_id == row.sku_id) & (raw.day < row.day)]
        base.append(seasonal_naive(hist, row.day))
    scored["baseline"] = base
    mae_b = float(np.mean(np.abs(scored["baseline"] - scored["units"])))
    mape = float(np.mean(np.abs(scored["p50"] - scored["units"]) / np.clip(scored["units"], 1, None)))
    cover = float(((scored["units"] >= scored["p10"]) & (scored["units"] <= scored["p90"])).mean())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with connect() as con:
        con.execute(
            "INSERT INTO eval_runs (created_at, n_points, mae_model, mae_baseline, mape_model, coverage_80) VALUES (?,?,?,?,?,?)",
            (now, int(len(scored)), mae_m, mae_b, mape, cover),
        )
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "eval.json").write_text(
        json.dumps(
            {
                "cutoff": str(cut.date()),
                "n_holdout": int(len(scored)),
                "mae_model": mae_m,
                "mae_baseline": mae_b,
                "mape_model": mape,
                "coverage_p10_p90": cover,
                "beats_baseline": mae_m <= mae_b,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"holdout n={len(scored)} MAE model={mae_m:.2f} baseline={mae_b:.2f} "
        f"MAPE={mape:.3f} cover[p10,p90]={cover:.2f}"
    )
    write_forward_forecast(raw, models, asof=cut)


def write_forward_forecast(raw: pd.DataFrame, models, asof: pd.Timestamp) -> None:
    """Recursive 14-day forecast from the last observed day per series."""
    from pulsedesk.config import HORIZON
    from pulsedesk.features import FEATURE_COLS, add_features

    asof_s = str(pd.Timestamp(raw["day"].max()).date())
    rows = []
    recs = []
    for (store_id, sku_id), grp in raw.groupby(["store_id", "sku_id"]):
        hist = grp.sort_values("day").copy()
        lead = int(hist["lead_days"].iloc[0])
        on_hand = float(hist["on_hand"].iloc[-1])
        for step in range(1, HORIZON + 1):
            nxt = hist["day"].max() + pd.Timedelta(days=1)
            extra = hist.iloc[-1:].copy()
            extra["day"] = nxt
            extra["units"] = np.nan
            extra["promo"] = 0
            work = add_features(pd.concat([hist, extra], ignore_index=True))
            last = work.iloc[[-1]].copy()
            last[FEATURE_COLS] = last[FEATURE_COLS].fillna(0)
            pred = predict(models, last).iloc[0]
            p10, p50, p90 = float(pred.p10), float(pred.p50), float(pred.p90)
            base = seasonal_naive(hist, nxt)
            rows.append((asof_s, int(store_id), int(sku_id), str(nxt.date()), p10, p50, p90, base))
            extra.loc[:, "units"] = p50
            hist = pd.concat([hist, extra], ignore_index=True)
        need50 = sum(r[5] for r in rows[-HORIZON:])
        need90 = sum(r[6] for r in rows[-HORIZON:])
        suggested = max(0, int(round(need90 - on_hand)))
        recs.append(
            (
                asof_s,
                int(store_id),
                int(sku_id),
                HORIZON,
                on_hand,
                need50,
                need90,
                suggested,
                f"{HORIZON}d p90 cover minus on-hand; lead {lead}d",
            )
        )
    with connect() as con:
        con.execute("DELETE FROM forecasts WHERE asof = ?", (asof_s,))
        con.execute("DELETE FROM recommendations WHERE asof = ?", (asof_s,))
        con.executemany(
            "INSERT INTO forecasts VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        con.executemany(
            "INSERT INTO recommendations (asof, store_id, sku_id, cover_days, on_hand, need_p50, need_p90, suggested_qty, reason) VALUES (?,?,?,?,?,?,?,?,?)",
            recs,
        )
    print(f"wrote {len(rows)} forecast rows and {len(recs)} order recs asof={asof_s}")
