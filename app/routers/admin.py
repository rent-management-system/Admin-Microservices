from fastapi import APIRouter, Depends, HTTPException
from fastapi_limiter.depends import RateLimiter
from app.schemas.admin import UserResponse, PropertyResponse, ReportResponse
from app.services.admin import get_users, get_user_by_id, update_user, get_properties, approve_property, get_health
from app.services.reporting import generate_user_report, export_report
from app.dependencies.auth import get_current_admin, oauth2_scheme
from structlog import get_logger
from typing import List

logger = get_logger()
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

@router.get("/users", response_model=List[UserResponse], dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def list_users(skip: int = 0, limit: int = 100, admin: dict = Depends(get_current_admin), token: str = Depends(oauth2_scheme)):
    users = await get_users(token, skip=skip, limit=limit)
    await logger.info("Fetched users", admin_id=admin["id"])
    return users

@router.get("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def get_user_detail(user_id: str, admin: dict = Depends(get_current_admin), token: str = Depends(oauth2_scheme)):
    user = await get_user_by_id(user_id, token)
    await logger.info("Fetched user detail", user_id=user_id, admin_id=admin["id"])
    return user

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user_endpoint(user_id: str, data: dict, admin: dict = Depends(get_current_admin), token: str = Depends(oauth2_scheme)):
    user = await update_user(user_id, data, token)
    await logger.info("Updated user", user_id=user_id, admin_id=admin["id"])
    return user

@router.get("/properties", response_model=List[PropertyResponse])
async def list_properties(admin: dict = Depends(get_current_admin), token: str = Depends(oauth2_scheme)):
    properties = await get_properties(token)
    await logger.info("Fetched properties", admin_id=admin["id"])
    return properties

@router.post("/properties/{property_id}/approve")
async def approve_property_endpoint(property_id: str, admin: dict = Depends(get_current_admin)):
    await approve_property(property_id, admin["id"])
    await logger.info("Approved property", property_id=property_id, admin_id=admin["id"])
    return {"status": "success"}

@router.get("/health")
async def check_health(admin: dict = Depends(get_current_admin)):
    health = await get_health()
    await logger.info("Fetched health status", admin_id=admin["id"])
    return health

@router.get("/reports/users", response_model=ReportResponse)
async def user_report(lang: str = "en", admin: dict = Depends(get_current_admin)):
    report = await generate_user_report(lang)
    await logger.info("Generated user report", lang=lang, admin_id=admin["id"])
    return report

@router.get("/reports/export/{type}")
async def export_report_endpoint(type: str, lang: str = "en", admin: dict = Depends(get_current_admin)):
    file_url = await export_report(type, lang)
    await logger.info("Exported report", type=type, lang=lang, admin_id=admin["id"])
    return {"file_url": file_url}
