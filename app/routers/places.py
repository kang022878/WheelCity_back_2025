from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
#from app.db import db
from fastapi import Request

from app.models.place import PlaceIn
from app.models.utils import serialize_doc
from app.deps import verify_internal
from pydantic import BaseModel
from typing import Literal

class ReactionIn(BaseModel):
    vote: Literal["up", "down"]
    action: Literal["increase", "decrease"] = "increase"

router = APIRouter()

# ✅ MongoDB 헬퍼: app.state.db 가져오기
def _get_db_or_500(request: Request):
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    return db

@router.post("/", dependencies=[Depends(verify_internal)])
async def create_place(place: PlaceIn, request: Request):
    db = _get_db_or_500(request)
    res = await db.places.insert_one(place.model_dump())
    return {"inserted_id": str(res.inserted_id)}

@router.get("/{place_id}")
async def get_place(place_id: str, request: Request):
    db = _get_db_or_500(request)
    try:
        oid = ObjectId(place_id)
    except:
        raise HTTPException(400, "invalid id")
    doc = await db.places.find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "not found")
    return serialize_doc(doc)

@router.get("/nearby/")
async def nearby(request: Request, lat: float, lng: float, radius: int = 800):
    db = _get_db_or_500(request)
    # GeoJSON은 [lng, lat] 순서!
    q = {
        "location": {
            "$near": {
                "$geometry": {"type":"Point","coordinates":[lng, lat]},
                "$maxDistance": radius
            }
        }
    }
    cursor = db.places.find(q, projection={"name":1,"location":1,"accessibility":1,"imageUrl":1})
    return [serialize_doc(d) async for d in cursor]

@router.get("/bbox")
async def bbox(
    request: Request,
    minLng: float = Query(...), minLat: float = Query(...),
    maxLng: float = Query(...), maxLat: float = Query(...)):
    db = _get_db_or_500(request)

    if not (minLng < maxLng and minLat < maxLat):
        raise HTTPException(400, "invalid bbox")

    poly = {
        "type":"Polygon",
        "coordinates":[[
            [minLng,minLat],[maxLng,minLat],
            [maxLng,maxLat],[minLng,maxLat],
            [minLng,minLat]
        ]]
    }
    cursor = db.places.find(
        {"location":{"$geoWithin":{"$geometry": poly}}},
        projection={"name":1,"location":1,"accessibility":1,"imageUrl":1}
    ).limit(500)
    return [serialize_doc(d) async for d in cursor]

# ML 추론 결과 적재(내부용)
@router.post("/{place_id}/ingest", dependencies=[Depends(verify_internal)])
async def ingest(place_id: str, pred: dict, request: Request):
    db = _get_db_or_500(request)
    # pred 예: {"threshold":1,"entrance":1,"door":0,"confidence":0.87,"modelVersion":"v1"}
    try:
        oid = ObjectId(place_id)
    except:
        raise HTTPException(400, "invalid id")
    update = {
        "accessibility": {
            **pred,
            "updatedAt": __import__("datetime").datetime.utcnow().isoformat(),
            "source": "model"
        }
    }
    await db.places.update_one({"_id": oid}, {"$set": update})
    return {"ok": True}

# 좋아요/싫어요 수 라우트 추가
@router.post("/{place_id}/react")
async def react_place(place_id: str, payload: ReactionIn, request: Request):
    """
    장소 단위 좋아요/싫어요 수를 +1 또는 -1 하되,
    0 이하로는 내려가지 않게 제한.
    """
    db = _get_db_or_500(request)

    try:
        oid = ObjectId(place_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid id")

    # 현재 값 조회
    doc = await db.places.find_one(
        {"_id": oid},
        projection={"accessibility.up": 1, "accessibility.down": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="place not found")

    acc = doc.get("accessibility", {})
    current_value = acc.get(payload.vote, 0)

    # 증가/감소 결정
    if payload.action == "increase":
        delta = 1
    else:  # decrease
        if current_value <= 0:
            # 이미 0이면 감소 불가
            return {
                "place_id": place_id,
                "message": f"{payload.vote} count is already 0",
                "up": acc.get("up", 0),
                "down": acc.get("down", 0)
            }
        delta = -1

    # MongoDB 업데이트
    inc_path = f"accessibility.{payload.vote}"
    res = await db.places.update_one({"_id": oid}, {"$inc": {inc_path: delta}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="place not found")

    # 업데이트 후 최신 값 반환
    doc2 = await db.places.find_one(
        {"_id": oid},
        projection={"accessibility.up": 1, "accessibility.down": 1}
    )
    acc2 = (doc2 or {}).get("accessibility", {})
    return {
        "place_id": place_id,
        "up": acc2.get("up", 0),
        "down": acc2.get("down", 0)
    }

# 좋아요/싫어요 수 조회 라우트
@router.get("/{place_id}/reactions")
async def get_reactions(request: Request, place_id: str):
    db = _get_db_or_500(request)   # ✅ app.state.db에서 DB 가져오기

    try:
        oid = ObjectId(place_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid id")

    doc = await db.places.find_one(
        {"_id": oid},
        projection={"accessibility.up": 1, "accessibility.down": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="place not found")

    acc = doc.get("accessibility", {})
    return {
        "place_id": place_id,
        "up": acc.get("up", 0),
        "down": acc.get("down", 0)
    }
