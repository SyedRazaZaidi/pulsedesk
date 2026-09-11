from fastapi.testclient import TestClient

from pulsedesk.serve.app import create_app


def test_pulse_and_board():
    client = TestClient(create_app())
    health = client.get("/api/health").json()
    assert health["ok"] is True
    assert health["observations"] > 0
    pulse = client.get("/api/pulse").json()
    assert "nodes" in pulse
    assert pulse["metrics"].get("mae_model")
    board = client.get("/api/board").json()["items"]
    assert board
    assert "risk" in board[0]
    heat = client.get("/api/heatmap").json()["cells"]
    assert heat
    page = client.get("/")
    assert page.status_code == 200
    assert b"night ledger" in page.content.lower()
