from pydantic import BaseModel
from typing import List, Optional

class PropertyResponse(BaseModel):
    id: str
    title: str
    location: str
    status: str
    owner_id: Optional[str] = None
    price: float
    lat: Optional[float]
    lon: Optional[float]

class PropertyListResponse(BaseModel):
    total: int
    items: List[PropertyResponse]
