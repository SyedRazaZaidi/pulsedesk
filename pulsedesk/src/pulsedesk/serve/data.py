from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from pulsedesk.db import connect


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _audit(con, kind: str, detail: str) -> None:
    con.execute(
        "INSERT INTO audit (kind, detail, created_at) VALUES (?,?,?)",
        (kind, detail, _now()),
    )


class SkuIn(BaseModel):
    sku: str
    name: str
    category: str
    unit_cost: float = Field(ge=0)
    lead_days: int = Field(default=3, ge=1, le=30)


class SkuPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    unit_cost: float | None = Field(default=None, ge=0)
    lead_days: int | None = Field(default=None, ge=1, le=30)


class StoreIn(BaseModel):
    name: str
    city: str = "Karachi"


class ObsIn(BaseModel):
    store_id: int
    sku_id: int
    day: str
    units: float = Field(ge=0)
    promo: int = 0
    on_hand: float = Field(ge=0)


class StockIn(BaseModel):
    store_id: int
    sku_id: int
    qty: float
    reason: str = "receive"


class WhatIfIn(BaseModel):
    store_id: int
    sku_id: int
    alpha: float = Field(default=0.8, ge=0, le=1)
    on_hand: float | None = Field(default=None, ge=0)


class TransferIn(BaseModel):
    sku_id: int
    from_store_id: int
    to_store_id: int
    qty: float = Field(gt=0)


class DecisionNote(BaseModel):
    note: str


