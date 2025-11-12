from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.db import db
from app.deps import verify_internal
from app.models import AverageScores, ShopCreate, ShopUpdateAI, serialize_doc

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
    summary="Store or update AI prediction for a shop",
)
async def update_ai_prediction(
    shop_id: str,
    payload: ShopUpdateAI,
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    oid = _oid(shop_id)
    update_doc = {"ai_prediction": payload.model_dump()}
    res = await database.shops.find_one_and_update(
        {"_id": oid},
        {"$set": update_doc},
        return_document=ReturnDocument.AFTER,
    )
    if not res:
        raise HTTPException(status_code=404, detail="Shop not found")
    return serialize_doc(res)

