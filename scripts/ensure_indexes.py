# scripts/ensure_indexes.py
import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def run():
    uri = os.environ["MONGODB_URI"]
    dbname = os.environ.get("MONGODB_DB", "mingjing")
    cli = AsyncIOMotorClient(uri)
    db = cli[dbname]
    await db["messages"].create_index([("user_id",1),("created_at",1)])
    await db["memories"].create_index([("user_id",1)], unique=True)
    print("Indexes ensured.")

if __name__ == "__main__":
    asyncio.run(run())
