from fastapi import APIRouter, HTTPException, Request, status
from app.models.accessibility_model import AccessibilityData
from app.ws.manager import manager
from typing import Optional
import traceback
from datetime import datetime

router = APIRouter()

def _pick_db(request: Request):
    db = getattr(request.app.state, "db", None)
    if db is not None:
        return db
    try:
        from app.db import db as global_db  # type: ignore
        if global_db is not None:
            return global_db
    except Exception:
        pass
    return None

@router.post("/accessibility", status_code=status.HTTP_201_CREATED)
async def save_accessibility_data(data: AccessibilityData, request: Request):
    """
    ML 모델 결과(접근성 정보)를 MongoDB에 저장하고,
    1) 같은 place_id 방에 JSON 이벤트 브로드캐스트
    2) 전체 클라이언트에 텍스트 알림 브로드캐스트 (manager.broadcast)
    """
    db = _pick_db(request)
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    try:
        # pydantic v2 호환
        doc = data.model_dump() if hasattr(data, "model_dump") else data.dict()

        # analyzed_at 기본값 보정
        if "analyzed_at" not in doc or doc["analyzed_at"] is None:
            doc["analyzed_at"] = datetime.utcnow()

        # 저장
        result = await db["accessibility_data"].insert_one(doc)

        # 직렬화된 시간 문자열 준비
        analyzed_at_str: Optional[str] = None
        if isinstance(doc.get("analyzed_at"), datetime):
            analyzed_at_str = doc["analyzed_at"].isoformat()
        elif doc.get("analyzed_at") is not None:
            analyzed_at_str = str(doc["analyzed_at"])

        # 1) 같은 place_id 방으로 구조화 이벤트 전송
        event = {
            "type": "accessibility:new",
            "data": {
                "id": str(result.inserted_id),
                "place_id": doc.get("place_id"),
                "image_url": doc.get("image_url"),
                "detected_features": doc.get("detected_features", {}),
                "confidence_scores": doc.get("confidence_scores", {}),
                "overall_accessibility_score": doc.get("overall_accessibility_score"),
                "analyzed_at": analyzed_at_str,
                "model_version": doc.get("model_version"),
            },
        }
        try:
            if doc.get("place_id"):
                await manager.broadcast_room(doc["place_id"], event)
        except Exception as be:
            print(f"[WS broadcast_room skipped] {be}")
            traceback.print_exc()

        # 2) 모든 연결 클라이언트에 간단 텍스트 알림 전송
        try:
            place = doc.get("place_id", "unknown")
            score = doc.get("overall_accessibility_score", "N/A")
            await manager.broadcast(f"✅ New accessibility data inserted (place_id={place}, score={score})")
        except Exception as be2:
            print(f"[WS broadcast skipped] {be2}")
            traceback.print_exc()

        return {
            "message": "Accessibility data stored successfully",
            "id": str(result.inserted_id),
        }

    except HTTPException:
        raise
    except Exception as e:
        print("❌ Ingest error:", repr(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
