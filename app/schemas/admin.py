from pydantic import BaseModel
from typing import List, Optional, Dict

class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    phone: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None

class PropertyResponse(BaseModel):
    id: str
    title: str
    location: str
    status: str
    owner_id: str
    price: float
    lat: Optional[float]
    lon: Optional[float]

class ReportResponse(BaseModel):
    title: str
    data: dict

class MetricsTotalsResponse(BaseModel):
    total_users: int
    total_properties: int
    total_payments: int
    total_services: int
    healthy_services: int
    properties_by_type: Dict[str, int] | None = None
    properties_by_status: Dict[str, int] | None = None

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total_users: int
