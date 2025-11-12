from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.db import db
from app.models import UserCreate, UserUpdate, serialize_doc

router = APIRouter()


def get_db() -> AsyncIOMotorDatabase:
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

