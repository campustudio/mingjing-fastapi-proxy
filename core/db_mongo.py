# core/db_mongo.py
from __future__ import annotations
import os
import asyncio
from typing import Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import OperationFailure
from weakref import WeakKeyDictionary

# ============ per-event-loop 资源池 ============
# 每个事件循环独立维护 client / db / 索引就绪标记 / 索引锁
_CLIENTS: "WeakKeyDictionary[asyncio.AbstractEventLoop, AsyncIOMotorClient]" = WeakKeyDictionary()
_DBS:     "WeakKeyDictionary[asyncio.AbstractEventLoop, AsyncIOMotorDatabase]" = WeakKeyDictionary()
_READY:   "WeakKeyDictionary[asyncio.AbstractEventLoop, set[str]]" = WeakKeyDictionary()
_LOCKS:   "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = WeakKeyDictionary()

def _get_loop() -> asyncio.AbstractEventLoop:
    return asyncio.get_running_loop()

def _get_lock() -> asyncio.Lock:
    loop = _get_loop()
    lock = _LOCKS.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[loop] = lock
    return lock

def _is_ready(database: AsyncIOMotorDatabase) -> bool:
    loop = _get_loop()
    ready = _READY.get(loop)
    return ready is not None and database.name in ready

def _mark_ready(database: AsyncIOMotorDatabase) -> None:
    loop = _get_loop()
    ready = _READY.get(loop)
    if ready is None:
        ready = set()
        _READY[loop] = ready
    ready.add(database.name)

# 可选：遇到“同键但不同选项”的旧索引是否删后重建
_INDEX_STRICT = os.getenv("MONGO_INDEX_STRICT", "false").lower() in ("1","true","yes","y")

async def _create_index_safe(coll, keys, **kwargs):
    try:
        return await coll.create_index(keys, **kwargs)
    except OperationFailure as e:
        if getattr(e, "code", None) == 85:
            if _INDEX_STRICT:
                idxs = await coll.list_indexes().to_list(length=None)
                key_list = list(keys)
                def same_key(idx): return list(idx["key"].items()) == key_list
                for idx in idxs:
                    if same_key(idx):
                        await coll.drop_index(idx["name"])
                        return await coll.create_index(keys, **kwargs)
            # 非严格：跳过即可
            msg = e.details.get("errmsg") if getattr(e, "details", None) else str(e)
            print(f"[indexes] skip conflict on {coll.name} {keys} ({msg})")
            return None
        raise

async def _ensure_indexes(database: AsyncIOMotorDatabase) -> None:
    if _is_ready(database):
        return
    async with _get_lock():
        if _is_ready(database):
            return
        await _create_index_safe(database["messages"], [("user_id", 1), ("created_at", 1)], name="user_created_at")
        await _create_index_safe(database["messages"], [("user_id", 1), ("role", 1), ("created_at", 1)], name="user_role_created_at")
        await _create_index_safe(database["memories"], [("user_id", 1)], name="mem_user_unique", unique=True)
        await _create_index_safe(database["users"], [("username_lower", 1)], name="username_lower_unique", unique=True)
        _mark_ready(database)

async def connect() -> Optional[AsyncIOMotorDatabase]:
    """
    为**当前事件循环**返回（或创建）独立的 AsyncIOMotorClient/Database，并保证索引就绪。
    """
    uri = os.getenv("MONGODB_URI")
    if not uri:
        return None

    loop = _get_loop()
    db = _DBS.get(loop)
    if db is not None:
        return db

    dbname = os.getenv("MONGODB_DB", "mingjing")
    sstm   = int(os.getenv("MONGODB_SSTM", "8000"))
    pool   = int(os.getenv("MONGODB_MAX_POOL", "10"))
    app    = os.getenv("MONGODB_APPNAME", "mingjing-fastapi")

    client = AsyncIOMotorClient(
        uri,
        serverSelectionTimeoutMS=sstm,
        maxPoolSize=pool,
        uuidRepresentation="standard",
        appname=app,
    )
    # 提前探测凭据/白名单
    await client.admin.command("ping")

    db = client[dbname]
    _CLIENTS[loop] = client
    _DBS[loop] = db

    await _ensure_indexes(db)
    return db

def db() -> Optional[AsyncIOMotorDatabase]:
    """取当前事件循环的 DB 实例。"""
    return _DBS.get(_get_loop())

def client() -> Optional[AsyncIOMotorClient]:
    """取当前事件循环的 Client 实例。"""
    return _CLIENTS.get(_get_loop())

def close() -> None:
    """本地/测试时清理所有循环下的连接与状态。"""
    for c in list(_CLIENTS.values()):
        try: c.close()
        except Exception: pass
    _CLIENTS.clear()
    _DBS.clear()
    _READY.clear()
    _LOCKS.clear()
