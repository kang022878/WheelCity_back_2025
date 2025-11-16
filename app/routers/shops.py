import logging
import re
import sys
from typing import List, Optional

import requests
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from app.deps import verify_internal
from app.models import AIPredictionRequest, AverageScores, ShopCreate, ShopUpdateAI, serialize_doc
from app.services.gemini_service import get_gemini_service
from app.services.yolov8_service import yolov8_service

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db() -> AsyncIOMotorDatabase:
    print("[GET_DB] get_db() called", flush=True)
    # Import db module to access the current value (not the imported value at module load time)
    import app.db
    db = app.db.db
    if db is None:
        print("[GET_DB ERROR] Database is None!", flush=True)
        raise HTTPException(status_code=500, detail="Database not connected")
    print("[GET_DB] Returning database", flush=True)
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
    print(f"[SEARCH] FUNCTION CALLED - text: {text}, limit: {limit}", flush=True)
    try:
        print(f"[SEARCH] Searching shops with text: {text}, limit: {limit}", flush=True)
        logger.info(f"Searching shops with text: {text}, limit: {limit}")
        # Escape special regex characters to prevent injection
        escaped_text = re.escape(text)
        query = {"name": {"$regex": escaped_text, "$options": "i"}}
        print(f"[SEARCH] Query: {query}")
        logger.info(f"Query: {query}")
        
        # Test database connection first
        try:
            print("[SEARCH] Testing database ping...")
            await database.command("ping")
            print("[SEARCH] Database ping successful")
            logger.info("Database ping successful")
        except OperationFailure as e:
            error_code = e.code
            if error_code == 13:  # Unauthorized
                logger.error(f"MongoDB Authorization Error: {e}")
                raise HTTPException(
                    status_code=403,
                    detail=f"MongoDB authorization failed. Check your database user permissions. Error: {str(e)}"
                )
            else:
                logger.error(f"MongoDB Operation Error: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"MongoDB operation failed: {str(e)}"
                )
        except ServerSelectionTimeoutError as e:
            logger.error(f"MongoDB Connection Timeout: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Cannot connect to MongoDB. Check your connection string and network access. Error: {str(e)}"
            )
        
        print("[SEARCH] Executing find query...")
        cursor = database.shops.find(query).limit(limit)
        items = []
        count = 0
        print("[SEARCH] Iterating through cursor...")
        async for doc in cursor:
            count += 1
            print(f"[SEARCH] Processing document {count}")
            try:
                serialized = serialize_doc(doc)
                items.append(serialized)
                print(f"[SEARCH] Successfully serialized document {count}")
            except Exception as e:
                print(f"[SEARCH ERROR] Error serializing shop document (count={count}): {e}")
                logger.error(f"Error serializing shop document (count={count}): {e}", exc_info=True)
                # Skip this document and continue
                continue
        print(f"[SEARCH] Found {len(items)} shops")
        logger.info(f"Found {len(items)} shops")
        result = {"items": items, "count": len(items)}
        print(f"[SEARCH] Returning result with {len(items)} items")
        return result
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except OperationFailure as e:
        error_code = e.code
        print(f"[SEARCH ERROR] MongoDB Operation Failure: {e}, code: {error_code}")
        logger.error(f"MongoDB Operation Failure in search: {e}", exc_info=True)
        if error_code == 13:  # Unauthorized
            raise HTTPException(
                status_code=403,
                detail=f"MongoDB authorization failed. Your database user may not have permission to read from the 'shops' collection. Error: {str(e)}"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"MongoDB operation failed: {str(e)}"
            )
    except Exception as e:
        print(f"[SEARCH ERROR] Exception in search_shops: {type(e).__name__}: {e}")
        import traceback
        traceback_str = traceback.format_exc()
        print(f"[SEARCH ERROR] Traceback:\n{traceback_str}")
        logger.error(f"Error in search_shops: {e}", exc_info=True)
        logger.error(traceback_str)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/{shop_id}", summary="Get shop details")
async def get_shop(shop_id: str, database: AsyncIOMotorDatabase = Depends(get_db)):
    oid = _oid(shop_id)
    shop = await database.shops.find_one({"_id": oid})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    scores = await _fetch_average_scores(database, oid)
    response = serialize_doc(shop)
    response["average_scores"] = scores.model_dump() if hasattr(scores, "model_dump") else scores.dict()
    return response


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
        print(f"[AI-PRED] Downloading image from {image_url}", flush=True)
        logger.info(f"Downloading image from {image_url}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        image_bytes = response.content
        print(f"[AI-PRED] Downloaded {len(image_bytes)} bytes", flush=True)
        
        # Run YOLOv8 analysis
        print(f"[AI-PRED] Running YOLOv8 analysis...", flush=True)
        logger.info("Running YOLOv8 analysis...")
        yolov8_features = await yolov8_service.analyze_accessibility_features(image_bytes)
        print(f"[AI-PRED] YOLOv8 results: {yolov8_features}", flush=True)
        
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
        print(f"[AI-PRED] Running Gemini analysis...", flush=True)
        logger.info("Running Gemini analysis...")
        gemini = get_gemini_service()
        gemini_result = await gemini.analyze_accessibility(analysis_image, filename)
        print(f"[AI-PRED] Gemini results: {gemini_result}", flush=True)
        
        # Convert analysis results to AIPrediction format
        # ramp: True if ramp detected OR if accessible (no curbs/steps)
        # curb: True if stairs/curbs detected AND no ramp
        ramp_detected = yolov8_features.get("ramp_detected", False)
        stairs_detected = yolov8_features.get("stairs_detected", False)
        is_accessible = gemini_result.get("accessible", False)
        
        # Determine ramp and curb based on detections and accessibility
        has_ramp = ramp_detected or (is_accessible and not stairs_detected)
        has_curb = stairs_detected and not ramp_detected
        print(f"[AI-PRED] Final prediction: ramp={has_ramp}, curb={has_curb}", flush=True)
        
        # Create AI prediction
        ai_prediction = ShopUpdateAI(
            ramp=has_ramp,
            curb=has_curb,
            image_url=payload.image_url
        )
        
        # Update shop with AI prediction
        update_doc = {
            "ai_prediction": ai_prediction.model_dump(),
            "needPhotos": False,  # Reset needPhotos when AI prediction is updated
        }
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

