# from fastapi import APIRouter, HTTPException, status
# from app.models.accessibility_model import AccessibilityData
# from app.db import db
# from datetime import datetime

# router = APIRouter()

# @router.post("/accessibility", status_code=status.HTTP_201_CREATED)
# async def save_accessibility_data(data: AccessibilityData):
#     """
#     ML모델 결과를 MongoDB에 저장하는 엔드포인트
#     """
#     try:
#         record = data.dict()
#         record["created_at"] = datetime.utcnow()

#         result = await db["accessibility"].insert_one(record)

#         return {
#             "message": "Accessibility data saved successfully.",
#             "inserted_id": str(result.inserted_id)
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


from fastapi import APIRouter, HTTPException, Request, status
from app.models.accessibility_model import AccessibilityData

router = APIRouter()

@router.post("/accessibility", status_code=status.HTTP_201_CREATED)
async def save_accessibility_data(data: AccessibilityData, request: Request):
    # ✅ app.state에서 db를 꺼낸다
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    try:
        doc = data.model_dump()  # pydantic v2
        result = await db["accessibility_data"].insert_one(doc)
        return {"message": "Accessibility data stored successfully", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
