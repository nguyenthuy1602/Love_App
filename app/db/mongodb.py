from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

client: AsyncIOMotorClient = None


def get_database():
    return client[settings.database_name]


async def connect_db():
    global client
    client = AsyncIOMotorClient(settings.mongodb_uri)
    await client.admin.command("ping")
    print(f"✅ Connected to MongoDB: {settings.database_name}")


async def close_db():
    global client
    if client:
        client.close()
        print("🔌 MongoDB connection closed")
