from httpx import AsyncClient
from app.config import settings
from structlog import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import insert
from app.models.admin_log import AdminLog
from redis.asyncio import Redis

logger = get_logger()

async def get_users():
    async with AsyncClient() as client:
        response = await client.get(
            f"{settings.USER_MANAGEMENT_URL}/api/v1/users",
            headers={"Authorization": f"Bearer {settings.USER_TOKEN}"}
        )
        response.raise_for_status()
        return response.json()

async def update_user(user_id: str, data: dict):
    async with AsyncClient() as client:
        response = await client.put(
            f"{settings.USER_MANAGEMENT_URL}/api/v1/users/{user_id}",
            json=data,
            headers={"Authorization": f"Bearer {settings.USER_TOKEN}"}
        )
        response.raise_for_status()
        return response.json()

async def get_properties():
    async with AsyncClient() as client:
        response = await client.get(
            f"{settings.PROPERTY_LISTING_URL}/api/v1/properties",
            headers={"Authorization": f"Bearer {settings.PROPERTY_TOKEN}"}
        )
        response.raise_for_status()
        return response.json()

async def approve_property(property_id: str, admin_id: str): # Added admin_id here
    async with AsyncClient() as client:
        response = await client.post(
            f"{settings.PROPERTY_LISTING_URL}/api/v1/properties/{property_id}/approve",
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
