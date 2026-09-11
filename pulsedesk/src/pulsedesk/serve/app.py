from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pulsedesk.config import ARTIFACTS
from pulsedesk.db import connect, init_db
from pulsedesk.serve.data import register_data_routes

STATIC = Path(__file__).resolve().parent / "static"


class DecisionIn(BaseModel):
    rec_id: int
    action: str
    qty: int | None = None
    note: str = ""


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(title="PulseDesk", version="0.2.0", docs_url="/api/docs")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    register_data_routes(app)

    @app.get("/api/health")
    def health() -> dict:
        with connect() as con:
            n_obs = con.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
            n_rec = con.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
        return {"ok": True, "observations": n_obs, "recommendations": n_rec}

    @app.get("/api/metrics")
    def metrics() -> dict:
        path = ARTIFACTS / "eval.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"status": "run pulsedesk train"}

    @app.get("/api/drivers")
    def drivers() -> dict:
        from pulsedesk.features import FEATURE_COLS
        from pulsedesk.models import load_models

        try:
            models = load_models()
        except FileNotFoundError:
            return {"items": []}
        labels = {
            "lag_1": "yesterday",
            "lag_7": "same day last week",
            "lag_14": "two weeks back",
            "roll_7": "7-day mean",
            "roll_28": "28-day mean",
            "dow": "weekday",
            "week": "week of year",
            "month": "month",
            "promo": "promo today",
            "promo_lag": "promo yesterday",
            "store_id": "store",
            "sku_id": "SKU",
        }
        booster = models["p50"]
        gains = booster.feature_importance(importance_type="gain")
        pairs = sorted(zip(FEATURE_COLS, [float(g) for g in gains]), key=lambda x: -x[1])
        total = sum(p[1] for p in pairs) or 1.0
        return {
            "items": [
                {"name": labels.get(n, n), "key": n, "gain": g, "share": g / total}
                for n, g in pairs
            ]
        }

    @app.get("/api/heatmap")
    def heatmap(store_id: int | None = None) -> dict:
        q = """
        SELECT s.sku, s.name, CAST(strftime('%w', o.day) AS INTEGER) AS dow,
               AVG(o.units) AS units
        FROM observations o
        JOIN skus s ON s.id = o.sku_id
        """
        params: list = []
        if store_id is not None:
            q += " WHERE o.store_id = ?"
            params.append(store_id)
        q += " GROUP BY s.sku, s.name, dow ORDER BY s.sku, dow"
        with connect() as con:
            rows = [dict(r) for r in con.execute(q, params)]
        return {"cells": rows}

    @app.get("/api/sparks")
    def sparks(store_id: int | None = None) -> dict:
        q = """
        SELECT store_id, sku_id, day, units
        FROM observations
        WHERE day >= (SELECT date(MAX(day), '-28 days') FROM observations)
        """
        params: list = []
        if store_id is not None:
            q += " AND store_id = ?"
            params.append(store_id)
        q += " ORDER BY store_id, sku_id, day"
        with connect() as con:
            rows = [dict(r) for r in con.execute(q, params)]
        return {"points": rows}

    @app.get("/api/stores")
    def stores() -> dict:
        with connect() as con:
            rows = [dict(r) for r in con.execute("SELECT * FROM stores")]
        return {"stores": rows}

    @app.get("/api/board")
    def board(store_id: int | None = None) -> dict:
        q = """
        SELECT r.id, r.asof, r.store_id, r.sku_id, r.cover_days, r.on_hand,
               r.need_p50, r.need_p90, r.suggested_qty, r.reason,
               s.sku, s.name, s.category, st.name AS store,
               (SELECT action FROM decisions d WHERE d.rec_id = r.id ORDER BY d.id DESC LIMIT 1) AS last_action
        FROM recommendations r
        JOIN skus s ON s.id = r.sku_id
        JOIN stores st ON st.id = r.store_id
        """
        params: list = []
        if store_id is not None:
            q += " WHERE r.store_id = ?"
            params.append(store_id)
        q += " ORDER BY r.suggested_qty DESC"
        with connect() as con:
            rows = [dict(r) for r in con.execute(q, params)]
        for row in rows:
            need90 = float(row["need_p90"] or 0)
            on_hand = float(row["on_hand"] or 0)
            row["risk"] = max(0.0, (need90 - on_hand) / max(need90, 1.0))
            row["cover_now"] = on_hand / max(float(row["need_p50"] or 1) / 14.0, 0.1)
        return {"items": rows}

    @app.get("/api/pulse")
    def pulse() -> dict:
        with connect() as con:
            city = [
                dict(r)
                for r in con.execute(
                    """
                    SELECT day, SUM(units) AS units
                    FROM observations
                    WHERE day >= (SELECT date(MAX(day), '-45 days') FROM observations)
                    GROUP BY day ORDER BY day
                    """
                )
            ]
            cats = [
                dict(r)
                for r in con.execute(
                    """
                    SELECT s.category, SUM(r.suggested_qty) AS qty, AVG(r.need_p90 - r.on_hand) AS gap
                    FROM recommendations r JOIN skus s ON s.id = r.sku_id
                    GROUP BY s.category
                    """
                )
            ]
            open_n = con.execute(
                """
                SELECT COUNT(*) FROM recommendations r
                WHERE NOT EXISTS (SELECT 1 FROM decisions d WHERE d.rec_id = r.id)
                """
            ).fetchone()[0]
            nodes = [
                dict(r)
                for r in con.execute(
                    """
                    SELECT st.id, st.name, st.city,
                           (SELECT COALESCE(SUM(units),0) FROM observations o
                            WHERE o.store_id = st.id
                              AND o.day >= (SELECT date(MAX(day), '-7 days') FROM observations)
                           ) AS units_7d,
                           (SELECT COUNT(*) FROM recommendations r
                            WHERE r.store_id = st.id
                              AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.rec_id = r.id)
                           ) AS open_recs
                    FROM stores st
                    """
                )
            ]
        path = ARTIFACTS / "eval.json"
        metrics = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        lift = None
        if metrics.get("mae_baseline"):
            lift = (1 - metrics["mae_model"] / metrics["mae_baseline"]) * 100
        return {
            "city": city,
            "categories": cats,
            "nodes": nodes,
            "open_recs": open_n,
            "lift_pct": lift,
            "metrics": metrics,
        }

    @app.get("/api/series")
    def series(store_id: int, sku_id: int) -> dict:
        with connect() as con:
            hist = [
                dict(r)
                for r in con.execute(
                    "SELECT day, units, promo, on_hand FROM observations WHERE store_id=? AND sku_id=? ORDER BY day",
                    (store_id, sku_id),
                )
            ]
            fc = [
                dict(r)
                for r in con.execute(
                    "SELECT day, p10, p50, p90, baseline FROM forecasts WHERE store_id=? AND sku_id=? ORDER BY day",
                    (store_id, sku_id),
                )
            ]
            sku = con.execute("SELECT * FROM skus WHERE id=?", (sku_id,)).fetchone()
            store = con.execute("SELECT * FROM stores WHERE id=?", (store_id,)).fetchone()
        if not sku:
            raise HTTPException(404, "unknown sku")
        return {
            "sku": dict(sku),
            "store": dict(store) if store else {},
            "history": hist[-90:],
            "forecast": fc,
        }

    @app.post("/api/decide")
    def decide(body: DecisionIn) -> dict:
        if body.action not in {"accept", "edit", "dismiss"}:
            raise HTTPException(400, "action must be accept, edit, or dismiss")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with connect() as con:
            rec = con.execute("SELECT id FROM recommendations WHERE id=?", (body.rec_id,)).fetchone()
            if not rec:
                raise HTTPException(404, "unknown rec_id")
            con.execute(
                "INSERT INTO decisions (rec_id, action, qty, note, created_at) VALUES (?,?,?,?,?)",
                (body.rec_id, body.action, body.qty, body.note, now),
            )
            row_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"ok": True, "id": row_id}

    @app.get("/api/decisions")
    def decisions(limit: int = 40) -> dict:
        with connect() as con:
            rows = [
                dict(r)
                for r in con.execute(
                    """
                    SELECT d.id, d.rec_id, d.action, d.qty, d.note, d.created_at,
                           s.sku, s.name AS sku_name, st.name AS store
                    FROM decisions d
                    JOIN recommendations r ON r.id = d.rec_id
                    JOIN skus s ON s.id = r.sku_id
                    JOIN stores st ON st.id = r.store_id
                    ORDER BY d.id DESC LIMIT ?
                    """,
                    (limit,),
                )
            ]
        return {"items": rows}

    if STATIC.exists():
        app.mount("/static", StaticFiles(directory=STATIC), name="static")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(STATIC / "index.html")

    return app


app = create_app()
