from pydantic import BaseModel
from typing import List, Optional

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
