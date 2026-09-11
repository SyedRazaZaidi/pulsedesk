# LinkedIn — copy when the repo is public

## Post

I built PulseDesk — a retail ops desk, not a chatbot.

Karachi. Two stores. Twelve SKUs. Every night’s demand in SQLite.

Most student “AI projects” give you one number and a dashboard. Ops people do not buy that. They want a band, an order, and a record of who overrode it.

PulseDesk:

→ seasonal naive baseline vs LightGBM p10 / p50 / p90  
→ 14-day cover minus on-hand  
→ service-level + demand-shock sliders  
→ transfer radar between stores  
→ buyer pack (one PO for the city)  
→ human stamp on every ticket  

Holdout (1,488 store-days, time-split, no leaked future):  
MAE 5.05 vs naive 7.68 (~34% lift). [p10, p90] covers 77% of nights.

One process. CPU. No API key. No PyTorch.

GitHub: [PASTE REPO URL]  
Run: `pulsedesk all` then `pulsedesk serve`

#MachineLearning #Forecasting #RetailTech #LightGBM #FastAPI #BuildInPublic

## GitHub / resume project blurb

PulseDesk — Quantile demand + ops desk. LightGBM p10/p50/p90 vs seasonal naive on a time-split holdout (MAE 5.05 vs 7.68). SQLite ledger, transfer radar, buyer pack, human sign-off. One FastAPI process.