def register_data_routes(app: FastAPI) -> None:
    @app.get("/api/skus")
    def skus() -> dict:
        with connect() as con:
            rows = [dict(r) for r in con.execute("SELECT * FROM skus ORDER BY category, sku")]
        return {"skus": rows}

    @app.post("/api/skus")
    def add_sku(body: SkuIn) -> dict:
        with connect() as con:
            exists = con.execute("SELECT id FROM skus WHERE sku=?", (body.sku.strip(),)).fetchone()
            if exists:
                raise HTTPException(409, "sku code already exists")
            con.execute(
                "INSERT INTO skus (sku, name, category, unit_cost, lead_days) VALUES (?,?,?,?,?)",
                (body.sku.strip(), body.name.strip(), body.category.strip(), body.unit_cost, body.lead_days),
            )
            row_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            _audit(con, "sku.add", f"{body.sku} {body.name}")
        return {"ok": True, "id": row_id}

    @app.patch("/api/skus/{sku_id}")
    def patch_sku(sku_id: int, body: SkuPatch) -> dict:
        fields = body.model_dump(exclude_none=True)
        if not fields:
            raise HTTPException(400, "nothing to update")
        sets = ", ".join(f"{k}=?" for k in fields)
        with connect() as con:
            found = con.execute("SELECT id FROM skus WHERE id=?", (sku_id,)).fetchone()
            if not found:
                raise HTTPException(404, "unknown sku")
            con.execute(f"UPDATE skus SET {sets} WHERE id=?", [*fields.values(), sku_id])
            _audit(con, "sku.edit", f"id={sku_id} {fields}")
        return {"ok": True}

    @app.post("/api/stores")
    def add_store(body: StoreIn) -> dict:
        with connect() as con:
            con.execute("INSERT INTO stores (name, city) VALUES (?,?)", (body.name.strip(), body.city.strip()))
            row_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            _audit(con, "store.add", body.name)
        return {"ok": True, "id": row_id}

    @app.get("/api/observations")
    def observations(
        store_id: int | None = None,
        sku_id: int | None = None,
        day_from: str | None = None,
        day_to: str | None = None,
        promo: int | None = None,
        q: str = "",
        limit: int = 40,
        offset: int = 0,
    ) -> dict:
        where = ["1=1"]
        params: list = []
        if store_id is not None:
            where.append("o.store_id=?")
            params.append(store_id)
        if sku_id is not None:
            where.append("o.sku_id=?")
            params.append(sku_id)
        if day_from:
            where.append("o.day>=?")
            params.append(day_from)
        if day_to:
            where.append("o.day<=?")
            params.append(day_to)
        if promo is not None:
            where.append("o.promo=?")
            params.append(promo)
        if q.strip():
            where.append("(s.sku LIKE ? OR s.name LIKE ?)")
            params.extend([f"%{q.strip()}%", f"%{q.strip()}%"])
        clause = " AND ".join(where)
        sql = f"""
            SELECT o.store_id, o.sku_id, o.day, o.units, o.promo, o.on_hand,
                   s.sku, s.name, s.category, st.name AS store
            FROM observations o
            JOIN skus s ON s.id = o.sku_id
            JOIN stores st ON st.id = o.store_id
            WHERE {clause}
            ORDER BY o.day DESC, s.sku
            LIMIT ? OFFSET ?
        """
        count_sql = f"SELECT COUNT(*) FROM observations o JOIN skus s ON s.id=o.sku_id WHERE {clause}"
        with connect() as con:
            total = con.execute(count_sql, params).fetchone()[0]
            rows = [dict(r) for r in con.execute(sql, [*params, max(1, min(limit, 200)), max(0, offset)])]
        return {"items": rows, "total": total, "limit": limit, "offset": offset}

    @app.post("/api/observations")
    def upsert_obs(body: ObsIn) -> dict:
        if body.promo not in (0, 1):
            raise HTTPException(400, "promo must be 0 or 1")
        with connect() as con:
            store = con.execute("SELECT id FROM stores WHERE id=?", (body.store_id,)).fetchone()
            sku = con.execute("SELECT sku FROM skus WHERE id=?", (body.sku_id,)).fetchone()
            if not store or not sku:
                raise HTTPException(404, "unknown store or sku")
            con.execute(
                """
                INSERT INTO observations (store_id, sku_id, day, units, promo, on_hand)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(store_id, sku_id, day) DO UPDATE SET
                  units=excluded.units, promo=excluded.promo, on_hand=excluded.on_hand
                """,
                (body.store_id, body.sku_id, body.day, body.units, body.promo, body.on_hand),
            )
            _audit(con, "obs.upsert", f"{sku['sku']} {body.day} units={body.units}")
        return {"ok": True}

    @app.get("/api/stock")
    def stock(store_id: int | None = None) -> dict:
        q = """
            SELECT o.store_id, o.sku_id, o.day, o.units, o.on_hand, o.promo,
                   s.sku, s.name, s.category, s.unit_cost, s.lead_days, st.name AS store,
                   r.need_p50, r.need_p90, r.suggested_qty, r.id AS rec_id
            FROM observations o
            JOIN skus s ON s.id = o.sku_id
            JOIN stores st ON st.id = o.store_id
            LEFT JOIN recommendations r ON r.store_id = o.store_id AND r.sku_id = o.sku_id
            WHERE o.day = (
              SELECT MAX(o2.day) FROM observations o2
              WHERE o2.store_id = o.store_id AND o2.sku_id = o.sku_id
            )
        """
        params: list = []
        if store_id is not None:
            q += " AND o.store_id=?"
            params.append(store_id)
        q += " ORDER BY st.name, s.sku"
        with connect() as con:
            rows = [dict(r) for r in con.execute(q, params)]
        for row in rows:
            need90 = float(row["need_p90"] or 0)
            on_hand = float(row["on_hand"] or 0)
            row["risk"] = max(0.0, (need90 - on_hand) / max(need90, 1.0))
            row["value"] = on_hand * float(row["unit_cost"] or 0)
        return {"items": rows}

    def _apply_stock(con, store_id: int, sku_id: int, qty: float, reason: str) -> float:
        last = con.execute(
            """
            SELECT day, on_hand FROM observations
            WHERE store_id=? AND sku_id=? ORDER BY day DESC LIMIT 1
            """,
            (store_id, sku_id),
        ).fetchone()
        if not last:
            raise HTTPException(404, "no observation for that store/sku — add a ledger row first")
        new_on = max(0.0, float(last["on_hand"]) + float(qty))
        con.execute(
            "UPDATE observations SET on_hand=? WHERE store_id=? AND sku_id=? AND day=?",
            (new_on, store_id, sku_id, last["day"]),
        )
        con.execute(
            "UPDATE recommendations SET on_hand=? WHERE store_id=? AND sku_id=?",
            (new_on, store_id, sku_id),
        )
        con.execute(
            "INSERT INTO inventory_moves (store_id, sku_id, qty, reason, created_at) VALUES (?,?,?,?,?)",
            (store_id, sku_id, qty, reason, _now()),
        )
        return new_on

    @app.post("/api/stock")
    def move_stock(body: StockIn) -> dict:
        if body.qty == 0:
            raise HTTPException(400, "qty cannot be zero")
        with connect() as con:
            new_on = _apply_stock(con, body.store_id, body.sku_id, body.qty, body.reason.strip() or "adjust")
            _audit(con, "stock.move", f"store={body.store_id} sku={body.sku_id} qty={body.qty}")
        return {"ok": True, "on_hand": new_on}

    @app.post("/api/transfer")
    def transfer(body: TransferIn) -> dict:
        if body.from_store_id == body.to_store_id:
            raise HTTPException(400, "cannot transfer to the same node")
        with connect() as con:
            left = _apply_stock(con, body.from_store_id, body.sku_id, -body.qty, "transfer-out")
            right = _apply_stock(con, body.to_store_id, body.sku_id, body.qty, "transfer-in")
            _audit(con, "stock.transfer", f"sku={body.sku_id} {body.qty} {body.from_store_id}->{body.to_store_id}")
        return {"ok": True, "from_on_hand": left, "to_on_hand": right}

    @app.get("/api/intel")
    def intel() -> dict:
        with connect() as con:
            recs = [
                dict(r)
                for r in con.execute(
                    """
                    SELECT r.store_id, r.sku_id, r.on_hand, r.need_p50, r.need_p90,
                           s.sku, s.name, st.name AS store
                    FROM recommendations r
                    JOIN skus s ON s.id = r.sku_id
                    JOIN stores st ON st.id = r.store_id
                    """
                )
            ]
            recent = [
                dict(r)
                for r in con.execute(
                    """
                    SELECT o.store_id, o.sku_id, s.sku, s.name, st.name AS store,
                           AVG(CASE WHEN o.day >= date((SELECT MAX(day) FROM observations), '-6 days')
                                    THEN o.units END) AS u7,
                           AVG(o.units) AS u28
                    FROM observations o
                    JOIN skus s ON s.id = o.sku_id
                    JOIN stores st ON st.id = o.store_id
                    WHERE o.day >= date((SELECT MAX(day) FROM observations), '-27 days')
                    GROUP BY o.store_id, o.sku_id
                    """
                )
            ]
        by_sku: dict[int, list] = {}
        for row in recs:
            by_sku.setdefault(int(row["sku_id"]), []).append(row)
        transfers = []
        for rows in by_sku.values():
            if len(rows) < 2:
                continue
            scored = []
            for row in rows:
                daily = max(float(row["need_p50"]) / 14.0, 0.1)
                scored.append((float(row["on_hand"]) / daily, daily, row))
            rich_c, rich_d, rich = max(scored, key=lambda x: x[0])
            poor_c, poor_d, poor = min(scored, key=lambda x: x[0])
            if rich["store_id"] == poor["store_id"] or rich_c - poor_c < 1.5:
                continue
            qty = int((rich_c - poor_c) * 0.5 * poor_d)
            qty = max(0, min(qty, int(float(rich["on_hand"]) * 0.45)))
            if qty >= 3:
                transfers.append(
                    {
                        "sku_id": rich["sku_id"],
                        "sku": rich["sku"],
                        "name": rich["name"],
                        "from_store_id": rich["store_id"],
                        "to_store_id": poor["store_id"],
                        "from_store": rich["store"],
                        "to_store": poor["store"],
                        "qty": qty,
                        "why": f"{rich['store']} has {rich_c:.1f}d cover, {poor['store']} has {poor_c:.1f}d",
                    }
                )
        anomalies = []
        for row in recent:
            u7 = float(row["u7"] or 0)
            u28 = float(row["u28"] or 0)
            if u28 <= 0:
                continue
            ratio = u7 / u28
            if ratio >= 1.12 or ratio <= 0.88:
                anomalies.append(
                    {
                        "store_id": row["store_id"],
                        "sku_id": row["sku_id"],
                        "sku": row["sku"],
                        "name": row["name"],
                        "store": row["store"],
                        "ratio": ratio,
                        "kind": "spike" if ratio >= 1.12 else "drop",
                        "u7": u7,
                        "u28": u28,
                    }
                )
        anomalies.sort(key=lambda x: abs(x["ratio"] - 1), reverse=True)
        return {"transfers": transfers, "anomalies": anomalies[:12]}

    @app.get("/api/pack")
    def pack(alpha: float = 0.8, shock: float = 1.0) -> dict:
        with connect() as con:
            rows = [
                dict(r)
                for r in con.execute(
                    """
                    SELECT r.*, s.sku, s.name, s.unit_cost, st.name AS store,
                           (SELECT action FROM decisions d WHERE d.rec_id=r.id ORDER BY d.id DESC LIMIT 1) AS last_action
                    FROM recommendations r
                    JOIN skus s ON s.id = r.sku_id
                    JOIN stores st ON st.id = r.store_id
                    """
                )
            ]
        lines = []
        for row in rows:
            if row["last_action"] == "dismiss":
                continue
            mix = (float(row["need_p50"]) * (1 - alpha) + float(row["need_p90"]) * alpha) * shock
            qty = max(0, int(round(mix - float(row["on_hand"]))))
            if qty <= 0:
                continue
            lines.append(
                {
                    "store": row["store"],
                    "sku": row["sku"],
                    "name": row["name"],
                    "qty": qty,
                    "cost": qty * float(row["unit_cost"] or 0),
                }
            )
        bag: dict[str, dict] = {}
        for line in lines:
            item = bag.setdefault(line["sku"], {"sku": line["sku"], "name": line["name"], "qty": 0, "cost": 0, "stores": []})
            item["qty"] += line["qty"]
            item["cost"] += line["cost"]
            item["stores"].append(f"{line['store']} {line['qty']}")
        return {
            "alpha": alpha,
            "shock": shock,
            "lines": lines,
            "by_sku": list(bag.values()),
            "units": sum(x["qty"] for x in lines),
            "cost": sum(x["cost"] for x in lines),
        }

    @app.get("/api/export/pack.csv")
    def export_pack(alpha: float = 0.8, shock: float = 1.0) -> Response:
        data = pack(alpha=alpha, shock=shock)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["store", "sku", "name", "qty", "cost"])
        for line in data["lines"]:
            w.writerow([line["store"], line["sku"], line["name"], line["qty"], f"{line['cost']:.2f}"])
        return Response(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=buyer-pack.csv"},
        )

    @app.get("/api/stock/moves")
    def stock_moves(limit: int = 30) -> dict:
        with connect() as con:
            rows = [
                dict(r)
                for r in con.execute(
                    """
                    SELECT m.id, m.qty, m.reason, m.created_at, s.sku, s.name, st.name AS store
                    FROM inventory_moves m
                    JOIN skus s ON s.id = m.sku_id
                    JOIN stores st ON st.id = m.store_id
                    ORDER BY m.id DESC LIMIT ?
                    """,
                    (max(1, min(limit, 100)),),
                )
            ]
        return {"items": rows}

    @app.post("/api/whatif")
    def whatif(body: WhatIfIn) -> dict:
        with connect() as con:
            rec = con.execute(
                """
                SELECT r.*, s.sku, s.name, s.category, st.name AS store
                FROM recommendations r
                JOIN skus s ON s.id = r.sku_id
                JOIN stores st ON st.id = r.store_id
                WHERE r.store_id=? AND r.sku_id=?
                """,
                (body.store_id, body.sku_id),
            ).fetchone()
        if not rec:
            raise HTTPException(404, "no recommendation for that pair — run pulsedesk train")
        row = dict(rec)
        on_hand = float(body.on_hand) if body.on_hand is not None else float(row["on_hand"])
        mix = float(row["need_p50"]) * (1 - body.alpha) + float(row["need_p90"]) * body.alpha
        qty = max(0, int(round(mix - on_hand)))
        return {
            "sku": row["sku"],
            "name": row["name"],
            "store": row["store"],
            "need_p50": row["need_p50"],
            "need_p90": row["need_p90"],
            "on_hand": on_hand,
            "alpha": body.alpha,
            "suggested_qty": qty,
            "risk": max(0.0, (float(row["need_p90"]) - on_hand) / max(float(row["need_p90"]), 1.0)),
            "reason": row["reason"],
        }

    @app.get("/api/alerts")
    def alerts() -> dict:
        with connect() as con:
            rows = [
                dict(r)
                for r in con.execute(
                    """
                    SELECT r.id, r.store_id, r.sku_id, r.on_hand, r.need_p50, r.need_p90, r.suggested_qty,
                           s.sku, s.name, s.category, st.name AS store,
                           (SELECT action FROM decisions d WHERE d.rec_id=r.id ORDER BY d.id DESC LIMIT 1) AS last_action
                    FROM recommendations r
                    JOIN skus s ON s.id = r.sku_id
                    JOIN stores st ON st.id = r.store_id
                    """
                )
            ]
        items = []
        for row in rows:
            need90 = float(row["need_p90"] or 0)
            on_hand = float(row["on_hand"] or 0)
            risk = max(0.0, (need90 - on_hand) / max(need90, 1.0))
            cover = on_hand / max(float(row["need_p50"] or 1) / 14.0, 0.1)
            if risk > 0.45 and not row["last_action"]:
                items.append({**row, "risk": risk, "cover_now": cover, "kind": "stockout"})
            elif cover < 3:
                items.append({**row, "risk": risk, "cover_now": cover, "kind": "thin_cover"})
        items.sort(key=lambda x: -x["risk"])
        return {"items": items}

    @app.get("/api/eval")
    def eval_runs() -> dict:
        with connect() as con:
            rows = [dict(r) for r in con.execute("SELECT * FROM eval_runs ORDER BY id DESC LIMIT 20")]
        return {"items": rows}

    @app.get("/api/audit")
    def audit_log(limit: int = 40) -> dict:
        with connect() as con:
            rows = [
                dict(r)
                for r in con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (max(1, min(limit, 100)),))
            ]
        return {"items": rows}

    @app.patch("/api/decisions/{dec_id}")
    def patch_decision(dec_id: int, body: DecisionNote) -> dict:
        with connect() as con:
            found = con.execute("SELECT id FROM decisions WHERE id=?", (dec_id,)).fetchone()
            if not found:
                raise HTTPException(404, "unknown decision")
            con.execute("UPDATE decisions SET note=? WHERE id=?", (body.note, dec_id))
            _audit(con, "decision.note", f"id={dec_id}")
        return {"ok": True}

    @app.get("/api/export/observations.csv")
    def export_obs(store_id: int | None = None, sku_id: int | None = None) -> Response:
        where = ["1=1"]
        params: list = []
        if store_id is not None:
            where.append("store_id=?")
            params.append(store_id)
        if sku_id is not None:
            where.append("sku_id=?")
            params.append(sku_id)
        with connect() as con:
            rows = con.execute(
                f"SELECT store_id, sku_id, day, units, promo, on_hand FROM observations WHERE {' AND '.join(where)} ORDER BY day, store_id, sku_id",
                params,
            ).fetchall()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["store_id", "sku_id", "day", "units", "promo", "on_hand"])
        w.writerows(rows)
        return Response(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=observations.csv"},
        )

    @app.get("/api/export/board.csv")
    def export_board() -> Response:
        with connect() as con:
            rows = con.execute(
                """
                SELECT st.name, s.sku, s.name, r.on_hand, r.need_p50, r.need_p90, r.suggested_qty, r.reason
                FROM recommendations r
                JOIN skus s ON s.id = r.sku_id
                JOIN stores st ON st.id = r.store_id
                ORDER BY r.suggested_qty DESC
                """
            ).fetchall()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["store", "sku", "name", "on_hand", "need_p50", "need_p90", "suggested_qty", "reason"])
        w.writerows(rows)
        return Response(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=board.csv"},
        )

    @app.get("/api/export/decisions.csv")
    def export_decisions() -> Response:
        with connect() as con:
            rows = con.execute(
                """
                SELECT d.created_at, d.action, d.qty, d.note, s.sku, s.name, st.name
                FROM decisions d
                JOIN recommendations r ON r.id = d.rec_id
                JOIN skus s ON s.id = r.sku_id
                JOIN stores st ON st.id = r.store_id
                ORDER BY d.id DESC
                """
            ).fetchall()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["created_at", "action", "qty", "note", "sku", "name", "store"])
        w.writerows(rows)
        return Response(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=decisions.csv"},
        )

    @app.post("/api/import/observations")
    async def import_obs(file: UploadFile = File(...)) -> dict:
        raw = (await file.read()).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(raw))
        needed = {"day", "units"}
        if not reader.fieldnames or not needed.issubset({c.strip() for c in reader.fieldnames}):
            raise HTTPException(400, "CSV needs at least day, units, plus store_id/sku_id or store/sku")
        n = 0
        with connect() as con:
            stores = {r["name"]: r["id"] for r in con.execute("SELECT id, name FROM stores")}
            skus = {r["sku"]: r["id"] for r in con.execute("SELECT id, sku FROM skus")}
            for row in reader:
                day = (row.get("day") or "").strip()
                try:
                    units = float(row.get("units") or 0)
                    promo = int(float(row.get("promo") or 0))
                    on_hand = float(row.get("on_hand") or 0)
                except ValueError as exc:
                    raise HTTPException(400, f"bad numeric row: {row}") from exc
                sid = row.get("store_id")
                kid = row.get("sku_id")
                if sid and kid:
                    store_id, sku_id = int(sid), int(kid)
                else:
                    store_id = stores.get((row.get("store") or "").strip())
                    sku_id = skus.get((row.get("sku") or "").strip())
                if not store_id or not sku_id or not day:
                    raise HTTPException(400, f"unresolved row: {row}")
                con.execute(
                    """
                    INSERT INTO observations (store_id, sku_id, day, units, promo, on_hand)
                    VALUES (?,?,?,?,?,?)
                    ON CONFLICT(store_id, sku_id, day) DO UPDATE SET
                      units=excluded.units, promo=excluded.promo, on_hand=excluded.on_hand
                    """,
                    (store_id, sku_id, day, units, promo, on_hand),
                )
                n += 1
            _audit(con, "obs.import", f"{n} rows from {file.filename}")
        return {"ok": True, "rows": n}
