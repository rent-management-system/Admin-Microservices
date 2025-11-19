from httpx import AsyncClient
from app.config import settings
from structlog import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import insert
from app.models.admin_log import AdminLog
from redis.asyncio import Redis

logger = get_logger()

# Normalize bases and prefixes from environment
_user_base = settings.USER_MANAGEMENT_URL.rstrip("/")
_user_has_v1 = _user_base.endswith("/api/v1")
_user_prefix = "" if _user_has_v1 else "/api/v1"

_prop_base = settings.PROPERTY_LISTING_URL.rstrip("/")
# A lot of gateways expose docs at /docs; ensure we don't keep that in API base
if "/docs" in _prop_base:
    _prop_base = _prop_base.replace("/docs", "")
_prop_has_v1 = _prop_base.endswith("/api/v1")
_prop_prefix = "" if _prop_has_v1 else "/api/v1"

async def get_users(admin_token: str, skip: int = 0, limit: int = 100):
    async with AsyncClient() as client:
        response = await client.get(
            f"{_user_base}{_user_prefix}/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"skip": skip, "limit": limit},
        )
        response.raise_for_status()
        return response.json()

async def update_user(user_id: str, data: dict, admin_token: str):
    async with AsyncClient() as client:
        response = await client.put(
            f"{_user_base}{_user_prefix}/admin/users/{user_id}",
            json=data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        response.raise_for_status()
        return response.json()

async def get_user_by_id(user_id: str, admin_token: str):
    async with AsyncClient() as client:
        response = await client.get(
            f"{_user_base}{_user_prefix}/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        response.raise_for_status()
        return response.json()

async def get_properties(admin_token: str):
    async with AsyncClient() as client:
        response = await client.get(
            f"{_prop_base}{_prop_prefix}/properties",
            headers={"Authorization": f"Bearer {settings.PROPERTY_TOKEN}"}
        )
        response.raise_for_status()
        return response.json()

async def approve_property(property_id: str, admin_id: str): 
    async with AsyncClient() as client:
        response = await client.post(
            f"{_prop_base}{_prop_prefix}/properties/{property_id}/approve",
            headers={"Authorization": f"Bearer {settings.PROPERTY_TOKEN}"}
        )
        response.raise_for_status()
        # Log action
        async with AsyncSession(create_async_engine(settings.DATABASE_URL)) as session:
            stmt = insert(AdminLog).values(
                admin_id=admin_id, action="property_approved", entity_id=property_id
            )
            await session.execute(stmt)
            await session.commit()

async def get_health():
    services = [
        "user_management", "property_listing", "payment_processing",
        "search_filters", "ai_recommendation", "notification"
    ]
    health = {}
    async with AsyncClient() as client:
        for service in services:
            try:
                # Dynamically get the URL from settings based on service name
                service_url_key = f"{service.upper()}_URL"
                service_url = getattr(settings, service_url_key)
                response = await client.get(
                    f"{service_url}/health"
                )
                health[service] = response.json()
            except Exception as e:
                health[service] = {"status": "error", "error": str(e)}
    return health
