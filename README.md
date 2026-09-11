# pulsedesk
PulseDesk forecasts 14-day demand as a p10/p50/p90 band, turns cover minus on-hand into an order ticket, and logs every accept/skip. Holdout: MAE 5.05 vs naive 7.68 (~34% lift), 77% interval coverage. One FastAPI process. SQLite. No API key.
