from pydantic import BaseModel
from typing import List, Optional

class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    phone: Optional[str]
    is_active: bool
    created_at: str

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
