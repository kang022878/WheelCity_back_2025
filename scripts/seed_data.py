import asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv()

async def main():
    client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("DB_NAME","wheel_city")]
    docs = [
        {
            "name":"카페 스타",
            "location":{"type":"Point","coordinates":[126.9779451,37.5662952]},
            "accessibility":{"threshold":0,"entrance":1,"door":1,"confidence":0.95,"modelVersion":"v1","source":"model"},
            "imageUrl":None,"source":"seed"
        },
        {
            "name":"투썸 종각점",
            "location":{"type":"Point","coordinates":[126.982,37.57]},
            "accessibility":{"threshold":2,"entrance":2,"door":0,"confidence":0.82,"modelVersion":"v1","source":"model"},
            "imageUrl":None,"source":"seed"
        }
    ]
    await db.places.insert_many(docs)
    print("Seeded")
    client.close()

asyncio.run(main())
