import pytest
from .utils import quick_login
from motor.motor_asyncio import AsyncIOMotorClient
import os

@pytest.mark.asyncio
async def test_multi_user_isolation(client):
    token_a, user_id_a = await quick_login(client, "dora")
    token_b, user_id_b = await quick_login(client, "ethan")
    assert user_id_a != user_id_b

    resp_a = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"},
        json={"messages":[{"role":"user","content":"A 的消息"}]}
    )
    assert resp_a.status_code == 200

    resp_b = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token_b}", "Content-Type": "application/json"},
        json={"messages":[{"role":"user","content":"B 的消息"}]}
    )
    assert resp_b.status_code == 200

    mongo = AsyncIOMotorClient(os.environ["MONGODB_URI"])
    coll = mongo[os.environ["MONGODB_DB"]]["messages"]
    count_a = await coll.count_documents({"user_id": user_id_a})
    count_b = await coll.count_documents({"user_id": user_id_b})
    assert count_a > 0 and count_b > 0

    doc_a = await coll.find_one({"user_id": user_id_a, "content": "A 的消息"})
    doc_b = await coll.find_one({"user_id": user_id_b, "content": "B 的消息"})
    assert doc_a is not None
    assert doc_b is not None
