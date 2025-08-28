import pytest
from fastapi.testclient import TestClient
from app.models import UserCreate

pytestmark = pytest.mark.asyncio


async def test_register_user(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "testuser1", "password": "testpassword"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser1"
    assert "id" in data
    assert "hashed_password" not in data


async def test_register_existing_user(client: TestClient):
    # First, create a user
    client.post(
        "/api/v1/auth/register",
        json={"username": "testuser2", "password": "testpassword"},
    )
    # Then, try to create the same user again
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "testuser2", "password": "testpassword"},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Username already registered"}


async def test_login_for_access_token(client: TestClient):
    # First, create a user
    user = UserCreate(username="testuser3", password="testpassword")
    client.post(
        "/api/v1/auth/register",
        json={"username": user.username, "password": user.password},
    )

    # Then, log in
    response = client.post(
        "/api/v1/auth/login",
        data={"username": user.username, "password": user.password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_incorrect_password(client: TestClient):
    # First, create a user
    user = UserCreate(username="testuser4", password="testpassword")
    client.post(
        "/api/v1/auth/register",
        json={"username": user.username, "password": user.password},
    )

    # Then, try to log in with the wrong password
    response = client.post(
        "/api/v1/auth/login",
        data={"username": user.username, "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}
