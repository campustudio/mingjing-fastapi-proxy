import os, json, asyncio, pytest
from motor.motor_asyncio import AsyncIOMotorClient
from tests.utils import quick_login
from core import client as core_client
import main as main_mod

@pytest.mark.asyncio
async def test_stream_concat_robustness(client, monkeypatch):
    # 阈值调高：避免本用例触发记忆逻辑干扰
    monkeypatch.setenv("SUMMARY_UPDATE_EVERY", "99")

    # mock 流式输出：包含空字符串和空格
    async def _mock_stream(msgs):
        for chunk in ["甲", "", " ", "乙", "", "丙"]:
            yield json.dumps({"choices":[{"delta":{"content":chunk}}]})
    core_client.call_openai_chat_stream = _mock_stream
    # 关键：main 里的包装器也要指向这份 mock
    main_mod.call_openai_chat_stream = _mock_stream   # 👈 新增

    token, user_id = await quick_login(client, "streamRobust")
    r = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type":"application/json"},
        json={"messages":[{"role":"user","content":"走流式"}], "stream": True}
    )
    assert r.status_code == 200
    assert "data:" in r.text

    # 等落库
    await asyncio.sleep(0.05)

    mongo = AsyncIOMotorClient(os.environ["MONGODB_URI"])
    docs = [d async for d in mongo[os.environ["MONGODB_DB"]]["messages"].find({"user_id": user_id, "role":"assistant"})]
    assert len(docs) == 1
    # 按现在实现：空字符串跳过、空格保留 => "甲 乙丙"
    assert docs[0]["content"] == "甲 乙丙"
