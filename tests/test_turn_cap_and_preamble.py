# tests/test_turn_cap_and_preamble.py
import os, re, pytest
from tests.utils import quick_login

@pytest.mark.asyncio
async def test_turn_cap_and_no_duplicate_preamble(client, payload_recorder, monkeypatch):
    os.environ["CONTEXT_MAX_TURNS"] = "3"  # 便于断言
    # mock 普通非流式
    from core import client as core_client
    async def _mock_call(msgs):
        payload_recorder["messages"] = list(msgs)
        return "OK"
    core_client.call_openai_chat = _mock_call

    token, _ = await quick_login(client, "capUser")
    # 多发几轮
    for i in range(6):
        await client.post("/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type":"application/json"},
            json={"messages":[{"role":"user","content":f"问{i}"}]}
        )

    msgs = payload_recorder["messages"]
    assert msgs is not None
    # 前导只出现一次
    joined = "\n".join(m.get("content","") for m in msgs if isinstance(m.get("content",""), str))
    assert joined.count("## Long-term memory summary") == 1
    # 总条数 ≤ 2 * CONTEXT_MAX_TURNS
    assert len(msgs) <= 2 * int(os.environ["CONTEXT_MAX_TURNS"])
    # 最后一条是最后的用户输入
    assert msgs[-1]["role"] == "user"
