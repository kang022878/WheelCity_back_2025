from __future__ import annotations

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
    return str(val) if isinstance(val, ObjectId) else val


def serialize_doc(doc: dict) -> dict:
    """Convert Mongo ObjectIds to strings for API responses."""
    if "_id" in doc:
        doc["_id"] = _stringify(doc["_id"])
    if "shop_id" in doc:
        doc["shop_id"] = _stringify(doc["shop_id"])
    if "user_id" in doc:
        doc["user_id"] = _stringify(doc["user_id"])
    return doc
