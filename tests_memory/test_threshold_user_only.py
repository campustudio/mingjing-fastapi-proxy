import os, asyncio, pytest
from motor.motor_asyncio import AsyncIOMotorClient
from tests.utils import quick_login
import main as main_mod

@pytest.mark.asyncio
async def test_threshold_counts_user_only(client, monkeypatch):
    # 阈值=2：发两条 user 才触发
    monkeypatch.setenv("SUMMARY_UPDATE_EVERY", "2")
    monkeypatch.setattr(main_mod, "SUMMARY_UPDATE_EVERY", 2, raising=False)

    # mock 总结函数：被调用时打点
    called = asyncio.Event()
    async def _spy_maybe_update_memory(database, user_id):
        called.set()
    # patch 到 main（因为 schedule 从 main 调）
    monkeypatch.setattr(main_mod, "maybe_update_memory", _spy_maybe_update_memory)

    token, _ = await quick_login(client, "thresholdUser")

    # 第 1 次：不会触发
    r1 = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type":"application/json"},
        json={"messages":[{"role":"user","content":"u1"}]}
    )
    assert r1.status_code == 200
    await asyncio.sleep(0.05)
    assert not called.is_set()

    # 第 2 次：达到倍数，触发
    r2 = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type":"application/json"},
        json={"messages":[{"role":"user","content":"u2"}]}
    )
    assert r2.status_code == 200
    await asyncio.wait_for(called.wait(), timeout=1.0)
