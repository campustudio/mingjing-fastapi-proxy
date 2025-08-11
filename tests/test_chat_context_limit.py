import pytest
from .utils import quick_login
import os

@pytest.mark.asyncio
async def test_context_is_limited_by_max_turns(client, payload_recorder):
    token, _ = await quick_login(client, "charlie")

    for i in range(6):
        resp = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"messages":[{"role":"user","content":f"问{i}"}]}
        )
        assert resp.status_code == 200

    msgs = payload_recorder["messages"]
    assert msgs is not None
    assert len(msgs) <= 2*int(os.environ.get("CONTEXT_MAX_TURNS","3"))
    assert msgs[-1]["content"] == "问5"
