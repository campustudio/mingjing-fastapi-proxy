import pytest
from .utils import quick_login

@pytest.mark.asyncio
async def test_context_includes_memory_preamble(client, payload_recorder):
    token, user_id = await quick_login(client, "preambleUser")
    # 触发两轮以生成记忆
    for i in range(2):
        await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"messages":[{"role":"user","content":f"我更偏好要点列表{i}"}]}
        )
    r = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"messages":[{"role":"user","content":"现在问个新问题"}]}
    )
    assert r.status_code == 200
    msgs = payload_recorder["messages"]
    joined = "\n".join(m.get("content","") for m in msgs[:3] if isinstance(m.get("content",""), str))
    assert "## Long-term memory summary" in joined
