import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import boto3
import requests
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.results import DeleteResult

from app.models import ReviewCreate, S3UploadRequest, serialize_doc
from app.services.ai_reevaluation import (
    check_user_disagrees_with_ai,
    handle_ai_reevaluation_on_disagree,
)

logger = logging.getLogger(__name__)

router = APIRouter()

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_PRESIGN_EXPIRES = int(os.getenv("S3_PRESIGN_EXPIRES", "900"))


def get_db() -> AsyncIOMotorDatabase:
    # Import db module to access the current value (not the imported value at module load time)
    import app.db
    db = app.db.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    return db


def get_s3_client():
    if not S3_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="S3 bucket is not configured")
    return boto3.client("s3")


def _oid(value: str, field: str = "id") -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field}")
    return ObjectId(value)


@router.post(
    "/{shop_id}/upload-urls",
    summary="Generate pre-signed URLs for review photo uploads",
)
async def generate_upload_urls(
    shop_id: str,
    request: S3UploadRequest,
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    print(f"[S3] Generating upload URLs for shop {shop_id}, {len(request.files)} files", flush=True)
    _ = _oid(shop_id, "shop_id")
    s3 = get_s3_client()

    upload_entries: List[dict] = []
    public_urls: List[str] = []

    for original_name in request.files:
        extension = os.path.splitext(original_name)[1] or ""
        key = f"reviews/{shop_id}/{uuid.uuid4().hex}{extension}"
        print(f"[S3] Generating URL for key: {key}", flush=True)
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": S3_BUCKET_NAME, "Key": key},
            ExpiresIn=S3_PRESIGN_EXPIRES,
        )
        public_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{key}"
        upload_entries.append({"file_name": key, "upload_url": upload_url})
        public_urls.append(public_url)
        print(f"[S3] Generated public URL: {public_url}", flush=True)

    print(f"[S3] Returning {len(public_urls)} upload URLs", flush=True)
    return {"upload_urls": upload_entries, "public_urls": public_urls}


