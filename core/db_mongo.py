# core/db_mongo.py
from __future__ import annotations
import os
import asyncio
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import OperationFailure   # ← 新增
from weakref import WeakKeyDictionary  # ← 新增

_MONGO_CLIENT: Optional[AsyncIOMotorClient] = None
_DB: Optional[AsyncIOMotorDatabase] = None

# ❌ 不要在模块级直接创建 asyncio.Lock()
# _INDEX_LOCK = asyncio.Lock()
# ✅ 改为：按“事件循环”维护锁，避免跨循环复用
_INDEX_LOCKS: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = WeakKeyDictionary()

def _get_index_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _INDEX_LOCKS.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _INDEX_LOCKS[loop] = lock
    return lock

_INDEXES_READY = False

# 可选：严格模式，发现“同键不同名/选项”就丢弃旧索引并统一重建
_MONGO_INDEX_STRICT = os.getenv("MONGO_INDEX_STRICT", "false").lower() in ("1", "true", "yes", "y")

async def _create_index_safe(coll, keys, **kwargs):
    """
    幂等建索引。如果遇到 85（IndexOptionsConflict：同键已存在但名字/选项不同）：
    - 默认：跳过，不中断（生产更稳）
    - MONGO_INDEX_STRICT=true：删除同键旧索引后按期望选项重建（更一致）
    """
    try:
        return await coll.create_index(keys, **kwargs)
    except OperationFailure as e:
        if getattr(e, "code", None) == 85:
            # 同键不同名/选项
            if _MONGO_INDEX_STRICT:
                # 找到“键完全一致”的旧索引并删除后重建
                idxs = await coll.list_indexes().to_list(length=None)
                key_list = list(keys)  # [('user_id', 1), ('created_at', 1)] 这种
                def same_key(idx):
                    # idx["key"] 是有序字典，转为 list(tuple) 比较
                    return list(idx["key"].items()) == key_list
                for idx in idxs:
                    if same_key(idx):
                        await coll.drop_index(idx["name"])
                        return await coll.create_index(keys, **kwargs)
            # 非严格：跳过
            print(f"[indexes] skip conflict on {coll.name} {keys} ({e.details.get('errmsg')})")
            return None
        raise

async def connect() -> Optional[AsyncIOMotorDatabase]:
    global _MONGO_CLIENT, _DB

    uri = os.getenv("MONGODB_URI")
    if not uri:
        return None

    if _DB is not None:
        return _DB

    dbname = os.getenv("MONGODB_DB", "mingjing")
    server_selection_timeout_ms = int(os.getenv("MONGODB_SSTM", "8000"))
    max_pool_size = int(os.getenv("MONGODB_MAX_POOL", "10"))
    appname = os.getenv("MONGODB_APPNAME", "mingjing-fastapi")

    _MONGO_CLIENT = AsyncIOMotorClient(
        uri,
        serverSelectionTimeoutMS=server_selection_timeout_ms,
        maxPoolSize=max_pool_size,
        uuidRepresentation="standard",
        appname=appname,
    )

    await _MONGO_CLIENT.admin.command("ping")

    _DB = _MONGO_CLIENT[dbname]
    await _ensure_indexes(_DB)

    return _DB

async def _ensure_indexes(database: AsyncIOMotorDatabase) -> None:
    # 用“按事件循环隔离”的锁
    async with _get_index_lock():
        # messages
        await _create_index_safe(
            database["messages"],
            [("user_id", 1), ("created_at", 1)],
            name="user_created_at",
        )
        await _create_index_safe(
            database["messages"],
            [("user_id", 1), ("role", 1), ("created_at", 1)],
            name="user_role_created_at",
        )
        # memories：唯一
        await _create_index_safe(
            database["memories"],
            [("user_id", 1)],
            name="mem_user_unique",
            unique=True,
        )
        # users：唯一
        await _create_index_safe(
            database["users"],
            [("username_lower", 1)],
            name="username_lower_unique",
            unique=True,
        )
        
def db() -> Optional[AsyncIOMotorDatabase]:
    return _DB

def client() -> Optional[AsyncIOMotorClient]:
    return _MONGO_CLIENT

def close() -> None:
    global _MONGO_CLIENT, _DB, _INDEXES_READY
    if _MONGO_CLIENT:
        _MONGO_CLIENT.close()
    _MONGO_CLIENT = None
    _DB = None
    _INDEXES_READY = False
