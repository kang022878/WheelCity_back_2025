import os
from fastapi import Header, HTTPException

API_KEY = os.getenv("API_KEY_INTERNAL")

async def verify_internal(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
