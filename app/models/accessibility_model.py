from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime

class AccessibilityData(BaseModel):
    place_id: str
    image_url: str
    detected_features: Dict[str, bool]
    confidence_scores: Dict[str, float]
    overall_accessibility_score: float
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: Optional[str] = None
