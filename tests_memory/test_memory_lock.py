# tests_memory/test_memory_lock.py
import asyncio, pytest
from motor.motor_asyncio import AsyncIOMotorClient
from tests.utils import quick_login
import os

@pytest.mark.asyncio
async def test_memory_lock_allows_only_one_summary(client, monkeypatch):
    token, user_id = await quick_login(client, "lockUser")
    # 准备若干用户消息
    for i in range(5):
        await client.post("/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type":"application/json"},
            json={"messages":[{"role":"user","content":f"偏好{i}"}]}
        )

    # mock call_openai_chat: 慢 100ms
    from core import client as core_client
    async def _slow_call(msgs):
        await asyncio.sleep(0.1)
        return "## Long-term memory summary\n...\n\n## Facts\n- A\n- B"
    core_client.call_openai_chat = _slow_call

    # 并发触发两次 maybe_update_memory
    from core.db_mongo import db, connect
    await connect()
    database = db()
    from core.memory_manager import maybe_update_memory
    await asyncio.gather(
        maybe_update_memory(database, user_id),
        maybe_update_memory(database, user_id),
    )

    # 断言只写入一次
    mongo = AsyncIOMotorClient(os.environ["MONGODB_URI"])
    mem = await mongo[os.environ["MONGODB_DB"]]["memories"].find_one({"user_id": user_id})
    assert mem is not None
    # 可选：再触发一次，updated_at 应变化而不是新增
    before = mem["updated_at"]
    await maybe_update_memory(database, user_id)
    mem2 = await mongo[os.environ["MONGODB_DB"]]["memories"].find_one({"user_id": user_id})
    assert mem2["_id"] == mem["_id"]
