import asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI=os.getenv("MONGO_URI")
DB_NAME=os.getenv("DB_NAME","wheel_city")

async def main():
    client=AsyncIOMotorClient(MONGO_URI)
    db=client[DB_NAME]
    await db.places.create_index([("location","2dsphere")])
    await db.observations.create_index([("placeId",1),("createdAt",-1)])
    await db.user_reports.create_index([("placeId",1),("status",1),("createdAt",-1)])
    #추가
    await db.accessibility_data.create_index([("place_id", 1), ("analyzed_at", -1)])
    await db.accessibility_data.create_index([("analyzed_at", -1)])

    print("Indexes created")
    client.close()

asyncio.run(main())
