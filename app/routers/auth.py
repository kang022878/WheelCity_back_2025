from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import EmailStr
from app.models.user import UserCreate, UserPublic, Token, UserInDB
from app.security.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_db_from_request
)
from datetime import timedelta
from bson import ObjectId

router = APIRouter()

@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, request: Request, db = Depends(get_db_from_request)):
    exists = await db["users"].find_one({"email": data.email})
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    doc = UserInDB(
        email=data.email,
        hashed_password=hash_password(data.password),
        name=data.name
    ).dict()

    res = await db["users"].insert_one(doc)
    created = await db["users"].find_one({"_id": res.inserted_id})
    created["_id"] = str(created["_id"])
    return created

@router.post("/login", response_model=Token)
async def login(form: dict, request: Request, db = Depends(get_db_from_request)):
    """
    Body(JSON):
    { "email": "user@example.com", "password": "..." }
    """
    email = form.get("email")
    password = form.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")

    user = await db["users"].find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(password, user.get("hashed_password","")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(subject=email, expires_delta=timedelta(minutes=30))
    return Token(access_token=token)

@router.get("/me", response_model=UserPublic)
async def me(current_user=Depends(get_current_user)):
    # current_user는 dict 이므로 alias 맞춰서 반환
    current_user["_id"] = str(current_user["_id"])
    return current_user
