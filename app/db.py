import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from typing import Optional

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "wheel_city")

client: Optional[AsyncIOMotorClient] = None
db = None

async def connect():
    global client, db
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

async def close():
    if client:
        client.close()
