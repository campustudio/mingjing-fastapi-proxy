# tests/test_chat_streaming.py
import json, asyncio, pytest
import main as main_mod

@pytest.mark.asyncio
async def test_stream_mode_persists_and_then_schedules(client, monkeypatch):
    # 阈值改成 1（双保险）
    monkeypatch.setenv("SUMMARY_UPDATE_EVERY", "1")
    monkeypatch.setattr(main_mod, "SUMMARY_UPDATE_EVERY", 1, raising=False)

    # ✅ 关键：同时 patch main.call_openai_chat_stream
    async def _mock_stream(msgs):
        for chunk in ["甲", "乙", "丙"]:
            yield json.dumps({"choices":[{"delta":{"content":chunk}}]})
    monkeypatch.setattr(main_mod, "call_openai_chat_stream", _mock_stream, raising=True)

    #（可选）也 patch core.client；只是为了一致性
    from core import client as core_client
    core_client.call_openai_chat_stream = _mock_stream

    called = asyncio.Event()
    async def _spy_maybe_update_memory(database, user_id):
        docs = [d async for d in database["messages"].find({"user_id": user_id, "role":"assistant"})]
        assert len(docs) == 1 and docs[0]["content"] == "甲乙丙"
        called.set()
    monkeypatch.setattr(main_mod, "maybe_update_memory", _spy_maybe_update_memory, raising=True)

    # 发起流式请求
    from tests.utils import quick_login
    token, user_id = await quick_login(client, "streamUser")
    r = await client.post("/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type":"application/json"},
        json={"messages":[{"role":"user","content":"流式一条"}], "stream": True}
    )
    assert r.status_code == 200
    assert "data:" in r.text

    # 等待后台任务触发
    await asyncio.wait_for(called.wait(), timeout=2.0)
