"""End-to-end tests for the reservations API."""
from datetime import datetime, timedelta, timezone


def _future_time(hours: int = 24) -> str:
    """Return an ISO datetime safely inside opening hours."""
    target = datetime.now(timezone.utc) + timedelta(hours=hours)
    target = target.replace(hour=19, minute=0, second=0, microsecond=0)
    return target.isoformat()


async def test_health_check(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_create_and_get_reservation(client):
    payload = {
        "customer_name": "Ada Lovelace",
        "customer_phone": "+15551234567",
        "party_size": 4,
        "reservation_time": _future_time(),
    }
    r = await client.post("/api/v1/reservations", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "confirmed"
    assert body["customer_name"] == "Ada Lovelace"

    # Fetch it back
    r2 = await client.get(f"/api/v1/reservations/{body['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"]


async def test_create_reservation_in_past_rejected(client):
    payload = {
        "customer_name": "Past Person",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    }
    r = await client.post("/api/v1/reservations", json=payload)
    assert r.status_code == 422


async def test_oversized_party_rejected(client):
    payload = {
        "customer_name": "Big Group",
        "customer_phone": "+15551234567",
        "party_size": 99,  # exceeds MAX_PARTY_SIZE
        "reservation_time": _future_time(),
    }
    r = await client.post("/api/v1/reservations", json=payload)
    assert r.status_code == 422


async def test_cancel_reservation(client):
    payload = {
        "customer_name": "Bye Bye",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": _future_time(48),
    }
    created = (await client.post("/api/v1/reservations", json=payload)).json()
    r = await client.delete(f"/api/v1/reservations/{created['id']}")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


async def test_list_reservations(client):
    for i in range(3):
        await client.post(
            "/api/v1/reservations",
            json={
                "customer_name": f"Guest {i}",
                "customer_phone": "+15551234567",
                "party_size": 2,
                "reservation_time": _future_time(24 + i),
            },
        )
    r = await client.get("/api/v1/reservations")
    assert r.status_code == 200
    assert len(r.json()) >= 3


async def test_get_unknown_reservation_returns_404(client):
    r = await client.get("/api/v1/reservations/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
