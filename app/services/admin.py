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

async def get_payment_health():
    base = settings.PAYMENT_URL.rstrip("/")
    async with AsyncClient() as client:
        # Prefer explicit /api/v1/health if base includes /api/v1; otherwise try /health
        url = f"{base}/health"
        resp = await client.get(url)
        # Fallback: if base ends with /api/v1 and first attempt fails, try root /health
        if resp.status_code >= 400 and base.endswith("/api/v1"):
            root = base[: -len("/api/v1")]
            resp = await client.get(f"{root}/health")
        try:
            data = resp.json()
        except Exception:
            data = resp.text or "ok"
        return {"status_code": resp.status_code, "data": data}

async def get_ai_health():
    base = settings.AI_RECOMMENDATION_URL.rstrip("/")
    async with AsyncClient() as client:
        url = f"{base}/health"
        resp = await client.get(url)
        if resp.status_code >= 400 and base.endswith("/api/v1"):
            root = base[: -len("/api/v1")]
            resp = await client.get(f"{root}/health")
        try:
            data = resp.json()
        except Exception:
            data = resp.text or "ok"
        return {"status_code": resp.status_code, "data": data}

async def get_search_health():
    base = settings.SEARCH_FILTERS_URL.rstrip("/")
    async with AsyncClient() as client:
        url = f"{base}/health"
        resp = await client.get(url)
        # No special /api/v1 logic unless base includes it
        if resp.status_code >= 400 and base.endswith("/api/v1"):
            root = base[: -len("/api/v1")]
            resp = await client.get(f"{root}/health")
        try:
            data = resp.json()
        except Exception:
            data = resp.text or "ok"
        return {"status_code": resp.status_code, "data": data}

async def get_payment_metrics():
    base = settings.PAYMENT_URL.rstrip("/")
    async with AsyncClient() as client:
        url = f"{base}/metrics"
        resp = await client.get(url)
        if resp.status_code >= 400 and base.endswith("/api/v1"):
            root = base[: -len("/api/v1")]
            resp = await client.get(f"{root}/metrics")
        try:
            data = resp.json()
        except Exception:
            data = resp.text or "ok"
        return {"status_code": resp.status_code, "data": data}

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

async def get_properties(
    location: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    amenities: list[str] | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 20,
):
    params = {
        "location": location,
        "min_price": min_price,
        "max_price": max_price,
        "search": search,
        "offset": offset,
        "limit": limit,
    }
    # Handle amenities list: property listing often expects repeated query params or comma-separated.
    # We'll send as repeated params if provided.
    async with AsyncClient() as client:
        if amenities:
            # httpx will encode list values as repeated params when a list is provided
            params_with_amenities = {**params, "amenities": amenities}
        else:
            params_with_amenities = params
        response = await client.get(
            f"{_prop_base}{_prop_prefix}/properties",
            headers={"Authorization": f"Bearer {settings.PROPERTY_TOKEN}"},
            params=params_with_amenities,
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
                service_url = getattr(settings, service_url_key).rstrip("/")
                # First try '<base>/health'
                resp = await client.get(f"{service_url}/health")
                if resp.status_code >= 400:
                    # If base endswith '/api/v1', retry without it for '/health'
                    if service_url.endswith("/api/v1"):
                        root_base = service_url[: -len("/api/v1")]
                        resp = await client.get(f"{root_base}/health")
                # Parse JSON if possible; otherwise keep plain text
                try:
                    health_payload = resp.json()
                except Exception:
                    health_payload = {"message": (resp.text or "ok")}
                health[service] = {"status_code": resp.status_code, "data": health_payload}
            except Exception as e:
                health[service] = {"status": "error", "error": str(e)}
    return health

async def get_property_metrics():
    async with AsyncClient() as client:
        response = await client.get(
            f"{_prop_base}{_prop_prefix}/properties/metrics",
            headers={"Authorization": f"Bearer {settings.PROPERTY_TOKEN}"}
        )
        response.raise_for_status()
        return response.json()
