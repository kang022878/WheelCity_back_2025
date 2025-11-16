from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional, Sequence

from bson import ObjectId
from pydantic import BaseModel, Field, HttpUrl, validator


class GeoPoint(BaseModel):
    """GeoJSON point helper that ensures [lng, lat] ordering."""

    type: Literal["Point"] = "Point"
    coordinates: Sequence[float] = Field(..., min_items=2, max_items=2)

    @validator("coordinates")
    def validate_coordinates(cls, value: Sequence[float]) -> Sequence[float]:
        if len(value) != 2:
            raise ValueError("GeoJSON Point coordinates must contain [lng, lat]")
        return value


class UserBase(BaseModel):
    wheelchair_type: Literal["manual", "auto"]
    max_height_cm: int = Field(..., ge=0)
    last_location: Optional[GeoPoint] = None
    review_score: float = Field(0.0, ge=0)


class UserCreate(UserBase):
    auth_id: str


class UserUpdate(BaseModel):
    wheelchair_type: Optional[Literal["manual", "auto"]] = None
    max_height_cm: Optional[int] = Field(None, ge=0)
    last_location: Optional[GeoPoint] = None
    review_score: Optional[float] = Field(None, ge=0)


class AIPrediction(BaseModel):
    ramp: bool
    curb: bool
    image_url: Optional[HttpUrl] = None


class AverageScores(BaseModel):
    enter_success_rate: float = Field(0.0, ge=0, le=1)
    alone_entry_rate: float = Field(0.0, ge=0, le=1)
    comfort_rate: float = Field(0.0, ge=0, le=1)
    ai_accuracy_rate: float = Field(0.0, ge=0, le=1)


class ShopCreate(BaseModel):
    name: str
    location: GeoPoint
    ai_prediction: Optional[AIPrediction] = None
    needPhotos: bool = False
    ai_recheck_date: Optional[datetime] = None


class ShopUpdateAI(BaseModel):
    ramp: bool
    curb: bool
    image_url: Optional[HttpUrl] = None


class AIPredictionRequest(BaseModel):
    """Request to analyze an image and generate AI prediction"""
    image_url: HttpUrl


class ReviewAICorrect(BaseModel):
    ramp: bool
    curb: bool


class ReviewCreate(BaseModel):
    user_id: str
    enter: bool
    alone: bool
    comfort: bool
    ai_correct: ReviewAICorrect
    photo_urls: List[HttpUrl] = []
    review_text: Optional[str] = None


class S3UploadRequest(BaseModel):
    files: List[str] = Field(..., min_length=1)


def _stringify(val):
    """Convert MongoDB types to JSON-serializable types."""
    if isinstance(val, ObjectId):
        return str(val)
    elif isinstance(val, datetime):
        return val.isoformat()
    return val


def serialize_doc(doc: dict) -> dict:
    """Convert Mongo ObjectIds and other types to JSON-serializable formats."""
    if not isinstance(doc, dict):
        return doc
    
    # Create a copy to avoid mutating the original
    result = {}
    for key, value in doc.items():
        if isinstance(value, dict):
            result[key] = serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [serialize_doc(item) if isinstance(item, dict) else _stringify(item) for item in value]
        else:
            result[key] = _stringify(value)
    return result
