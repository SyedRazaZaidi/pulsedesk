import pandas as pd

from pulsedesk.models import seasonal_naive


def test_seasonal_naive_uses_last_week():
    days = pd.date_range("2024-01-01", periods=14, freq="D")
    hist = pd.DataFrame({"day": days, "units": range(14)})
    got = seasonal_naive(hist, pd.Timestamp("2024-01-15"))
    assert got == 7.0
