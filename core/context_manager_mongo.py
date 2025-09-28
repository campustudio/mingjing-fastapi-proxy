# context_manager_mongo.py
from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime, timezone
import asyncio, os
from .db_mongo import db, connect
from .memory_manager import get_memory, build_memory_preamble
from typing import List, Dict, Any, Optional, Awaitable
from core.config import CONTEXT_MAX_TURNS
import os, asyncio

DB_WRITE_INLINE = os.getenv("DB_WRITE_INLINE", "false").lower() in ("1","true","yes","y")
DEFAULT_TOKEN_BUDGET = int(os.getenv("CONTEXT_TOKEN_BUDGET", "6000"))
DEFAULT_TURNS = CONTEXT_MAX_TURNS

def _estimate_tokens_of_messages(msgs: List[Dict[str, Any]]) -> int:
    total = 0
    for m in msgs:
        c = m.get("content") or ""
        total += max(1, len(c) // 3) + 8
    return total + 20

class MongoContextManager:
    def __init__(self, max_context_length: int = DEFAULT_TURNS, token_budget: int = DEFAULT_TOKEN_BUDGET):
        self.max_context_length = max_context_length
        self.token_budget = token_budget

    async def _ensure(self):
        await connect()

    async def build_context_messages(self, new_messages: List[Dict[str, Any]], user_id: str = "default_user") -> List[Dict[str, Any]]:
        await self._ensure()
        database = db()
        if database is None:
            # 兜底：只返回这次请求里最后一条 user（如果有）
            if new_messages and isinstance(new_messages[-1], dict):
                nm = new_messages[-1]
                if nm.get("role") == "user" and nm.get("content"):
                    return [{"role": "user", "content": nm["content"]}]
            return []

        # 1) 长时记忆前缀（0-2 条 assistant）
        mem = await get_memory(database, user_id)
        preamble = build_memory_preamble(mem)

        # 2) 拉历史记录（升序）
        coll = database["messages"]
        cursor = coll.find({"user_id": user_id}).sort("created_at", 1)
        history = [{"role": d.get("role","user"), "content": d.get("content","")} async for d in cursor]

        # 仅保留 (N-1) 个 turn => 2*(N-1) 条历史
        keep_hist = 2 * max(self.max_context_length - 1, 0)
        history = history[-keep_hist:] if keep_hist > 0 else []

        # 3) 只取本次请求里的“最后一条 user”
        last_user = None
        if new_messages and isinstance(new_messages[-1], dict):
            nm = new_messages[-1]
            if nm.get("role") == "user" and nm.get("content"):
                last_user = {"role": "user", "content": nm["content"]}

        # 4) 合并顺序：preamble + history + last_user
        merged: List[Dict[str, Any]] = []
        merged.extend(preamble)
        merged.extend(history)
        if last_user:
            merged.append(last_user)

        # 5) 按条数硬性裁剪：保证加上 build_prompt 的 1 条 system 后总数 <= 2*N
        max_without_system = max(2 * self.max_context_length - 1, 0)
        if len(merged) > max_without_system:
            overflow = len(merged) - max_without_system

            # 优先从“历史最早处”裁剪
            drop_from_hist = min(overflow, len(history))
            if drop_from_hist:
                history = history[drop_from_hist:]
                merged = preamble + history + ([last_user] if last_user else [])
                overflow = len(merged) - max_without_system

            # 若仍超标，再从 preamble 头部裁剪（始终保留 last_user）
            if overflow > 0 and preamble:
                preamble = preamble[min(overflow, len(preamble)):]
                merged = preamble + history + ([last_user] if last_user else [])

        # 6) 再按 token 预算做细裁（不丢最后一条消息）
        def fit_budget(msgs: List[Dict[str, Any]], budget: int) -> List[Dict[str, Any]]:
            if not msgs:
                return msgs
            last = msgs[-1]
            kept: List[Dict[str, Any]] = []
            for m in msgs[:-1]:
                kept.append(m)
                if _estimate_tokens_of_messages(kept + [last]) > self.token_budget:
                    kept.pop()
                    break
            kept.append(last)
            while _estimate_tokens_of_messages(kept) > self.token_budget and len(kept) > 1:
                kept.pop(0)
            return kept

        merged = fit_budget(merged, self.token_budget)
        return merged

    def _schedule(self, coro):
        """
        在 Serverless（或配置 DB_WRITE_INLINE=true）下，返回协程给调用方 await；
        其他环境返回 Task（后台写入）。
        """
        if DB_WRITE_INLINE:
            return coro
        try:
            loop = asyncio.get_running_loop()
            return loop.create_task(coro)
        except RuntimeError:
            # 没有运行中的 loop（Serverless 冷启动/收尾阶段），退回协程
            return coro

    def add_message_to_context(self, message: Dict[str, Any], user_id: str = "default_user"):
        role = message.get("role")
        content = message.get("content")
        if not content or role not in {"system", "user", "assistant", "tool"}:
            return None
        # 返回 Task，供调用方 await
        return self._schedule(self._insert_message(role, content, user_id))

    def add_user_message(self, message_content: str, user_id: str = "default_user"):
        if not message_content:
            return None
        return self._schedule(self._insert_message("user", message_content, user_id))

    def add_assistant_response(self, response_content: str, user_id: str = "default_user"):
        if not response_content:
            return None
        return self._schedule(self._insert_message("assistant", response_content, user_id))

    def clear_context(self, user_id: str = "default_user"):
        return self._schedule(self._insert_message("system", "[context cleared]", user_id))

    async def _insert_message(self, role: str, content: str, user_id: str):
        await self._ensure()
        database = db()
        if database is None:
            return
        await database["messages"].insert_one({
            "user_id": user_id,
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc),
        })
