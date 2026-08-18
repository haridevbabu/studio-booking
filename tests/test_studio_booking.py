import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_studio_workflow(client: AsyncClient) -> None:
    staff_res = await client.post("/users", json={"email": "boss@studio.com", "name": "Admin", "is_staff": True})
    member_res = await client.post("/users", json={"email": "member@studio.com", "name": "Jane", "is_staff": False})

    staff_id = staff_res.json()["id"]
    member_id = member_res.json()["id"]

    studio_res = await client.post("/studios",
                                   json={"name": "Metcon Central", "timezone": "America/New_York",
                                         "cancellation_cutoff_hours": 4},
                                   headers={"X-User-Id": staff_id})
    assert studio_res.status_code == 201
    studio_id = studio_res.json()["id"]

    class_res = await client.post(f"/studios/{studio_id}/classes", json={
        "name": "Savage Shred", "instructor": "Coach Dan", "start_time": "2026-10-10T12:00:00Z", "total_capacity": 1,
        "credit_cost": 2
    }, headers={"X-User-Id": staff_id})
    class_id = class_res.json()["id"]

    await client.post(f"/users/{member_id}/credit-packs",
                      json={"total_credits": 10, "expiry_date": "2026-11-11T00:00:00Z"},
                      headers={"X-User-Id": staff_id})

    bal_res = await client.get(f"/users/{member_id}/credits/balance", headers={"X-User-Id": member_id})
    assert bal_res.json()["current_balance"] == 10

    book_res = await client.post("/bookings", json={"class_id": class_id}, headers={"X-User-Id": member_id})
    assert book_res.json()["status"] == "CONFIRMED"

    statement_res = await client.get(f"/users/{member_id}/credits/statement", headers={"X-User-Id": member_id})
    assert len(statement_res.json()) == 2
