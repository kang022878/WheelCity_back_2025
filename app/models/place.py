from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Tuple

class GeoPoint(BaseModel):
    type: str = Field(default="Point", pattern="^Point$")
    coordinates: Tuple[float, float]  # (longitude, latitude)

class PlaceIn(BaseModel):
    name: str
    address: Optional[str] = None
    location: GeoPoint                  # GeoJSON 포맷 필수 (2dsphere 인덱스용)
    types: Optional[List[str]] = None   # 예: ["cafe","restaurant"]
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, str]] = None
