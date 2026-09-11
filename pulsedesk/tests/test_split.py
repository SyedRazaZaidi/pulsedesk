import pandas as pd

from pulsedesk.train import _cutoff


def test_cutoff_is_inside_range():
    days = pd.date_range("2024-01-01", periods=100, freq="D")
    frame = pd.DataFrame({"day": days})
    cut = _cutoff(frame)
    assert days[0] < cut < days[-1]
