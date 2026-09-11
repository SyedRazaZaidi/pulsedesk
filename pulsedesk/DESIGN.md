# PulseDesk — Design

Ops forecasting product for a small retail catalog.
Not an LLM. The product is the **band**, the **order**, and the **stamp**.

## User

Store ops lead: “How many units do I need for the next 14 days, and how wrong might I be?”

Buyer: “Give me one pack for both Karachi nodes.”

## What ships

- Daily demand in **SQLite** (SKUs × stores)
- Time split (no future leak)
- Seasonal-naive **baseline** vs LightGBM **quantile** forecast (p10 / p50 / p90)
- Recommended qty = service-level mix of the band, minus on-hand, optional shock
- Human **accept / edit / dismiss** written to `decisions`
- Transfers that equalize days-of-cover across stores
- Ledger import / export, catalog edits, stock moves, audit tape
- One FastAPI process + night-ledger UI
- CPU, no PyTorch, no Docker, no API key

## Desks

Command · Ledger · Catalog · Stock · Lab · Tape

Theater is a **click-to-open drawer**, not a permanent dock.

## Non-goals

- No 7B models, no camera, no Kafka
- No 25M-row claims. Default catalog is ~12 SKUs × 2 stores × ~420 days.

## Metrics (frozen holdout)

Written to `artifacts/eval.json` and `eval_runs`:

- MAE / MAPE on p50 vs seasonal naive
- Interval coverage of [p10, p90] (target ~80%)
- Decision log completeness (every rec can be accepted)
