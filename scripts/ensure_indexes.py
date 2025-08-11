# scripts/ensure_indexes.py
import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = os.environ["MONGODB_URI"]
MONGODB_DB  = os.environ.get("MONGODB_DB", "mingjing")

async def main():
    cli = AsyncIOMotorClient(MONGODB_URI)
    db = cli[MONGODB_DB]
    # 幂等创建索引（与应用保持一致的名字/选项）
    await db["messages"].create_index(
        [("user_id", 1), ("created_at", 1)],
        name="user_id_1_created_at_1",
        background=True,
    )
    await db["users"].create_index(
        [("username_lower", 1)],
        name="username_lower_unique",
        unique=True,
        background=True,
    )
    await db["memories"].create_index(
        [("user_id", 1)],
        name="user_id_unique",
        unique=True,
        background=True,
    )
    print("Indexes ensured.")

if __name__ == "__main__":
    asyncio.run(main())
