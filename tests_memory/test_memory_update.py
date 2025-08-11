import asyncio, os, pytest
from motor.motor_asyncio import AsyncIOMotorClient
from .utils import quick_login

@pytest.mark.asyncio
async def test_memory_auto_updates_after_threshold(client):
    token, user_id = await quick_login(client, "memoryUser")
    for i in range(3):
        r = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"messages":[{"role":"user","content":f"关于偏好{i}：我喜欢结构化输出"}]}
        )
        assert r.status_code == 200

    await asyncio.sleep(0.1)

    mongo = AsyncIOMotorClient(os.environ["MONGODB_URI"])
    mem = await mongo[os.environ["MONGODB_DB"]]["memories"].find_one({"user_id": user_id})
    assert mem.get("summary", "").strip() != ""   # 有内容即可
    assert mem.get("facts")                       # facts 至少有一条
