import asyncio, os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv()

async def main():
    client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("DB_NAME","wheel_city")]
    user = await db.users.insert_one(
        {
            "auth_id": "demo-user-1",
            "wheelchair_type": "manual",
            "max_height_cm": 12,
            "last_location": {"type": "Point", "coordinates": [126.9779451, 37.5662952]},
            "review_score": 0,
        }
    )

    shops = await db.shops.insert_many(
        [
            {
                "name": "카페 스타",
                "location": {"type": "Point", "coordinates": [126.9779451, 37.5662952]},
                "ai_prediction": {
                    "ramp": True,
                    "curb": False,
                    "image_url": None,
                },
            },
            {
                "name": "투썸 종각점",
                "location": {"type": "Point", "coordinates": [126.982, 37.57]},
                "ai_prediction": {
                    "ramp": False,
                    "curb": True,
                    "image_url": None,
                },
            },
        ]
    )

    review = await db.reviews.insert_one(
        {
            "shop_id": shops.inserted_ids[0],
            "user_id": user.inserted_id,
            "enter": True,
            "alone": False,
            "comfort": True,
            "ai_correct": {"ramp": True, "curb": False},
            "photo_urls": [],
            "review_text": "친절하고 진입이 쉬웠어요.",
            "created_at": datetime.utcnow(),
        }
    )

    print("✅ Seeded demo data successfully!")
    print(f"   - Created user: {user.inserted_id}")
    print(f"   - Created {len(shops.inserted_ids)} shops:")
    for i, shop_id in enumerate(shops.inserted_ids):
        print(f"     Shop {i+1}: {shop_id}")
    print(f"   - Created review: {review.inserted_id}")
    client.close()

asyncio.run(main())
