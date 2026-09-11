# PulseDesk

**Karachi night ledger** — a retail ops desk that forecasts 14-day demand as a band, not a point, then turns that band into an order you can stamp.

Not a chatbot. One process. CPU. No API key. No PyTorch.

```
seasonal naive → LightGBM p10 / p50 / p90 → cover − on-hand → human stamp
```

Holdout **1,488 store-days** (time split, no leaked future):

| | MAE | notes |
|---|---|---|
| LightGBM p50 | **5.05** | MAPE 15% |
| Seasonal naive | 7.68 | same holdout |
| Lift | **~34%** | model beats baseline |
| [p10, p90] coverage | **77%** | target ~80% |

## What you actually do

Six desks, one SQLite file.

| Desk | What it is |
|---|---|
| **Command** | City pulse, tickets, transfer radar, demand shock, buyer pack. Click a ticket to open the forecast theater. |
| **Ledger** | 10k+ nights. Filter, edit, write a row, import / export CSV. |
| **Catalog** | SKUs, lead time, unit cost, new store nodes. |
| **Stock** | Receive, write-off, count, transfer. Shelf value. Move tape. |
| **Lab** | Holdout tape, feature gain, what-if cover. |
| **Tape** | Every accept / skip / edit + notes + audit. |

Special loops (these are the hireable bits):

- **Quantile order** — service slider mixes p50→p90; shock slider lifts the city (Eid-style).
- **Transfer radar** — equalize cover between Harbor Market and Midtown Mart with one move.
- **Buyer pack** — one purchase order for the city, CSV for the buyer.
- **Explain** — on-hand days, band, mix, shock. No magic number.
- **Sister node** — the other store’s actuals on the same chart.
- **Ctrl+K** — jump a desk, open a SKU, fire a transfer.

Keyboard on an open ticket: `←` `→` · `Enter` sign · `X` skip · `Esc` close · `Ctrl+K` palette.

## Quick start

```powershell
cd D:\MyProjects\pulsedesk
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pulsedesk all
pulsedesk serve
```

Open [http://127.0.0.1:8010](http://127.0.0.1:8010).

```text
pulsedesk seed    # 12 SKUs × 2 Karachi stores × ~420 days → SQLite
pulsedesk train   # time split, fit quantiles, write recs, stamp eval
pulsedesk serve   # one FastAPI process, :8010
pytest -q
```

## How the model is honest

1. Daily units live in SQLite (`observations`).
2. Features are lags and rolling means — **shifted**, so tomorrow cannot leak.
3. Train on the first 85% of calendar days. Score the rest.
4. Baseline is **seasonal naive** (same weekday last week), not “we beat a dummy mean.”
5. Forward 14 days are a recursive p50 walk. Order qty = mixed quantile cover minus on-hand.
6. A human must accept, edit, or dismiss. That write is the product.

Default catalog is synthetic (GroupLens-scale shape, planted weekend / promo). Swap the seed when you have a real ledger. Do not claim 25 million rows.

## Stack

Python 3.10+ · FastAPI · LightGBM · SQLite · one static desk. Laptop-safe. No Docker. No local LLM.

See [DESIGN.md](DESIGN.md). API docs while serving: `/api/docs`.

## License

MIT. © 2026 Syed Raza Zaidi

<img width="1350" height="642" alt="PD-2" src="https://github.com/user-attachments/assets/19d5feaf-477e-428f-968b-425f44e69ee7" />
<img width="1351" height="640" alt="PD-1" src="https://github.com/user-attachments/assets/5745dc4e-27c7-4904-99a2-9e6dea03154b" />
<img width="1351" height="643" alt="PD-9" src="https://github.com/user-attachments/assets/4c50bc9f-dcc2-44b0-bc41-3ed6bf628a4e" />
<img width="1352" height="639" alt="PD-8" src="https://github.com/user-attachments/assets/807fb7f0-df60-446d-a821-957425a73804" />
<img width="1350" height="639" alt="PD-7" src="https://github.com/user-attachments/assets/e5bf9769-f9b7-455f-ad1e-195016db7461" />
<img width="1351" height="639" alt="PD-6" src="https://github.com/user-attachments/assets/5f266bec-5ace-4b8f-b7ee-bfcb1df95d63" />
<img width="1352" height="639" alt="PD-5" src="https://github.com/user-attachments/assets/ef56fac1-53dd-4cc0-8649-53845bcabe80" />
<img width="1351" height="642" alt="PD-4" src="https://github.com/user-attachments/assets/43ca4535-4046-41bf-9c57-7b401590b1ec" />
<img width="1353" height="647" alt="PD-10" src="https://github.com/user-attachments/assets/c83e36eb-8013-47bb-be3c-e2a92e0dd503" />
<img width="1352" height="640" alt="PD-12" src="https://github.com/user-attachments/assets/5a2259d7-ea84-4542-89cc-4e0111c3f628" />
<img width="1350" height="644" alt="PD-11" src="https://github.com/user-attachments/assets/ff4d05a9-1057-4237-8a6b-5a1c13ad9986" />
<img width="1352" height="643" alt="PD-3" src="https://github.com/user-attachments/assets/4436a7c7-9010-468e-b4c7-dc481d3878c5" />

