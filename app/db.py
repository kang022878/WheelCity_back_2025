from typing import Optional
import os
from pathlib import Path
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Get the project root directory (where .env should be)
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"

# Load .env file from project root
load_dotenv(dotenv_path=env_path)

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
        print(f"❌ MONGO_URI is not set in .env file")
        print(f"   Looking for .env at: {env_path}")
        print(f"   .env file exists: {env_path.exists()}")
        if env_path.exists():
            print(f"   .env file size: {env_path.stat().st_size} bytes")
        error_msg = (
            "❌ MONGO_URI is not set in .env file. Please check:\n"
            "   1. Variable name is MONGO_URI (all uppercase)\n"
            "   2. No spaces around the = sign\n"
            "   3. .env file is in the wheel_city_server directory"
        )
        raise ValueError(error_msg)

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
    if _client is not None:
        _client.close()
        print("🛑 MongoDB connection closed")

