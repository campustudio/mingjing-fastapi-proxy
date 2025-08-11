# memory_manager.py
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Any, Dict
import asyncio

MEMORY_ENABLED = os.getenv("MEMORY_ENABLED", "true").lower() != "false"
SUMMARY_UPDATE_EVERY = int(os.getenv("SUMMARY_UPDATE_EVERY", "5"))
SUMMARY_WINDOW_TURNS = int(os.getenv("SUMMARY_WINDOW_TURNS", "40"))
SUMMARY_MAXLEN_CHARS = int(os.getenv("SUMMARY_MAXLEN_CHARS", "2000"))

MEMORY_PREAMBLE_SUMMARY_TITLE = "## Long-term memory summary"
MEMORY_PREAMBLE_FACTS_TITLE = "## Facts"

# 每个用户一个 Lock，避免并发跑总结
_USER_LOCKS: dict[str, asyncio.Lock] = {}

def _get_user_lock(user_id: str) -> asyncio.Lock:
    lock = _USER_LOCKS.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _USER_LOCKS[user_id] = lock
    return lock

def _now():
    return datetime.now(timezone.utc)

def _parse_summary_and_facts(text: str) -> tuple[str, list[str]]:
    """
    从模型输出里抽取：
      - summary：只保留“长期记忆概述”部分（如无标题则自动补上）
      - facts：只取 ## Facts 标题下的 - 项
    同时避免重复加标题。
    """
    if not isinstance(text, str):
        text = str(text or "")

    lines = text.splitlines()
    facts: list[str] = []
    summary_lines: list[str] = []

    in_facts = False
    for line in lines:
        stripped = line.strip()
        # 进入 Facts 段落
        if stripped.lower().startswith(MEMORY_PREAMBLE_FACTS_TITLE.lower()):
            in_facts = True
            continue

        if in_facts:
            # 收集 - 开头的要点
            if stripped.startswith("- "):
                facts.append(stripped[2:].strip())
            # 遇到新标题则结束 facts 收集
            elif stripped.startswith("#"):
                in_facts = False
                summary_lines.append(line)
        else:
            summary_lines.append(line)

    # 拼 summary，并裁剪空行
    summary_text = "\n".join(l for l in summary_lines if l.strip() != "").strip()

    # 如未以我们期望的标题开头，自动补标题
    if not summary_text.lstrip().lower().startswith(MEMORY_PREAMBLE_SUMMARY_TITLE.lower()):
        summary_text = f"{MEMORY_PREAMBLE_SUMMARY_TITLE}\n{summary_text}"

    # 如果 facts 还是空，兜底从全文里抓 - 列表（兼容模型未按模板输出）
    if not facts:
        for line in lines:
            if line.strip().startswith("- "):
                facts.append(line.strip()[2:].strip())

    return summary_text, facts


async def get_memory(db: AsyncIOMotorDatabase, user_id: str) -> Optional[Dict[str, Any]]:
    return await db["memories"].find_one({"user_id": user_id})

def default_memory(user_id: str) -> Dict[str, Any]:
    return {"user_id": user_id, "summary": "", "facts": []}

async def get_memory_or_default(db, user_id: str) -> Dict[str, Any]:
    return (await get_memory(db, user_id)) or default_memory(user_id)
    
# async def get_memory_or_default(database, user_id: str) -> Dict[str, Any]:
#     """
#     读取用户的长时记忆文档；没有则返回空结构。
#     预期集合名: memories
#     文档结构例子:
#       { "user_id": "xxx", "summary": "……", "facts": ["a", "b"], "updated_at": ... }
#     """
#     if database is None:
#         return {}
#     doc = await database["memories"].find_one({"user_id": user_id})
#     return doc or {"user_id": user_id, "summary": "", "facts": []}

async def set_memory(db: AsyncIOMotorDatabase, user_id: str, summary: str, facts: list[str] | None = None):
    doc = {"user_id": user_id, "summary": summary, "facts": facts or [], "updated_at": _now()}
    await db["memories"].update_one({"user_id": user_id}, {"$set": doc}, upsert=True)

async def _build_summary_prompt(prev_summary: str, msgs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    sys = {
        "role": "system",
        "content": (
            "你是一名对话总结助手。请把近期对话压缩为用户画像与长期记忆，"
            "保留：人物偏好、观点、目标、禁忌、项目上下文、已做决定、待办事项。"
            "输出两段 Markdown：\n"
            f"{MEMORY_PREAMBLE_SUMMARY_TITLE}\n(200-400字，尽量客观)\n\n"
            f"{MEMORY_PREAMBLE_FACTS_TITLE}\n- 用要点列出稳定事实/偏好\n"
        )
    }
    prev = {"role": "system", "content": f"之前的长期记忆（可为空）：\n{prev_summary or ''}"}
    compact = [{"role": m.get("role","user"), "content": m.get("content","")} for m in msgs if m.get("content")]
    return [sys, prev] + compact

async def maybe_update_memory(db: AsyncIOMotorDatabase, user_id: str):
    if not MEMORY_ENABLED or not user_id:
        return

    lock = _get_user_lock(user_id)
    async with lock:
        mem = await get_memory(db, user_id)
        last_ts = mem.get("updated_at") if mem else None

        q = {"user_id": user_id, "role": "user"}
        if last_ts:
            q["created_at"] = {"$gt": last_ts}
        new_user_count = await db["messages"].count_documents(q)

        # ✅ 你现有的“首次/阈值”策略保持不变（方案 C）
        if mem is None:
            # 首次：放宽触发策略（你现在的逻辑）
            total_user = await db["messages"].count_documents({"user_id": user_id, "role": "user"})
            if total_user < 3:  # 或你设的首次阈值
                return
        else:
            if new_user_count < SUMMARY_UPDATE_EVERY:
                return

        turns = SUMMARY_WINDOW_TURNS
        cursor = db["messages"].find({"user_id": user_id}).sort("created_at", -1).limit(turns * 2)
        recent: List[Dict[str, Any]] = [doc async for doc in cursor]
        recent.reverse()

        from core.client import call_openai_chat
        prompt_msgs = await _build_summary_prompt(mem.get("summary","") if mem else "", recent)
        summary_text = await call_openai_chat(prompt_msgs)
        if not isinstance(summary_text, str):
            summary_text = str(summary_text)
        if len(summary_text) > SUMMARY_MAXLEN_CHARS:
            summary_text = summary_text[:SUMMARY_MAXLEN_CHARS]

        facts: list[str] = []
        try:
            for line in summary_text.splitlines():
                if line.strip().startswith("- "):
                    facts.append(line.strip()[2:].strip())
        except Exception:
            pass

        await set_memory(db, user_id, summary_text, facts)

def build_memory_preamble(mem):
    if not mem:
        return []
    out = []
    summary = (mem.get("summary") or "").strip()
    facts = mem.get("facts") or []

    if summary:
        # 如果 summary 已经以我们定义的标题开头，就不要再加一遍
        content_summary = (
            summary if summary.lstrip().lower().startswith(MEMORY_PREAMBLE_SUMMARY_TITLE.lower())
            else f"{MEMORY_PREAMBLE_SUMMARY_TITLE}\n{summary}"
        )
        out.append({"role": "assistant", "content": content_summary})

    if facts:
        joined = "\n".join(f"- {x}" for x in facts[:20])
        out.append({"role": "assistant", "content": f"{MEMORY_PREAMBLE_FACTS_TITLE}\n{joined}"})

    return out

