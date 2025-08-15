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

# ---------------- per-event-loop 资源 ----------------
# per-loop 锁：避免跨事件循环复用导致 "Event loop is closed"
_INDEX_LOCKS: "WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = WeakKeyDictionary()
# per-loop 就绪标记：每个 loop 只为同一个 DB 建一次索引
_INDEX_READY_BY_LOOP: "WeakKeyDictionary[asyncio.AbstractEventLoop, set[str]]" = WeakKeyDictionary()

def _get_index_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _INDEX_LOCKS.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _INDEX_LOCKS[loop] = lock
    return lock

def _is_index_ready_for_db(database: AsyncIOMotorDatabase) -> bool:
    loop = asyncio.get_running_loop()
    ready = _INDEX_READY_BY_LOOP.get(loop)
    return ready is not None and database.name in ready

def _mark_index_ready_for_db(database: AsyncIOMotorDatabase) -> None:
    loop = asyncio.get_running_loop()
    ready = _INDEX_READY_BY_LOOP.get(loop)
    if ready is None:
        ready = set()
        _INDEX_READY_BY_LOOP[loop] = ready
    ready.add(database.name)

_INDEXES_READY = False

# 可选严格模式：遇到“同键不同名/选项”的旧索引时是否先删再建
_MONGO_INDEX_STRICT = os.getenv("MONGO_INDEX_STRICT", "false").lower() in ("1", "true", "yes", "y")

async def _create_index_safe(coll, keys, **kwargs):
    try:
        return await coll.create_index(keys, **kwargs)
    except OperationFailure as e:
        if getattr(e, "code", None) == 85:
            if _MONGO_INDEX_STRICT:
                idxs = await coll.list_indexes().to_list(length=None)
                key_list = list(keys)
                def same_key(idx):
                    return list(idx["key"].items()) == key_list
                for idx in idxs:
                    if same_key(idx):
                        await coll.drop_index(idx["name"])
                        return await coll.create_index(keys, **kwargs)
            # 非严格：跳过
            msg = e.details.get("errmsg") if getattr(e, "details", None) else str(e)
            print(f"[indexes] skip conflict on {coll.name} {keys} ({msg})")
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
    # 及早发现凭据/白名单错误
    await _MONGO_CLIENT.admin.command("ping")

    _DB = _MONGO_CLIENT[dbname]
    await _ensure_indexes(_DB)
    return _DB

async def _ensure_indexes(database: AsyncIOMotorDatabase) -> None:
    # 第一层检查：同一个 loop / 同一个 DB 已经建过就跳过
    if _is_index_ready_for_db(database):
        return

    async with _get_index_lock():
        # 双检，防止并发重复建
        if _is_index_ready_for_db(database):
            return

        # messages：时间线/统计友好
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
        # memories：每个用户唯一
        await _create_index_safe(
            database["memories"],
            [("user_id", 1)],
            name="mem_user_unique",
            unique=True,
        )
        # users：用户名小写唯一
        await _create_index_safe(
            database["users"],
            [("username_lower", 1)],
            name="username_lower_unique",
            unique=True,
        )

        _mark_index_ready_for_db(database)
        
def db() -> Optional[AsyncIOMotorDatabase]:
    return _DB

def client() -> Optional[AsyncIOMotorClient]:
    return _MONGO_CLIENT

def close() -> None:
    """测试/本地调试时主动清理连接与缓存。"""
    global _MONGO_CLIENT, _DB
    if _MONGO_CLIENT:
        _MONGO_CLIENT.close()
    _MONGO_CLIENT = None
    _DB = None
    # 清理 per-loop 缓存，避免下次测试串状态
    _INDEX_LOCKS.clear()
    _INDEX_READY_BY_LOOP.clear()
