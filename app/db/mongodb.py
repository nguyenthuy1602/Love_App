from motor.motor_asyncio import AsyncIOMotorClient
from datetime import timezone
from app.core.config import settings

client: AsyncIOMotorClient = None


def get_database():
    return client[settings.database_name]


async def connect_db():
    global client
    client = AsyncIOMotorClient(settings.mongodb_uri, tz_aware=True, tzinfo=timezone.utc)
    await client.admin.command("ping")
    print(f"✅ Connected to MongoDB: {settings.database_name}")


async def close_db():
    global client
    if client:
        client.close()
        print("🔌 MongoDB connection closed")
