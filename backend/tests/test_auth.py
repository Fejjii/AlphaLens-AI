from __future__ import annotations

from httpx import AsyncClient


async def test_register_user(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={
            "email": "register@example.com",
            "password": "Password123!",
            "full_name": "Register User",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "register@example.com"


async def test_login_user(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "Password123!",
            "full_name": "Login User",
        },
    )
    response = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "Password123!"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["full_name"] == "Login User"


async def test_reject_invalid_password(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={
            "email": "invalid-password@example.com",
            "password": "Password123!",
            "full_name": "Invalid Password User",
        },
    )
    response = await client.post(
        "/auth/login",
        json={"email": "invalid-password@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


async def test_auth_me_works_with_token(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test.user@example.com"


async def test_protected_route_rejects_missing_token(client: AsyncClient) -> None:
    response = await client.get("/approvals")
    assert response.status_code == 401


async def test_protected_route_works_with_token(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/usage/summary", headers=auth_headers)
    assert response.status_code == 200
