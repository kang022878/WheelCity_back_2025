# import asyncio, os
# from motor.motor_asyncio import AsyncIOMotorClient
# from dotenv import load_dotenv

# load_dotenv()
# MONGO_URI=os.getenv("MONGO_URI")
# DB_NAME=os.getenv("DB_NAME","wheel_city")

# async def main():
#     client=AsyncIOMotorClient(MONGO_URI)
#     db=client[DB_NAME]
#     await db.places.create_index([("location","2dsphere")])
#     await db.observations.create_index([("placeId",1),("createdAt",-1)])
#     await db.user_reports.create_index([("placeId",1),("status",1),("createdAt",-1)])
#     print("Indexes created")
#     client.close()

# asyncio.run(main())

import asyncio
import os
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# MongoDB Atlas 연결 정보
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "wheel_city")

# Atlas SSL 인증서 보장
CA = certifi.where()

async def main():
    print("🔗 Connecting to MongoDB Atlas...")
    client = AsyncIOMotorClient(MONGO_URI, tlsCAFile=CA)

    db = client[DB_NAME]

    # 연결 확인 (ping)
    try:
        await db.command("ping")
        print("✅ Connected successfully to MongoDB Atlas.")
    except Exception as e:
        print("❌ Connection failed:", e)
        return

    # 인덱스 생성
    print("⚙️ Creating indexes...")
    await db.places.create_index([("location", "2dsphere")])
    await db.observations.create_index([("placeId", 1), ("createdAt", -1)])
    await db.user_reports.create_index([("placeId", 1), ("status", 1), ("createdAt", -1)])

    # users 컬렉션 인덱스 추가: username, email은 로그인/회원가입 시 자주 검색되므로 unique index를 추천
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username", unique=True)
    await db.users.create_index([("createdAt", -1)])  # 최근 가입자 정렬용

    print("🎉 Indexes created successfully!")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
