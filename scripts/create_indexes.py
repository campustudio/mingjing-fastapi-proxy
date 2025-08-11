# scripts/create_indexes.py
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.environ.get("MONGODB_DB", "mingjing")

async def main():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB]

    # messages 索引
    msgs = db["messages"]
    print("[indexes] ensuring messages indexes...")
    await msgs.create_index([("user_id", 1), ("created_at", -1)],
                            name="uid_createdat_desc")
    await msgs.create_index([("user_id", 1), ("role", 1)],
                            name="uid_role")
    await msgs.create_index([("user_id", 1), ("role", 1), ("created_at", 1)],
                            name="uid_role_createdat")

    # memories 索引
    mems = db["memories"]
    print("[indexes] ensuring memories indexes...")
    await mems.create_index([("user_id", 1)], name="uid_unique", unique=True)

    print("[indexes] done.")

if __name__ == "__main__":
    asyncio.run(main())
