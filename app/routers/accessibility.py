from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse, Response
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import hashlib
import json

from app.models import AccessibilityData

# POST /accessibility : ML 결과 저장(기존 ingest 대체 가능)
# GET /accessibility/latest : 특정 place의 최신 1건
# GET /accessibility/list : 페이지네이션 목록
# GET /accessibility/updates : “since” 시각 이후 신규만 (폴링 최적화)
# HEAD /accessibility/etag : ETag/Last-Modified를 위한 체크 (옵션)

router = APIRouter()

def _db(app) -> Optional[any]:
    return getattr(app.state, "db", None)

def _oid(val: str) -> ObjectId:
    return ObjectId(val) if ObjectId.is_valid(val) else val

@router.post("/accessibility", summary="접근성 데이터 저장")
async def create_accessibility(data: AccessibilityData, request: Request):
    db = _db(request.app)
    if db is None:
        raise HTTPException(500, "Database not connected")

    doc = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    if not doc.get("analyzed_at"):
        doc["analyzed_at"] = datetime.utcnow()

    result = await db["accessibility_data"].insert_one(doc)
    return {"id": str(result.inserted_id)}

@router.get("/accessibility/latest", summary="특정 place의 최신 1건")
async def get_latest(place_id: str, request: Request):
    db = _db(request.app)
    if db is None:
        raise HTTPException(500, "Database not connected")

    doc = await db["accessibility_data"].find_one(
        {"place_id": place_id},
        sort=[("analyzed_at", -1)]
    )
    if not doc:
        return JSONResponse({"message": "no data"}, status_code=204)

    doc["id"] = str(doc.pop("_id"))
    return doc

@router.get("/accessibility/list", summary="접근성 데이터 목록(페이지네이션)")
async def list_accessibility(
    request: Request,
    place_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    before: Optional[str] = None,   # ISO8601 (이전 시각)
    after: Optional[str] = None,    # ISO8601 (이후 시각)
):
    db = _db(request.app)
    if db is None:
        raise HTTPException(500, "Database not connected")

    q = {}
    if place_id:
        q["place_id"] = place_id
    if before:
        q.setdefault("analyzed_at", {})["$lt"] = datetime.fromisoformat(before.replace("Z",""))
    if after:
        q.setdefault("analyzed_at", {})["$gt"] = datetime.fromisoformat(after.replace("Z",""))

    cursor = (
        db["accessibility_data"]
        .find(q)
        .sort([("analyzed_at", -1)])
        .limit(limit)
    )
    docs = []
    async for d in cursor:
        d["id"] = str(d.pop("_id"))
        docs.append(d)
    return {"items": docs, "count": len(docs)}

@router.get("/accessibility/updates", summary="since 이후 신규만(폴링 최적화)")
async def get_updates(
    request: Request,
    place_id: str,
    since: str,  # ISO8601 문자열 (예: 2025-11-06T09:00:00Z)
    limit: int = Query(20, ge=1, le=100),
):
    db = _db(request.app)
    if db is None:
        raise HTTPException(500, "Database not connected")

    since_dt = datetime.fromisoformat(since.replace("Z",""))
    cursor = (
        db["accessibility_data"]
        .find({"place_id": place_id, "analyzed_at": {"$gt": since_dt}})
        .sort([("analyzed_at", 1)])  # 오래된 것부터
        .limit(limit)
    )
    items = []
    async for d in cursor:
        d["id"] = str(d.pop("_id"))
        items.append(d)

    if not items:
        # 신규 없음 → 204로 응답하면 클라가 폴링 주기만 유지
        return Response(status_code=204)

    return {"items": items, "count": len(items), "latest": items[-1]["analyzed_at"]}

@router.head("/accessibility/etag", summary="변경 감지용 ETag/Last-Modified 체크(옵션)")
async def check_etag(
    request: Request,
    place_id: str
):
    db = _db(request.app)
    if db is None:
        raise HTTPException(500, "Database not connected")

    latest = await db["accessibility_data"].find_one(
        {"place_id": place_id},
        sort=[("analyzed_at", -1)],
        projection={"_id": 1, "analyzed_at": 1}
    )
    if not latest:
        return Response(status_code=204)

    # 최신 레코드 기준 ETag/Last-Modified 생성
    etag_raw = f'{str(latest["_id"])}|{latest["analyzed_at"].isoformat()}'
    etag = hashlib.sha1(etag_raw.encode()).hexdigest()
    last_modified = latest["analyzed_at"].strftime("%a, %d %b %Y %H:%M:%S GMT")

    # If-None-Match / If-Modified-Since 처리
    inm = request.headers.get("If-None-Match")
    ims = request.headers.get("If-Modified-Since")
    headers = {"ETag": etag, "Last-Modified": last_modified}

    if (inm and inm == etag) or (ims and ims == last_modified):
        return Response(status_code=304, headers=headers)

    return Response(status_code=200, headers=headers)
