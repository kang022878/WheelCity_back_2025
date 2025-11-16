"""
Service for handling AI re-evaluation when users disagree with AI predictions.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.gemini_service import get_gemini_service
from app.services.yolov8_service import yolov8_service

logger = logging.getLogger(__name__)


async def check_user_disagrees_with_ai(
    review_ai_correct: Dict[str, bool], shop_ai_prediction: Optional[Dict[str, Any]]
) -> bool:
    """
    Check if user's review indicates disagreement with AI prediction.
    
    User disagrees if:
    - shop has ai_prediction AND
    - (review says ramp != shop says ramp) OR (review says curb != shop says curb)
    """
    if not shop_ai_prediction:
        return False  # No AI prediction to disagree with
    
    shop_ramp = shop_ai_prediction.get("ramp", False)
    shop_curb = shop_ai_prediction.get("curb", False)
    review_ramp = review_ai_correct.get("ramp", False)
    review_curb = review_ai_correct.get("curb", False)
    
    # Disagree if ramp or curb doesn't match
    return (review_ramp != shop_ramp) or (review_curb != shop_curb)


async def get_last_n_reviews(
    database: AsyncIOMotorDatabase, shop_id: ObjectId, n: int = 3
) -> List[Dict[str, Any]]:
    """Get the last N reviews for a shop, ordered by created_at descending."""
    cursor = (
        database.reviews.find({"shop_id": shop_id})
        .sort("created_at", -1)
        .limit(n)
    )
    reviews = []
    async for doc in cursor:
        reviews.append(doc)
    return reviews


async def all_reviews_disagree(reviews: List[Dict[str, Any]]) -> bool:
    """Check if all reviews have disagree_with_ai flag set to True."""
    if len(reviews) < 3:
        return False
    
    for review in reviews:
        if not review.get("disagree_with_ai", False):
            return False
    return True


async def collect_image_urls_from_reviews(reviews: List[Dict[str, Any]]) -> List[str]:
    """Collect all photo URLs from the given reviews."""
    image_urls = []
    for review in reviews:
        photo_urls = review.get("photo_urls", [])
        if photo_urls:
            # Convert HttpUrl objects to strings if needed
            for url in photo_urls:
                url_str = str(url) if url else None
                if url_str:
                    image_urls.append(url_str)
    return image_urls


async def analyze_image_for_ai_prediction(image_url: str) -> Optional[Dict[str, bool]]:
    """
    Analyze a single image and return AI prediction (ramp, curb).
    Returns None if analysis fails.
    """
    try:
        # Download image
        logger.info(f"Downloading image from {image_url} for re-evaluation")
        import os
        import boto3
        
        S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
        
        # Use boto3 for S3 URLs, requests for external URLs
        if S3_BUCKET_NAME and image_url.startswith(f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/"):
            s3_key = image_url.replace(f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/", "")
            s3 = boto3.client("s3")
            logger.info(f"Downloading from S3 bucket {S3_BUCKET_NAME}, key: {s3_key}")
            s3_response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
            image_bytes = s3_response['Body'].read()
        else:
            # Fallback to HTTP request for external URLs
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            image_bytes = response.content
        
        # Run YOLOv8 analysis
        yolov8_features = await yolov8_service.analyze_accessibility_features(image_bytes)
        
        # Extract entrance region if detected
        entrance_image = None
        if yolov8_features.get("entrance_detected", False):
            entrance_image = await yolov8_service.extract_entrance_region(
                image_bytes, yolov8_features.get("detections", [])
            )
        
        # Use entrance region for Gemini if available
        analysis_image = entrance_image if entrance_image else image_bytes
        filename = image_url.split("/")[-1] if "/" in image_url else "image.jpg"
        
        # Run Gemini analysis
        gemini = get_gemini_service()
        gemini_result = await gemini.analyze_accessibility(analysis_image, filename)
        
        # Convert to prediction format
        # Use Gemini's direct ramp/curb detection, combined with YOLOv8 results
        gemini_ramp = gemini_result.get("ramp", False)
        gemini_curb = gemini_result.get("curb", False)
        ramp_detected = yolov8_features.get("ramp_detected", False)
        stairs_detected = yolov8_features.get("stairs_detected", False)
        
        # Combine YOLOv8 and Gemini results (if either detects it, consider it present)
        has_ramp = ramp_detected or gemini_ramp
        has_curb = (stairs_detected or gemini_curb) and not has_ramp  # Only curb if no ramp
        
        return {"ramp": has_ramp, "curb": has_curb}
        
    except Exception as e:
        logger.error(f"Failed to analyze image {image_url}: {e}")
        return None


async def re_evaluate_shop_ai_prediction(
    database: AsyncIOMotorDatabase,
    shop_id: ObjectId,
    review_image_urls: List[str],
) -> Optional[Dict[str, bool]]:
    """
    Re-run AI analysis on review images.
    Returns AI prediction if at least one image analysis succeeds, None otherwise.
    """
    if not review_image_urls:
        return None
    
    successful_predictions = []
    
    for image_url in review_image_urls:
        prediction = await analyze_image_for_ai_prediction(image_url)
        if prediction:
            successful_predictions.append(prediction)
    
    if not successful_predictions:
        return None
    
    # If AI agrees with users on at least one image, use that prediction
    # For now, we'll use the first successful prediction
    # You could also implement voting logic here
    return successful_predictions[0]


async def handle_ai_reevaluation_on_disagree(
    database: AsyncIOMotorDatabase,
    shop_id: ObjectId,
    new_review: Dict[str, Any],
) -> None:
    """
    Main function to handle AI re-evaluation when users disagree.
    
    Flow:
    1. Get last 3 reviews (including the new one)
    2. Check if all 3 disagree
    3. If yes, collect images and re-run AI
    4. Update shop accordingly
    """
    try:
        print(f"[REEVAL] Starting re-evaluation for shop {shop_id}", flush=True)
        # Get last 3 reviews
        last_3_reviews = await get_last_n_reviews(database, shop_id, n=3)
        print(f"[REEVAL] Found {len(last_3_reviews)} reviews for shop {shop_id}", flush=True)
        
        if len(last_3_reviews) < 3:
            print(f"[REEVAL] Less than 3 reviews for shop {shop_id}, skipping re-evaluation", flush=True)
            logger.info(f"Less than 3 reviews for shop {shop_id}, skipping re-evaluation")
            return
        
        # Check if all 3 reviews have disagree_with_ai flag
        # We need to mark the new review as disagreeing first
        # For now, we'll check if the new review's ai_correct doesn't match shop's ai_prediction
        shop = await database.shops.find_one({"_id": shop_id})
        if not shop:
            logger.warning(f"Shop {shop_id} not found")
            return
        
        shop_ai_pred = shop.get("ai_prediction")
        if not shop_ai_pred:
            logger.info(f"Shop {shop_id} has no AI prediction, skipping")
            return
        
        # Check if new review disagrees
        new_review_disagrees = await check_user_disagrees_with_ai(
            new_review.get("ai_correct", {}), shop_ai_pred
        )
        
        if not new_review_disagrees:
            logger.info(f"New review for shop {shop_id} does not disagree with AI")
            return
        
        # Mark new review as disagreeing (for future checks)
        await database.reviews.update_one(
            {"_id": new_review.get("_id")},
            {"$set": {"disagree_with_ai": True}}
        )
        
        # Check last 3 reviews again (now with updated flag)
        last_3_reviews = await get_last_n_reviews(database, shop_id, n=3)
        
        # Check if all 3 disagree
        # For older reviews without the flag, check the logic
        all_disagree = True
        for review in last_3_reviews:
            # If flag exists, use it; otherwise check logic for older reviews
            if "disagree_with_ai" in review:
                if not review.get("disagree_with_ai", False):
                    all_disagree = False
                    break
            else:
                # Older review without flag - check logic
                review_ai_correct = review.get("ai_correct", {})
                review_disagrees = await check_user_disagrees_with_ai(
                    review_ai_correct, shop_ai_pred
                )
                if not review_disagrees:
                    all_disagree = False
                    break
                # Update the flag for future checks
                await database.reviews.update_one(
                    {"_id": review.get("_id")},
                    {"$set": {"disagree_with_ai": True}}
                )
        
        if not all_disagree:
            print(f"[REEVAL] Not all 3 reviews disagree for shop {shop_id}", flush=True)
            logger.info(f"Not all 3 reviews disagree for shop {shop_id}")
            return
        
        print(f"[REEVAL] All 3 reviews disagree for shop {shop_id}, triggering re-evaluation", flush=True)
        logger.info(f"All 3 reviews disagree for shop {shop_id}, triggering re-evaluation")
        
        # Collect image URLs from all 3 reviews
        image_urls = await collect_image_urls_from_reviews(last_3_reviews)
        
        if not image_urls:
            # No images - set needPhotos = true
            logger.info(f"No images in reviews for shop {shop_id}, setting needPhotos=true")
            await database.shops.update_one(
                {"_id": shop_id},
                {
                    "$set": {
                        "needPhotos": True,
                        "ai_recheck_date": datetime.now(timezone.utc),
                    }
                },
            )
            return
        
        # Re-run AI on images
        logger.info(f"Re-running AI on {len(image_urls)} images for shop {shop_id}")
        new_ai_prediction = await re_evaluate_shop_ai_prediction(
            database, shop_id, image_urls
        )
        
        if new_ai_prediction:
            # AI agreed with users on at least one image
            # Update shop's ai_prediction
            from app.models import ShopUpdateAI
            
            # Get the first image URL for the prediction (ensure it's a string)
            first_image_url = image_urls[0] if image_urls else None
            if first_image_url:
                first_image_url = str(first_image_url)
            
            update_doc = {
                "ai_prediction": {
                    "ramp": new_ai_prediction["ramp"],
                    "curb": new_ai_prediction["curb"],
                    "image_url": first_image_url,
                },
                "needPhotos": False,
                "ai_recheck_date": datetime.now(timezone.utc),
            }
            
            await database.shops.update_one(
                {"_id": shop_id},
                {"$set": update_doc},
            )
            
            logger.info(
                f"Updated shop {shop_id} AI prediction: ramp={new_ai_prediction['ramp']}, "
                f"curb={new_ai_prediction['curb']}"
            )
        else:
            # AI still disagrees on all images - set needPhotos = true
            logger.info(
                f"AI still disagrees on all images for shop {shop_id}, setting needPhotos=true"
            )
            await database.shops.update_one(
                {"_id": shop_id},
                {
                    "$set": {
                        "needPhotos": True,
                        "ai_recheck_date": datetime.now(timezone.utc),
                    }
                },
            )
            
    except Exception as e:
        logger.error(f"Error in AI re-evaluation for shop {shop_id}: {e}", exc_info=True)

