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

async def test_mark_reservation_seated_records_seated_at_once(client):
    payload = {
        "customer_name": "Temporal Guest",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": _future_time(72),
    }

    created_response = await client.post(
        "/api/v1/reservations",
        json=payload,
    )
    assert created_response.status_code == 201, created_response.text

    created = created_response.json()
    assert created["status"] == "confirmed"

    seated_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "seated"},
    )
    assert seated_response.status_code == 200, seated_response.text

    seated = seated_response.json()
    assert seated["status"] == "seated"
    assert seated["seated_at"] is not None

    first_seated_at = seated["seated_at"]

    repeated_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "seated"},
    )
    assert repeated_response.status_code == 200, repeated_response.text

    repeated = repeated_response.json()
    assert repeated["status"] == "seated"
    assert repeated["seated_at"] == first_seated_at

async def test_mark_reservation_completed_records_completed_at_once(client):
    payload = {
        "customer_name": "Completed Guest",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": _future_time(96),
    }

    created_response = await client.post(
        "/api/v1/reservations",
        json=payload,
    )
    assert created_response.status_code == 201, created_response.text

    created = created_response.json()

    seated_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "seated"},
    )
    assert seated_response.status_code == 200, seated_response.text

    completed_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "completed"},
    )
    assert completed_response.status_code == 200, completed_response.text

    completed = completed_response.json()
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None

    first_completed_at = completed["completed_at"]

    repeated_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "completed"},
    )
    assert repeated_response.status_code == 200, repeated_response.text

    repeated = repeated_response.json()
    assert repeated["status"] == "completed"
    assert repeated["completed_at"] == first_completed_at

async def test_cancel_reservation_records_cancelled_at_once(client):
    payload = {
        "customer_name": "Cancelled Temporal Guest",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": _future_time(120),
    }

    created_response = await client.post(
        "/api/v1/reservations",
        json=payload,
    )
    assert created_response.status_code == 201, created_response.text

    created = created_response.json()

    cancelled_response = await client.delete(
        f"/api/v1/reservations/{created['id']}",
    )
    assert cancelled_response.status_code == 200, cancelled_response.text

    cancelled = cancelled_response.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_at"] is not None

    first_cancelled_at = cancelled["cancelled_at"]

    repeated_response = await client.delete(
        f"/api/v1/reservations/{created['id']}",
    )
    assert repeated_response.status_code == 200, repeated_response.text

    repeated = repeated_response.json()
    assert repeated["status"] == "cancelled"
    assert repeated["cancelled_at"] == first_cancelled_at


async def test_mark_reservation_no_show_records_no_show_at_once(client):
    payload = {
        "customer_name": "No Show Temporal Guest",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": _future_time(144),
    }

    created_response = await client.post(
        "/api/v1/reservations",
        json=payload,
    )
    assert created_response.status_code == 201, created_response.text

    created = created_response.json()

    no_show_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "no_show"},
    )
    assert no_show_response.status_code == 200, no_show_response.text

    no_show = no_show_response.json()
    assert no_show["status"] == "no_show"
    assert no_show["no_show_at"] is not None

    first_no_show_at = no_show["no_show_at"]

    repeated_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "no_show"},
    )
    assert repeated_response.status_code == 200, repeated_response.text

    repeated = repeated_response.json()
    assert repeated["status"] == "no_show"
    assert repeated["no_show_at"] == first_no_show_at
