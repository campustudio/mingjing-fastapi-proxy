# core/db_mongo.py
from __future__ import annotations
import os
import asyncio
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_MONGO_CLIENT: Optional[AsyncIOMotorClient] = None
_DB: Optional[AsyncIOMotorDatabase] = None

# 仅在一次冷启动中建索引，避免重复等待
_INDEX_LOCK = asyncio.Lock()
_INDEXES_READY = False


async def connect() -> Optional[AsyncIOMotorDatabase]:
    """
    懒连接。若已连接则直接返回；若未设置 MONGODB_URI 则返回 None。
    成功连接后会做一次 ping 并保证索引已创建。
    """
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

    # Atlas / Serverless 友好参数
    _MONGO_CLIENT = AsyncIOMotorClient(
        uri,
        serverSelectionTimeoutMS=server_selection_timeout_ms,
        maxPoolSize=max_pool_size,
        uuidRepresentation="standard",
        appname=appname,
    )

    # 确认连通（这一步能更早暴露凭证/白名单问题）
    await _MONGO_CLIENT.admin.command("ping")

    _DB = _MONGO_CLIENT[dbname]
    await _ensure_indexes(_DB)

    return _DB


async def _ensure_indexes(database: AsyncIOMotorDatabase) -> None:
    """
    幂等地创建需要的索引；加锁确保一次冷启动仅跑一次。
    """
    global _INDEXES_READY
    if _INDEXES_READY:
        return

    async with _INDEX_LOCK:
        if _INDEXES_READY:
            return

        # messages：按用户 + 时间；以及用户 + 角色 + 时间（查询统计更快）
        await database["messages"].create_index(
            [("user_id", 1), ("created_at", 1)],
            name="user_created_at",
        )
        await database["messages"].create_index(
            [("user_id", 1), ("role", 1), ("created_at", 1)],
            name="user_role_created_at",
        )

        # memories：每个用户一份，唯一
        await database["memories"].create_index(
            [("user_id", 1)],
            name="mem_user_unique",
            unique=True,
        )

        # users：用户名小写唯一
        await database["users"].create_index(
            [("username_lower", 1)],
            name="username_lower_unique",
            unique=True,
        )

        _INDEXES_READY = True


def db() -> Optional[AsyncIOMotorDatabase]:
    """返回已连接的 DB；未连接则为 None。"""
    return _DB


def client() -> Optional[AsyncIOMotorClient]:
    """返回底层客户端；未连接则为 None。"""
    return _MONGO_CLIENT


def close() -> None:
    """
    主动关闭连接（测试/本地调试有用）。
    """
    global _MONGO_CLIENT, _DB, _INDEXES_READY
    if _MONGO_CLIENT:
        _MONGO_CLIENT.close()
    _MONGO_CLIENT = None
    _DB = None
    _INDEXES_READY = False
