from __future__ import annotations
import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_MONGO_CLIENT: Optional[AsyncIOMotorClient] = None
_DB: Optional[AsyncIOMotorDatabase] = None

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "mingjing")

async def connect() -> Optional[AsyncIOMotorDatabase]:
    global _MONGO_CLIENT, _DB
    if not MONGODB_URI:
        return None
    if _DB is None:
        _MONGO_CLIENT = AsyncIOMotorClient(MONGODB_URI)
        _DB = _MONGO_CLIENT[MONGODB_DB]
        await _DB["messages"].create_index([("user_id", 1), ("created_at", 1)])
        await _DB["users"].create_index("username_lower", unique=True)
    return _DB

def db() -> Optional[AsyncIOMotorDatabase]:
    return _DB