@router.post(
    "/{shop_id}",
    summary="Submit a review for a shop",
)
async def submit_review(
    shop_id: str,
    payload: ReviewCreate,
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    shop_oid = _oid(shop_id, "shop_id")
    user_oid = _oid(payload.user_id, "user_id")

    # Get shop to check AI prediction
    shop = await database.shops.find_one({"_id": shop_oid})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    # Check if user disagrees with AI
    shop_ai_pred = shop.get("ai_prediction")
    user_disagrees = False
    if shop_ai_pred:
        user_disagrees = await check_user_disagrees_with_ai(
            payload.ai_correct.model_dump(), shop_ai_pred
        )

    doc = payload.model_dump()
    doc["shop_id"] = shop_oid
    doc["user_id"] = user_oid
    doc["created_at"] = datetime.now(timezone.utc)
    doc["disagree_with_ai"] = user_disagrees

    result = await database.reviews.insert_one(doc)
    inserted_id = result.inserted_id

    # If review has images and shop doesn't have AI prediction, trigger initial AI evaluation
    if payload.photo_urls and len(payload.photo_urls) > 0:
        shop_ai_pred = shop.get("ai_prediction")
        if not shop_ai_pred:
            print(f"[REVIEW] Shop {shop_id} has no AI prediction, triggering initial evaluation with review images", flush=True)
            logger.info(f"Shop {shop_id} has no AI prediction, triggering initial evaluation with review images")
            # Use the first image for initial AI evaluation
            first_image_url = str(payload.photo_urls[0])
            try:
                from app.services.gemini_service import get_gemini_service
                from app.services.yolov8_service import yolov8_service
                from app.models import ShopUpdateAI
                
                print(f"[REVIEW] Downloading image from {first_image_url} for initial AI evaluation", flush=True)
                image_response = requests.get(first_image_url, timeout=30)
                image_response.raise_for_status()
                image_bytes = image_response.content
                
                # Run YOLOv8 analysis
                print(f"[REVIEW] Running YOLOv8 analysis for initial evaluation", flush=True)
                yolov8_features = await yolov8_service.analyze_accessibility_features(image_bytes)
                
                # Extract entrance region if detected
                entrance_image = None
                if yolov8_features.get("entrance_detected", False):
                    entrance_image = await yolov8_service.extract_entrance_region(
                        image_bytes, yolov8_features.get("detections", [])
                    )
                
                # Use entrance region for Gemini if available
                analysis_image = entrance_image if entrance_image else image_bytes
                filename = first_image_url.split("/")[-1] if "/" in first_image_url else "image.jpg"
                
                # Run Gemini analysis
                print(f"[REVIEW] Running Gemini analysis for initial evaluation", flush=True)
                gemini = get_gemini_service()
                gemini_result = await gemini.analyze_accessibility(analysis_image, filename)
                
                # Convert to prediction format
                ramp_detected = yolov8_features.get("ramp_detected", False)
                stairs_detected = yolov8_features.get("stairs_detected", False)
                is_accessible = gemini_result.get("accessible", False)
                
                has_ramp = ramp_detected or (is_accessible and not stairs_detected)
                has_curb = stairs_detected and not ramp_detected
                
                # Update shop with AI prediction
                ai_prediction = ShopUpdateAI(
                    ramp=has_ramp,
                    curb=has_curb,
                    image_url=payload.photo_urls[0]
                )
                
                update_doc = {
                    "ai_prediction": ai_prediction.model_dump(),
                    "needPhotos": False,
                }
                
                await database.shops.update_one(
                    {"_id": shop_oid},
                    {"$set": update_doc}
                )
                
                print(f"[REVIEW] Initial AI evaluation completed: ramp={has_ramp}, curb={has_curb}", flush=True)
                logger.info(f"Initial AI evaluation completed for shop {shop_id}: ramp={has_ramp}, curb={has_curb}")
            except Exception as e:
                print(f"[REVIEW ERROR] Failed initial AI evaluation: {e}", flush=True)
                import traceback
                print(f"[REVIEW ERROR] Traceback:\n{traceback.format_exc()}", flush=True)
                logger.error(f"Failed initial AI evaluation for shop {shop_id}: {e}", exc_info=True)
                # Don't fail review submission if initial evaluation fails

    # If user disagrees, trigger re-evaluation logic
    if user_disagrees:
        print(f"[REVIEW] User disagrees with AI for shop {shop_id}, checking for re-evaluation", flush=True)
        logger.info(
            f"User disagrees with AI for shop {shop_id}, checking for re-evaluation"
        )
        # Get the inserted review document
        inserted_review = await database.reviews.find_one({"_id": inserted_id})
        if inserted_review:
            print(f"[REVIEW] Calling handle_ai_reevaluation_on_disagree for shop {shop_id}", flush=True)
            # Run re-evaluation asynchronously (don't block the response)
            # In production, you might want to use a background task queue
            try:
                await handle_ai_reevaluation_on_disagree(
                    database, shop_oid, inserted_review
                )
                print(f"[REVIEW] Re-evaluation completed for shop {shop_id}", flush=True)
            except Exception as e:
                print(f"[REVIEW ERROR] Error during AI re-evaluation for shop {shop_id}: {e}", flush=True)
                import traceback
                print(f"[REVIEW ERROR] Traceback:\n{traceback.format_exc()}", flush=True)
                logger.error(
                    f"Error during AI re-evaluation for shop {shop_id}: {e}",
                    exc_info=True,
                )
                # Don't fail the review submission if re-evaluation fails
        else:
            print(f"[REVIEW ERROR] Could not find inserted review with id {inserted_id}", flush=True)
    else:
        print(f"[REVIEW] User does NOT disagree with AI for shop {shop_id}", flush=True)

    return {"review_id": str(inserted_id), "status": "success"}


@router.get(
    "/{shop_id}",
    summary="List reviews for a shop",
)
async def list_reviews_for_shop(
    shop_id: str,
    limit: int = Query(50, ge=1, le=100),
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    shop_oid = _oid(shop_id, "shop_id")
    cursor = (
        database.reviews.find({"shop_id": shop_oid})
        .sort("created_at", -1)
        .limit(limit)
    )
    reviews: List[dict] = []
    async for doc in cursor:
        reviews.append(serialize_doc(doc))
    return {"items": reviews, "count": len(reviews)}


@router.get(
    "/user/{user_id}",
    summary="Get reviews written by a user",
)
async def list_reviews_by_user(
    user_id: str,
    limit: int = Query(50, ge=1, le=100),
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    user_oid = _oid(user_id, "user_id")
    cursor = (
        database.reviews.find({"user_id": user_oid})
        .sort("created_at", -1)
        .limit(limit)
    )
    reviews: List[dict] = []
    async for doc in cursor:
        reviews.append(serialize_doc(doc))
    return {"items": reviews, "count": len(reviews)}


@router.delete(
    "/{review_id}",
    summary="Delete a review",
)
async def delete_review(
    review_id: str,
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    review_oid = _oid(review_id, "review_id")
    delete_result: DeleteResult = await database.reviews.delete_one({"_id": review_oid})
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"ok": True}

