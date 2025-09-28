from pydantic import BaseModel, Field
from typing import Literal, List, Optional

class Location(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: List[float]  # [lng, lat]

class Accessibility(BaseModel):
    threshold: int
    entrance: int
    door: int
    confidence: float = 0.0
    modelVersion: Optional[str] = None
    updatedAt: Optional[str] = None
    source: Optional[Literal["model","user","mixed"]] = "model"

class PlaceIn(BaseModel):
    name: str
    location: Location
    accessibility: Accessibility
    imageUrl: Optional[str] = None
    source: Optional[str] = "streetview"

def serialize_doc(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc
