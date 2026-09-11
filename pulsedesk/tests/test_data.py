from fastapi.testclient import TestClient

from pulsedesk.serve.app import create_app


def test_data_surfaces():
    client = TestClient(create_app())
    assert client.get("/api/skus").json()["skus"]
    led = client.get("/api/observations", params={"limit": 5}).json()
    assert led["total"] > 0
    assert client.get("/api/stock").json()["items"]
    pair = client.get("/api/board").json()["items"][0]
    what = client.post(
        "/api/whatif",
        json={"store_id": pair["store_id"], "sku_id": pair["sku_id"], "alpha": 0.8},
    )
    assert what.status_code == 200
    assert "suggested_qty" in what.json()
    assert client.get("/api/export/board.csv").status_code == 200
    assert client.get("/api/alerts").status_code == 200
    intel = client.get("/api/intel").json()
    assert "transfers" in intel and "anomalies" in intel
    pack = client.get("/api/pack").json()
    assert "lines" in pack
    page = client.get("/")
    assert b"#/ledger" in page.content
    assert b"#/catalog" in page.content
