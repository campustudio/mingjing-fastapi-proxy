import os, asyncio, json
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from tests.utils import quick_login

@pytest.mark.asyncio
async def test_memory_parse_robustness(client, monkeypatch):
    # 阈值设为 1：本轮必触发
    monkeypatch.setenv("SUMMARY_UPDATE_EVERY", "1")
    import main as main_mod
    monkeypatch.setattr(main_mod, "SUMMARY_UPDATE_EVERY", 1, raising=False)

    # 针对“总结助手提示”返回“非规整”文本；对普通聊天仍返回 MOCK_REPLY
    from core import client as core_client

    async def _smart_mock_call_openai_chat(msgs):
        # 如果是记忆总结的系统提示，就返回不规整内容
        if msgs and "对话总结助手" in msgs[0].get("content", ""):
            return (
                "这是一段没有标题的总结。\n"
                "可能包含一些事实：\n"
                "* 喜欢结构化输出\n"
                "— 正在构建明镜项目\n"   # 注意是破折号，不是标准 "- "
                "最后一行。"
            )
        return "MOCK_REPLY"

    core_client.call_openai_chat = _smart_mock_call_openai_chat

    token, user_id = await quick_login(client, "robustUser")
    # 触发一次对话（非流式）
    r = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type":"application/json"},
        json={"messages":[{"role":"user","content":"记一下：我喜欢结构化输出"}]}
    )
    assert r.status_code == 200

    mongo = AsyncIOMotorClient(os.environ["MONGODB_URI"])
    coll = mongo[os.environ["MONGODB_DB"]]["memories"]

    mem = None
    for _ in range(30):  # 30 * 0.05s = 1.5s 上限
        mem = await coll.find_one({"user_id": user_id})
        if mem:
            break
        await asyncio.sleep(0.05)

    assert mem is not None

    # summary 有内容即可
    assert mem.get("summary","").strip() != ""
    # facts 至少解析出一条（不规整也尽量提取）
    assert isinstance(mem.get("facts",[]), list)
    assert len(mem["facts"]) >= 1
