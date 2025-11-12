import asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI=os.getenv("MONGO_URI")
DB_NAME=os.getenv("DB_NAME","wheel_city")

async def main():
    client=AsyncIOMotorClient(MONGO_URI)
    db=client[DB_NAME]
    await db.shops.create_index([("location", "2dsphere")])
    await db.shops.create_index([("name", "text")])
    await db.reviews.create_index([("shop_id", 1), ("created_at", -1)])
    await db.reviews.create_index([("user_id", 1), ("created_at", -1)])
    await db.users.create_index([("auth_id", 1)], unique=True)

    print("Indexes created")
    client.close()

asyncio.run(main())
