import pytest
from httpx import AsyncClient
from app.main import app
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_list_users(monkeypatch):
    async def mock_get_users():
        return [{"id": "1", "email": "user@example.com", "role": "Owner", "phone": None, "is_active": True, "created_at": "2023-01-01T00:00:00"}]
    monkeypatch.setattr("app.services.admin.get_users", AsyncMock(return_value=mock_get_users()))
    
    async def mock_get_current_admin():
        return {"id": "admin_id", "role": "Admin"}
    monkeypatch.setattr("app.dependencies.auth.get_current_admin", mock_get_current_admin)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": "Bearer admin_jwt"}
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["email"] == "user@example.com"

@pytest.mark.asyncio
async def test_generate_user_report(monkeypatch):
    async def mock_generate_user_report(lang):
        return {"title": "User Report", "data": {"total_users": 10, "new_users_month": 2, "active_users": 8}}
    monkeypatch.setattr("app.services.reporting.generate_user_report", AsyncMock(return_value=mock_generate_user_report("en")))
    
    async def mock_get_current_admin():
        return {"id": "admin_id", "role": "Admin"}
    monkeypatch.setattr("app.dependencies.auth.get_current_admin", mock_get_current_admin)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/admin/reports/users?lang=en",
            headers={"Authorization": "Bearer admin_jwt"}
        )
        assert response.status_code == 200
        assert response.json()["title"] == "User Report"
        assert response.json()["data"]["total_users"] == 10

@pytest.mark.asyncio
async def test_approve_property(monkeypatch):
    async def mock_approve_property(property_id, admin_id):
        return {"status": "success"}
    monkeypatch.setattr("app.services.admin.approve_property", AsyncMock(return_value=mock_approve_property("123", "admin_id")))

    async def mock_get_current_admin():
        return {"id": "admin_id", "role": "Admin"}
    monkeypatch.setattr("app.dependencies.auth.get_current_admin", mock_get_current_admin)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/properties/123/approve",
            headers={"Authorization": "Bearer admin_jwt"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

@pytest.mark.asyncio
async def test_get_health(monkeypatch):
    async def mock_get_health():
        return {"user_management": {"status": "ok"}}
    monkeypatch.setattr("app.services.admin.get_health", AsyncMock(return_value=mock_get_health()))

    async def mock_get_current_admin():
        return {"id": "admin_id", "role": "Admin"}
    monkeypatch.setattr("app.dependencies.auth.get_current_admin", mock_get_current_admin)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/admin/health",
            headers={"Authorization": "Bearer admin_jwt"}
        )
        assert response.status_code == 200
        assert response.json()["user_management"]["status"] == "ok"
