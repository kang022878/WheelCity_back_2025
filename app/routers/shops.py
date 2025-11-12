import logging
from typing import List, Optional

import requests
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.db import db
from app.deps import verify_internal
from app.models import AIPredictionRequest, AverageScores, ShopCreate, ShopUpdateAI, serialize_doc
from app.services.gemini_service import get_gemini_service
from app.services.yolov8_service import yolov8_service

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db() -> AsyncIOMotorDatabase:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    return db


async def _fetch_average_scores(database: AsyncIOMotorDatabase, shop_id: ObjectId) -> AverageScores:
    pipeline = [
        {"$match": {"shop_id": shop_id}},
        {
            "$group": {
                "_id": "$shop_id",
                "enter_success_rate": {"$avg": {"$cond": ["$enter", 1, 0]}},
                "alone_entry_rate": {"$avg": {"$cond": ["$alone", 1, 0]}},
                "comfort_rate": {"$avg": {"$cond": ["$comfort", 1, 0]}},
                "ai_accuracy_rate": {
                    "$avg": {
                        "$divide": [
                            {
                                "$add": [
                                    {"$cond": [{"$eq": ["$ai_correct.ramp", True]}, 1, 0]},
                                    {"$cond": [{"$eq": ["$ai_correct.curb", True]}, 1, 0]},
                                ]
                            },
                            2,
                        ]
                    }
                },
            }
        },
    ]
    cursor = database.reviews.aggregate(pipeline)
    agg = await cursor.to_list(1)
    if not agg:
        return AverageScores()
    record = agg[0]
    return AverageScores(
        enter_success_rate=record.get("enter_success_rate", 0.0) or 0.0,
        alone_entry_rate=record.get("alone_entry_rate", 0.0) or 0.0,
        comfort_rate=record.get("comfort_rate", 0.0) or 0.0,
        ai_accuracy_rate=record.get("ai_accuracy_rate", 0.0) or 0.0,
    )


def _oid(id_str: str) -> ObjectId:
    if not ObjectId.is_valid(id_str):
        raise HTTPException(status_code=400, detail="Invalid id")
    return ObjectId(id_str)


@router.post("/", dependencies=[Depends(verify_internal)], summary="Create a new shop")
async def create_shop(payload: ShopCreate, database: AsyncIOMotorDatabase = Depends(get_db)):
    doc = payload.model_dump()
    result = await database.shops.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.get("/{shop_id}", summary="Get shop details")
async def get_shop(shop_id: str, database: AsyncIOMotorDatabase = Depends(get_db)):
    oid = _oid(shop_id)
    shop = await database.shops.find_one({"_id": oid})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    scores = await _fetch_average_scores(database, oid)
    response = serialize_doc(shop)
    response["average_scores"] = scores.dict()
    return response


@router.get("/nearby", summary="Find nearby shops using geospatial query")
async def nearby_shops(
    lat: float = Query(...),
    lng: float = Query(...),
    radius: int = Query(800, ge=0),
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    query = {
        "location": {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                "$maxDistance": radius,
            }
        }
    }
    cursor = database.shops.find(query)
    results = []
    async for doc in cursor:
        results.append(serialize_doc(doc))
    return results


@router.get("/search", summary="Search shops by text")
async def search_shops(
    text: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = (
        database.shops.find({"name": {"$regex": text, "$options": "i"}})
        .limit(limit)
    )
    items = []
    async for doc in cursor:
        items.append(serialize_doc(doc))
    return {"items": items, "count": len(items)}


@router.post(
    "/{shop_id}/ai-prediction",
    dependencies=[Depends(verify_internal)],
    summary="Analyze image and store AI prediction for a shop",
)
async def analyze_and_update_ai_prediction(
    shop_id: str,
    payload: AIPredictionRequest,
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Analyze an image URL using YOLOv8 and Gemini, then store the AI prediction.
    The image should already be uploaded to S3 by the frontend.
    """
    oid = _oid(shop_id)
    
    # Verify shop exists
    shop = await database.shops.find_one({"_id": oid})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    try:
        # Download image from S3 URL
        image_url = str(payload.image_url)
        logger.info(f"Downloading image from {image_url}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        image_bytes = response.content
        
        # Run YOLOv8 analysis
        logger.info("Running YOLOv8 analysis...")
        yolov8_features = await yolov8_service.analyze_accessibility_features(image_bytes)
        
        # Extract entrance region if detected for better Gemini analysis
        entrance_image = None
        if yolov8_features.get("entrance_detected", False):
            entrance_image = await yolov8_service.extract_entrance_region(
                image_bytes, yolov8_features.get("detections", [])
            )
        
        # Use entrance region for Gemini analysis if available, otherwise use full image
        analysis_image = entrance_image if entrance_image else image_bytes
        filename = image_url.split("/")[-1] if "/" in image_url else "image.jpg"
        
        # Run Gemini analysis
        logger.info("Running Gemini analysis...")
        gemini = get_gemini_service()
        gemini_result = await gemini.analyze_accessibility(analysis_image, filename)
        
        # Convert analysis results to AIPrediction format
        # ramp: True if ramp detected OR if accessible (no curbs/steps)
        # curb: True if stairs/curbs detected AND no ramp
        ramp_detected = yolov8_features.get("ramp_detected", False)
        stairs_detected = yolov8_features.get("stairs_detected", False)
        is_accessible = gemini_result.get("accessible", False)
        
        # Determine ramp and curb based on detections and accessibility
        has_ramp = ramp_detected or (is_accessible and not stairs_detected)
        has_curb = stairs_detected and not ramp_detected
        
        # Create AI prediction
        ai_prediction = ShopUpdateAI(
            ramp=has_ramp,
            curb=has_curb,
            image_url=payload.image_url
        )
        
        # Update shop with AI prediction
        update_doc = {"ai_prediction": ai_prediction.model_dump()}
        res = await database.shops.find_one_and_update(
            {"_id": oid},
            {"$set": update_doc},
            return_document=ReturnDocument.AFTER,
        )
        
        logger.info(f"AI prediction updated for shop {shop_id}: ramp={has_ramp}, curb={has_curb}")
        return serialize_doc(res)
        
    except requests.RequestException as e:
        logger.error(f"Failed to download image: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to download image from URL: {str(e)}")
    except Exception as e:
        logger.error(f"AI prediction analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

