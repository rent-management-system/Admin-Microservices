from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from httpx import AsyncClient
from app.config import settings
from app.schemas.property import PropertyListResponse, PropertyResponse
from structlog import get_logger

logger = get_logger()
router = APIRouter(prefix="/api/v1/properties", tags=["properties"])

# Normalize base and prefixes from environment
_prop_base = settings.PROPERTY_LISTING_URL.rstrip("/")
if "/docs" in _prop_base:
    _prop_base = _prop_base.replace("/docs", "")
_prop_has_v1 = _prop_base.endswith("/api/v1")
_prop_prefix = "" if _prop_has_v1 else "/api/v1"

@router.get("/public", response_model=PropertyListResponse)
async def get_all_properties_public(
    location: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    amenities: Optional[List[str]] = Query(None),
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
):
    """
    Public list endpoint to get all approved properties, with filtering and pagination.
    """
    params = {
        "location": location,
        "min_price": min_price,
        "max_price": max_price,
        "amenities": amenities,
        "search": search,
        "offset": offset,
        "limit": limit,
        "status": "approved" # Only fetch approved properties for public endpoint
    }
    # Remove None values from params
    params = {k: v for k, v in params.items() if v is not None}

    async with AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{_prop_base}{_prop_prefix}/properties",
                headers={"Authorization": f"Bearer {settings.PROPERTY_TOKEN}"},
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            # Assuming the upstream service returns a list of properties directly
            # or an object with 'items' and 'total'
            if isinstance(data, dict) and "items" in data and "total" in data:
                properties = data["items"]
                total = data["total"]
            elif isinstance(data, list):
                properties = data
                total = len(data) # Fallback if upstream doesn't provide total
            else:
                properties = []
                total = 0
            
            logger.info("Fetched public properties", total_properties=total)
            return {"total": total, "items": properties}
        except Exception as e:
            logger.error("Error fetching public properties from upstream", error=str(e))
            raise HTTPException(status_code=502, detail=f"Error fetching properties: {e}")

@router.get("/public/{property_id}", response_model=PropertyResponse)
async def get_property_public(property_id: str):
    """
    Public endpoint to get full details for a single approved property by ID.
    """
    async with AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{_prop_base}{_prop_prefix}/properties/{property_id}",
            )
            response.raise_for_status()
            property_data = response.json()

            if property_data.get("status", "").lower() != "approved":
                raise HTTPException(status_code=404, detail="Property not found or not approved")
            
            logger.info("Fetched public property details", property_id=property_id)
            return property_data
        except HTTPException:
            raise # Re-raise our own HTTPException
        except Exception as e:
            logger.error("Error fetching public property from upstream", property_id=property_id, error=str(e))
            raise HTTPException(status_code=502, detail=f"Error fetching property details: {e}")
