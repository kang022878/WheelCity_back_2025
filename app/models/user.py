from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

class UserPublic(BaseModel):
    id: str = Field(alias="_id")
    email: EmailStr
    name: Optional[str] = None
    created_at: datetime

class UserInDB(BaseModel):
    email: EmailStr
    hashed_password: str
    name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
