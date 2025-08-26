import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="function") # Changed scope to function
def auth_headers(client: TestClient):
    """Fixture to create a user and get auth headers."""
    username = "journaluser"
    password = "journalpassword"

    client.post("/api/v1/auth/register", json={"username": username, "password": password})

    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_create_journal_entry_unauthenticated(client: TestClient):
    response = client.post("/api/v1/journal/", json={})
    assert response.status_code == 401 # Unauthorized


async def test_create_and_read_journal_entry(client: TestClient, auth_headers: dict):
    entry_data = {
        "underlying": "TSLA",
        "strategy": "Covered Call",
        "entry_price": 5.50,
        "quantity": 10,
        "rationale": "Testing rationale"
    }
    response = client.post("/api/v1/journal/", json=entry_data, headers=auth_headers)

    assert response.status_code == 201
    created_entry = response.json()
    assert created_entry["underlying"] == "TSLA"
    assert created_entry["owner_id"] is not None
    entry_id = created_entry["id"]

    response = client.get(f"/api/v1/journal/{entry_id}", headers=auth_headers)
    assert response.status_code == 200
    read_entry = response.json()
    assert read_entry["id"] == entry_id
    assert read_entry["strategy"] == "Covered Call"

    response = client.get("/api/v1/journal/", headers=auth_headers)
    assert response.status_code == 200
    entries_list = response.json()
    assert isinstance(entries_list, list)
    assert len(entries_list) >= 1
    assert entries_list[0]["id"] == entry_id


async def test_read_non_existent_entry(client: TestClient, auth_headers: dict):
    response = client.get("/api/v1/journal/999999", headers=auth_headers)
    assert response.status_code == 404


async def test_user_cannot_access_other_user_journal(client: TestClient, auth_headers: dict):
    entry_data = {"underlying": "SPY", "strategy": "Iron Condor", "entry_price": 1.0, "quantity": 5}
    response = client.post("/api/v1/journal/", json=entry_data, headers=auth_headers)
    assert response.status_code == 201
    entry_id = response.json()["id"]

    user_b_creds = {"username": "userB", "password": "passwordB"}
    client.post("/api/v1/auth/register", json=user_b_creds)
    login_res = client.post("/api/v1/auth/login", data=user_b_creds, headers={"Content-Type": "application/x-www-form-urlencoded"})
    user_b_token = login_res.json()["access_token"]
    user_b_headers = {"Authorization": f"Bearer {user_b_token}"}

    response = client.get(f"/api/v1/journal/{entry_id}", headers=user_b_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "沒有權限讀取此日誌"
