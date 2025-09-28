# app/routers/reports.py
from fastapi import APIRouter, HTTPException
from app.db import db
from app.models import serialize_doc

router = APIRouter()

@router.post("/{place_id}")
async def create_report(place_id: str, report: dict):
    # report 예: {"user_id":"...", "content":"경사로 있음", "status":"pending"}
    report = {**report, "placeId": place_id}
    res = await db.user_reports.insert_one(report)
    return {"inserted_id": str(res.inserted_id)}

@router.get("/{place_id}")
async def list_reports(place_id: str):
    cursor = db.user_reports.find({"placeId": place_id})
    return [serialize_doc(d) async for d in cursor]
