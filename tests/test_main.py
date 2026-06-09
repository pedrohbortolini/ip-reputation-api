from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient

from app.main import app, cache


client = TestClient(app)


def setup_function():
    cache._store.clear()


def test_health_returns_200():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invalid_ip_returns_400():
    response = client.get("/reputation/nao-sou-um-ip")

    assert response.status_code == 400
    assert "inválido" in response.json()["detail"].lower()


def test_another_invalid_ip_returns_400():
    response = client.get("/reputation/999.999.999.999")

    assert response.status_code == 400


@patch("app.main.get_reputation", new_callable=AsyncMock)
def test_cache_hit_skips_external_call(mock_get_reputation):
    fake_response = {
        "ip": "8.8.8.8",
        "abuseipdb": {"abuse_score": 0},
        "ipinfo": {"country": "US"},
        "errors": [],
    }

    mock_get_reputation.return_value = fake_response

    r1 = client.get("/reputation/8.8.8.8")

    assert r1.status_code == 200
    assert r1.json()["cached"] is False
    assert mock_get_reputation.call_count == 1

    r2 = client.get("/reputation/8.8.8.8")

    assert r2.status_code == 200
    assert r2.json()["cached"] is True
    assert mock_get_reputation.call_count == 1
