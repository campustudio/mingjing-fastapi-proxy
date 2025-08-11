import pytest
from .utils import quick_login
from motor.motor_asyncio import AsyncIOMotorClient
import os

@pytest.mark.asyncio
async def test_chat_persists_and_responds(client, payload_recorder):
    token, user_id = await quick_login(client, "bob")

    resp = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"messages":[{"role":"user","content":"第一条"}]}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("message") == "MOCK_REPLY"

    mongo = AsyncIOMotorClient(os.environ["MONGODB_URI"])
    coll = mongo[os.environ["MONGODB_DB"]]["messages"]
    docs = [d async for d in coll.find({"user_id": user_id})]
    roles = {d["role"] for d in docs}
    assert "user" in roles and "assistant" in roles

    assert payload_recorder["messages"] is not None
    assert payload_recorder["messages"][-1]["content"] == "第一条"
