from pydantic import BaseModel, Field
from typing import Literal, List, Optional
from datetime import datetime

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

# Image and Accessibility Analysis Models
class ImageUpload(BaseModel):
    filename: str
    content_type: str
    size: int
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

class ImageMetadata(BaseModel):
    image_id: str
    filename: str
    s3_key: str
    s3_url: str
    content_type: str
    size: int
    uploaded_at: datetime
    analyzed: bool = False

class AccessibilityAnalysis(BaseModel):
    accessible: Optional[bool] = None
    reason: str
    confidence: Optional[float] = None
    model_version: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

class ImageAnalysisResult(BaseModel):
    image_id: str
    analysis: AccessibilityAnalysis
    processing_time: Optional[float] = None
    yolov8_detections: Optional[List[dict]] = None

class ImageUploadResponse(BaseModel):
    image_id: str
    s3_url: str
    message: str

class AnalysisRequest(BaseModel):
    image_id: str
    force_reanalyze: bool = False

def serialize_doc(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc
