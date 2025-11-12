import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import boto3
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.results import DeleteResult

from app.db import db
from app.models import ReviewCreate, S3UploadRequest, serialize_doc

router = APIRouter()

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_PRESIGN_EXPIRES = int(os.getenv("S3_PRESIGN_EXPIRES", "900"))


def get_db() -> AsyncIOMotorDatabase:
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
    _ = _oid(shop_id, "shop_id")
    s3 = get_s3_client()

    upload_entries: List[dict] = []
    public_urls: List[str] = []

    for original_name in request.files:
        extension = os.path.splitext(original_name)[1] or ""
        key = f"reviews/{shop_id}/{uuid.uuid4().hex}{extension}"
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": S3_BUCKET_NAME, "Key": key},
            ExpiresIn=S3_PRESIGN_EXPIRES,
        )
        upload_entries.append({"file_name": key, "upload_url": upload_url})
        public_urls.append(f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{key}")

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

    doc = payload.model_dump()
    doc["shop_id"] = shop_oid
    doc["user_id"] = user_oid
    doc["created_at"] = datetime.now(timezone.utc)

    result = await database.reviews.insert_one(doc)
    return {"review_id": str(result.inserted_id), "status": "success"}


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

