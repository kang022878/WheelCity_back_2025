from typing import Optional
import os
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "wheel_city")

# 전역 클라이언트와 DB 핸들
_client: Optional[AsyncIOMotorClient] = None
db = None


async def connect(*args, **kwargs):
    """
    MongoDB Atlas에 연결하고 전역 변수에 클라이언트와 데이터베이스 핸들을 저장.
    """
    global _client, db
    if not MONGO_URI:
        raise ValueError("❌ MONGO_URI is not set in .env file")

    try:
        _client = AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
        db = _client[DB_NAME]

        # 연결 테스트
        await db.command("ping")
        print("✅ Connected to MongoDB Atlas")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        _client = None
        db = None


async def close():
    """MongoDB 연결 종료"""
    global _client
    if _client:
        _client.close()
        print("🛑 MongoDB connection closed")
