from __future__ import annotations

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

from pulsedesk.config import ARTIFACTS, SEED
from pulsedesk.features import FEATURE_COLS


def _fit_quantile(x: pd.DataFrame, y: pd.Series, alpha: float) -> lgb.Booster:
    data = lgb.Dataset(x, label=y)
    params = {
        "objective": "quantile",
        "alpha": alpha,
        "learning_rate": 0.05,
        "num_leaves": 24,
        "min_data_in_leaf": 20,
        "verbosity": -1,
        "seed": SEED,
    }
    return lgb.train(params, data, num_boost_round=180)


def train_models(train: pd.DataFrame) -> dict[str, lgb.Booster]:
    x = train[FEATURE_COLS]
    y = train["units"]
    models = {
        "p10": _fit_quantile(x, y, 0.10),
        "p50": _fit_quantile(x, y, 0.50),
        "p90": _fit_quantile(x, y, 0.90),
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(models, ARTIFACTS / "quantiles.joblib")
    return models


def load_models() -> dict[str, lgb.Booster]:
    path = ARTIFACTS / "quantiles.joblib"
    if not path.exists():
        raise FileNotFoundError("Run `pulsedesk train` first.")
    return joblib.load(path)


def predict(models: dict[str, lgb.Booster], frame: pd.DataFrame) -> pd.DataFrame:
    x = frame[FEATURE_COLS].fillna(0)
    out = frame.copy()
    for name, booster in models.items():
        out[name] = np.clip(booster.predict(x), 0, None)
    return out


def seasonal_naive(history: pd.DataFrame, when: pd.Timestamp) -> float:
    """Same weekday, 7 days earlier if present."""
    target = when - pd.Timedelta(days=7)
    hit = history.loc[history["day"] == target, "units"]
    if len(hit):
        return float(hit.iloc[-1])
    if len(history):
        return float(history["units"].iloc[-7:].mean())
    return 0.0
