import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from bson import ObjectId
from app.db import db
from app.models import (
    ImageMetadata, 
    ImageUploadResponse, 
    ImageAnalysisResult, 
    AccessibilityAnalysis,
    AnalysisRequest
)
from app.services.s3_service import get_s3_service, S3Service
from app.services.gemini_service import get_gemini_service, GeminiService
from app.services.yolov8_service import yolov8_service
from app.deps import verify_internal
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Supported image formats
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    place_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    s3: S3Service = Depends(get_s3_service)
):
    """
    Upload a review/campaign image to S3
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Check file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format. Supported: {', '.join(SUPPORTED_FORMATS)}"
            )
        
        # Read file content
        content = await file.read()
        
        # Check file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Upload to S3
        upload_result = await s3.upload_image(
            file_content=content,
            filename=file.filename,
            content_type=file.content_type or "image/jpeg"
        )
        
        # Store metadata in MongoDB
        image_metadata = ImageMetadata(
            image_id=upload_result["image_id"],
            filename=upload_result["filename"],
            s3_key=upload_result["s3_key"],
            s3_url=upload_result["s3_url"],
            content_type=upload_result["content_type"],
            size=upload_result["size"],
            uploaded_at=upload_result["uploaded_at"],
            analyzed=False
        )
        
        # Add optional fields if provided
        metadata_doc = image_metadata.model_dump()
        if place_id:
            metadata_doc["place_id"] = place_id
        if user_id:
            metadata_doc["user_id"] = user_id
        
        await db.images.insert_one(metadata_doc)
        
        return ImageUploadResponse(
            image_id=upload_result["image_id"],
            s3_url=upload_result["s3_url"],
            message="Image uploaded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/analyze", response_model=ImageAnalysisResult)
async def analyze_image(request: AnalysisRequest, gemini: GeminiService = Depends(get_gemini_service)):
    """
    Analyze uploaded image for accessibility using Gemini API
    """
    try:
        # Get image metadata
        image_doc = await db.images.find_one({"image_id": request.image_id})
        if not image_doc:
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Check if already analyzed (unless force reanalyze)
        if image_doc.get("analyzed", False) and not request.force_reanalyze:
            # Return existing analysis
            existing_analysis = await db.image_analyses.find_one({"image_id": request.image_id})
            if existing_analysis:
                return ImageAnalysisResult(
                    image_id=request.image_id,
                    analysis=AccessibilityAnalysis(**existing_analysis["analysis"]),
                    processing_time=existing_analysis.get("processing_time"),
                    yolov8_detections=existing_analysis.get("yolov8_detections")
                )
        
        # Download image from S3 for analysis
        # Note: In production, you might want to stream the image directly from S3
        # For now, we'll assume the image is accessible via the S3 URL
        import requests
        
        try:
            response = requests.get(image_doc["s3_url"], timeout=30)
            response.raise_for_status()
            image_bytes = response.content
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to download image: {str(e)}")
        
        # Preprocess with YOLOV8 (if available)
        yolov8_features = await yolov8_service.analyze_accessibility_features(image_bytes)
        
        # Extract entrance region if detected
        entrance_image = None
        if yolov8_features.get("entrance_detected", False):
            entrance_image = await yolov8_service.extract_entrance_region(
                image_bytes, yolov8_features["detections"]
            )
        
        # Use entrance region for Gemini analysis if available, otherwise use full image
        analysis_image = entrance_image if entrance_image else image_bytes
        
        # Analyze with Gemini
        analysis_result = await gemini.analyze_accessibility(
            image_bytes=analysis_image,
            filename=image_doc["filename"]
        )
        
        # Create analysis document
        analysis_doc = {
            "image_id": request.image_id,
            "analysis": {
                "accessible": analysis_result["accessible"],
                "reason": analysis_result["reason"],
                "confidence": analysis_result.get("confidence"),
                "model_version": analysis_result.get("model_version"),
                "analyzed_at": analysis_result.get("analyzed_at")
            },
            "processing_time": analysis_result.get("processing_time"),
            "yolov8_detections": yolov8_features,
            "created_at": analysis_result.get("analyzed_at")
        }
        
        # Store analysis result
        await db.image_analyses.insert_one(analysis_doc)
        
        # Update image metadata
        await db.images.update_one(
            {"image_id": request.image_id},
            {"$set": {"analyzed": True, "analyzed_at": analysis_result.get("analyzed_at")}}
        )
        
        return ImageAnalysisResult(
            image_id=request.image_id,
            analysis=AccessibilityAnalysis(**analysis_doc["analysis"]),
            processing_time=analysis_doc["processing_time"],
            yolov8_detections=analysis_doc["yolov8_detections"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/{image_id}")
async def get_image_metadata(image_id: str):
    """
    Get image metadata and analysis results
    """
    try:
        # Get image metadata
        image_doc = await db.images.find_one({"image_id": image_id})
        if not image_doc:
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Get analysis if exists
        analysis_doc = await db.image_analyses.find_one({"image_id": image_id})
        
        result = {
            "image_id": image_doc["image_id"],
            "filename": image_doc["filename"],
            "s3_url": image_doc["s3_url"],
            "content_type": image_doc["content_type"],
            "size": image_doc["size"],
            "uploaded_at": image_doc["uploaded_at"],
            "analyzed": image_doc.get("analyzed", False),
            "analysis": None
        }
        
        if analysis_doc:
            result["analysis"] = {
                "accessible": analysis_doc["analysis"]["accessible"],
                "reason": analysis_doc["analysis"]["reason"],
                "confidence": analysis_doc["analysis"].get("confidence"),
                "model_version": analysis_doc["analysis"].get("model_version"),
                "analyzed_at": analysis_doc["analysis"].get("analyzed_at"),
                "processing_time": analysis_doc.get("processing_time")
            }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get image metadata error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get image metadata: {str(e)}")

@router.delete("/{image_id}")
async def delete_image(
    image_id: str,
    dependencies=[Depends(verify_internal)],
    s3: S3Service = Depends(get_s3_service)
):
    """
    Delete image from S3 and database (internal use only)
    """
    try:
        # Get image metadata
        image_doc = await db.images.find_one({"image_id": image_id})
        if not image_doc:
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Delete from S3
        s3_deleted = await s3.delete_image(image_doc["s3_key"])
        
        # Delete from database
        await db.images.delete_one({"image_id": image_id})
        await db.image_analyses.delete_one({"image_id": image_id})
        
        return {
            "message": "Image deleted successfully",
            "s3_deleted": s3_deleted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete image error: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@router.get("/")
async def list_images(
    skip: int = 0,
    limit: int = 20,
    analyzed_only: bool = False
):
    """
    List uploaded images with optional filtering
    """
    try:
        query = {}
        if analyzed_only:
            query["analyzed"] = True
        
        cursor = db.images.find(query).skip(skip).limit(limit).sort("uploaded_at", -1)
        images = []
        
        async for doc in cursor:
            images.append({
                "image_id": doc["image_id"],
                "filename": doc["filename"],
                "s3_url": doc["s3_url"],
                "size": doc["size"],
                "uploaded_at": doc["uploaded_at"],
                "analyzed": doc.get("analyzed", False)
            })
        
        return {
            "images": images,
            "total": await db.images.count_documents(query),
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"List images error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list images: {str(e)}")
