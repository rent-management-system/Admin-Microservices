from fastapi import APIRouter, Depends, HTTPException
from fastapi_limiter.depends import RateLimiter
from app.schemas.admin import UserResponse, PropertyResponse, ReportResponse, MetricsTotalsResponse, UserListResponse, UserUpdateRequest
from app.services.admin import get_users, get_user_by_id, update_user, get_properties, approve_property, get_health, get_property_metrics, get_payment_metrics, get_payment_health, get_search_health, get_ai_health, get_dashboard_totals
from app.services.reporting import generate_user_report, export_report
from app.dependencies.auth import get_current_admin, oauth2_scheme
from structlog import get_logger
from typing import List

logger = get_logger()
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

@router.get("/users", response_model=UserListResponse, dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def list_users(skip: int = 0, limit: int = 100, admin: dict = Depends(get_current_admin), token: str = Depends(oauth2_scheme)):
    users = await get_users(token, skip=skip, limit=limit)
    total_users = len(users)
    logger.info("Fetched users", admin_id=admin["id"])
    return {"users": users, "total_users": total_users}

@router.get("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def get_user_detail(user_id: str, admin: dict = Depends(get_current_admin), token: str = Depends(oauth2_scheme)):
    user = await get_user_by_id(user_id, token)
    logger.info("Fetched user detail", user_id=user_id, admin_id=admin["id"])
    return user

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user_endpoint(user_id: str, data: UserUpdateRequest, admin: dict = Depends(get_current_admin), token: str = Depends(oauth2_scheme)):
    user = await update_user(user_id, data.model_dump(exclude_unset=True), token)
    logger.info("Updated user", user_id=user_id, admin_id=admin["id"])
    return user

@router.get("/properties", response_model=List[PropertyResponse])
async def list_properties(
    location: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    amenities: List[str] | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 20,
):
    properties = await get_properties(
        location=location,
        min_price=min_price,
        max_price=max_price,
        amenities=amenities,
        search=search,
        offset=offset,
        limit=limit,
    )
    logger.info("Fetched properties")
    return properties

@router.post("/properties/{property_id}/approve")
async def approve_property_endpoint(property_id: str, admin: dict = Depends(get_current_admin)):
    await approve_property(property_id, admin["id"])
    logger.info("Approved property", property_id=property_id, admin_id=admin["id"])
    return {"status": "success"}

@router.get("/health")
async def check_health(verbose: bool = False):
    """Unified health endpoint. Use verbose=true to include tried URLs."""
    health = await get_health(verbose=verbose)
    logger.info("Fetched health status", verbose=verbose)
    return health

@router.get("/properties/metrics")
async def properties_metrics():
    metrics = await get_property_metrics()
    logger.info("Fetched property metrics")
    return metrics

@router.get("/payments/metrics")
async def payment_service_metrics():
    """Non-auth proxy to payment service metrics endpoint."""
    status = await get_payment_metrics()
    logger.info("Fetched payment metrics", status_code=status.get("status_code"))
    return status

# Aggregated totals for dashboard widgets
@router.get("/metrics/totals", response_model=MetricsTotalsResponse, dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def metrics_totals(admin: dict = Depends(get_current_admin), token: str = Depends(oauth2_scheme)):
    totals = await get_dashboard_totals(token)
    logger.info("Fetched dashboard totals", admin_id=admin["id"])
    return totals

# Backward-compatible alias: some clients may still call /ai/health
@router.get("/ai/health")
async def ai_service_health_alias():
    """Backward-compatible health proxy for the AI recommendation service.
    Prefer using the unified /api/v1/admin/health endpoint.
    """
    status = await get_ai_health()
    logger.info("Fetched AI recommendation health (alias)", status_code=status.get("status_code"))
    return status

# Backward-compatible alias: some clients may still call /payments/health
@router.get("/payments/health")
async def payment_service_health_alias():
    """Backward-compatible health proxy for the payment service.
    Prefer using the unified /api/v1/admin/health endpoint.
    """
    status = await get_payment_health()
    logger.info("Fetched payment health (alias)", status_code=status.get("status_code"))
    return status

# Backward-compatible alias: some clients may still call /search/health
@router.get("/search/health")
async def search_service_health_alias():
    """Backward-compatible health proxy for the search/filters service.
    Prefer using the unified /api/v1/admin/health endpoint.
    """
    status = await get_search_health()
    logger.info("Fetched search health (alias)", status_code=status.get("status_code"))
    return status

@router.get("/reports/users", response_model=ReportResponse)
async def user_report(lang: str = "en", admin: dict = Depends(get_current_admin), token: str = Depends(oauth2_scheme)):
    report = await generate_user_report(lang, token)
    # Wrap into ReportResponse schema: title and data
    title = report.get("title", "User Report") if isinstance(report, dict) else "User Report"
    data = report if isinstance(report, dict) else {"report": report}
    if isinstance(data, dict) and "title" in data:
        data = {k: v for k, v in data.items() if k != "title"}
    logger.info("Generated user report", lang=lang, admin_id=admin["id"])
    return {"title": title, "data": data}

@router.get("/reports/export/{type}")
async def export_report_endpoint(type: str, lang: str = "en", admin: dict = Depends(get_current_admin)):
    file_url = await export_report(type, lang)
    logger.info("Exported report", type=type, lang=lang, admin_id=admin["id"])
    return {"file_url": file_url}
