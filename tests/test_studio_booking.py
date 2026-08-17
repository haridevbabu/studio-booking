import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_studio_workflow(client: AsyncClient) -> None:
    # 1. Setup Identities
    staff_res = await client.post("/users", json={"email": "boss@studio.com", "name": "Admin", "is_staff": True})
    member_res = await client.post("/users", json={"email": "member@studio.com", "name": "Jane", "is_staff": False})

    staff_id = staff_res.json()["id"]
    member_id = member_res.json()["id"]

    # 2. Staff configures Studio
    studio_res = await client.post("/studios",
                                   json={"name": "Metcon Central", "timezone": "EST", "cancellation_cutoff_hours": 6},
                                   headers={"X-User-Id": staff_id})
    assert studio_res.status_code == 201
    studio_id = studio_res.json()["id"]

    # 3. Schedule Class
    class_res = await client.post(f"/studios/{studio_id}/classes", json={
        "name": "Savage Shred", "instructor": "Coach Dan", "start_time": "2026-10-10T12:00:00", "total_capacity": 1
    }, headers={"X-User-Id": staff_id})
    class_id = class_res.json()["id"]

    # 4. Grant multiple credit packs with distinct dates
    await client.post(f"/users/{member_id}/credit-packs",
                      json={"total_credits": 10, "expiry_date": "2026-11-11T00:00:00"}, headers={"X-User-Id": staff_id})
    await client.post(f"/users/{member_id}/credit-packs",
                      json={"total_credits": 5, "expiry_date": "2026-09-09T00:00:00"}, headers={"X-User-Id": staff_id})

    # 5. Review historical point-in-time calculation balance
    bal_res = await client.get(f"/users/{member_id}/credits/balance", headers={"X-User-Id": member_id})
    assert bal_res.json()["current_balance"] == 15

    # 6. Reserve and fill capacity context
    book_res = await client.post("/bookings", json={"class_id": class_id}, headers={"X-User-Id": member_id})
    assert book_res.json()["status"] == "CONFIRMED"

    # 7. Confirm transaction statement presence
    statement_res = await client.get(f"/users/{member_id}/credits/statement", headers={"X-User-Id": member_id})
    assert len(statement_res.json()) == 3  # Two Grants + One Booking consumption
