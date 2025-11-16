from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models import UserCreate, UserUpdate, UserGetOrCreate, serialize_doc

router = APIRouter()


def get_db() -> AsyncIOMotorDatabase:
    # Import db module to access the current value (not the imported value at module load time)
    import app.db
    db = app.db.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    return db


def _auth_header(x_auth_id: Optional[str]) -> str:
    if not x_auth_id:
        raise HTTPException(status_code=400, detail="X-Auth-Id header required")
    return x_auth_id


@router.post("/", summary="Create a new user")
async def create_user(user: UserCreate, database: AsyncIOMotorDatabase = Depends(get_db)):
    existing = await database.users.find_one({"auth_id": user.auth_id})
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    doc = user.model_dump()
    res = await database.users.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return doc


@router.get("/me", summary="Get current authenticated user profile")
async def get_current_user(
    x_auth_id: Optional[str] = Header(None, alias="X-Auth-Id"),
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    auth_id = _auth_header(x_auth_id)
    user = await database.users.find_one({"auth_id": auth_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_doc(user)


@router.patch("/me", summary="Update current user profile")
async def update_current_user(
    payload: UserUpdate,
    x_auth_id: Optional[str] = Header(None, alias="X-Auth-Id"),
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    auth_id = _auth_header(x_auth_id)
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided")
    res = await database.users.find_one_and_update(
        {"auth_id": auth_id},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER,
    )
    if not res:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_doc(res)


@router.post("/get-or-create", summary="Get or create a user by Kakao ID")
async def get_or_create_user_by_kakao(
    payload: UserGetOrCreate,
    database: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get existing user by Kakao ID, or create a new one if not found.
    Returns the user_id and whether the user was created.
    """
    # Try to find existing user by kakao_id
    existing_user = await database.users.find_one({"kakao_id": payload.kakao_id})
    
    if existing_user:
        return {
            "user_id": str(existing_user["_id"]),
            "created": False,
            "user": serialize_doc(existing_user)
        }
    
    # User doesn't exist, create a new one
    # Use kakao_id as auth_id for Kakao users
    new_user_data = {
        "auth_id": f"kakao_{payload.kakao_id}",
        "kakao_id": payload.kakao_id,
        "email": payload.email,
        "name": payload.name or "카카오사용자",
        "wheelchair_type": "manual",  # Default values
        "max_height_cm": 100,  # Default value
        "review_score": 0.0,
    }
    
    result = await database.users.insert_one(new_user_data)
    new_user_data["_id"] = result.inserted_id
    
    return {
        "user_id": str(result.inserted_id),
        "created": True,
        "user": serialize_doc(new_user_data)
    }

