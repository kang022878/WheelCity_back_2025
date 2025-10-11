from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
from app.db import db
from app.models.place import PlaceIn
from app.models.utils import serialize_doc
from app.deps import verify_internal

router = APIRouter()

@router.post("/", dependencies=[Depends(verify_internal)])
async def create_place(place: PlaceIn):
    res = await db.places.insert_one(place.model_dump())
    return {"inserted_id": str(res.inserted_id)}

@router.get("/{place_id}")
async def get_place(place_id: str):
    try:
        oid = ObjectId(place_id)
    except:
        raise HTTPException(400, "invalid id")
    doc = await db.places.find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "not found")
    return serialize_doc(doc)

@router.get("/nearby/")
async def nearby(lat: float, lng: float, radius: int = 800):
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
    minLng: float = Query(...), minLat: float = Query(...),
    maxLng: float = Query(...), maxLat: float = Query(...)
):
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
async def ingest(place_id: str, pred: dict):
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
