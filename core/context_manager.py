from __future__ import annotations
import os
from typing import List, Dict, Any
from core.config import CONTEXT_MAX_TURNS

MONGODB_URI = os.getenv("MONGODB_URI")
PURE_CONTEXT = os.getenv("PURE_CONTEXT", "false").lower() in ("1", "true", "yes", "y")

if PURE_CONTEXT:
    class NoopContextManager:
        """
        纯净模式：不维护任何上下文，也不做任何写入。
        """
        def __init__(self, max_context_length: int = 10):
            self.max_context_length = max_context_length

        async def build_context_messages(self, new_messages: List[Dict[str, Any]], user_id: str = "default_user") -> List[Dict[str, Any]]:
            # 仅返回本次请求的最后一条 user（如无则空），不附带历史
            if new_messages and isinstance(new_messages[-1], dict):
                maybe = new_messages[-1]
                if maybe.get("role") == "user" and maybe.get("content"):
                    return [{"role": "user", "content": maybe["content"]}]
            return []

        def add_message_to_context(self, message: Dict[str, Any], user_id: str = "default_user"):
            return

        def add_user_message(self, message_content: str, user_id: str = "default_user"):
            return

        def add_assistant_response(self, response_content: str, user_id: str = "default_user"):
            return

        def clear_context(self, user_id: str = "default_user"):
            return

    context_manager = NoopContextManager(max_context_length=CONTEXT_MAX_TURNS)

elif MONGODB_URI:
    from .context_manager_mongo import MongoContextManager
    context_manager = MongoContextManager(max_context_length=CONTEXT_MAX_TURNS)
else:
    class ContextManager:
        def __init__(self, max_context_length: int = 10):
            self.user_contexts: Dict[str, List[Dict[str, Any]]] = {}
            self.max_context_length = max_context_length
        
        def get_user_context(self, user_id: str = "default_user") -> List[Dict[str, Any]]:
            return self.user_contexts.get(user_id, [])

        async def build_context_messages(self, new_messages: List[Dict[str, Any]], user_id: str = "default_user") -> List[Dict[str, Any]]:
            """
            只带入 (N-1) 个历史 turn（= 2*(N-1) 条历史消息）+ 本次“最后一条 user 消息”。
            让 build_prompt 再去插入 1 条 system，从而总长 <= 2*N。
            """
            # 历史消息（已包含 user/assistant 交替）
            history = self.get_user_context(user_id)

            # 只保留 (N-1) 个 turn 的历史 => 2*(N-1) 条
            keep_hist = 2 * max(self.max_context_length - 1, 0)
            trimmed_hist = history[-keep_hist:] if keep_hist > 0 else []

            # 从本次请求里只取“最后一条 user 消息”
            last_user = None
            if new_messages and isinstance(new_messages[-1], dict):
                maybe = new_messages[-1]
                if maybe.get("role") == "user" and maybe.get("content"):
                    last_user = {"role": "user", "content": maybe["content"]}

            # 组合
            if last_user:
                return trimmed_hist + [last_user]
            return trimmed_hist

        def add_message_to_context(self, message: Dict[str, Any], user_id: str = "default_user"):
            context = self.user_contexts.setdefault(user_id, [])
            context.append(message)
            if len(context) > self.max_context_length:
                self.user_contexts[user_id] = context[-self.max_context_length:]

        def add_user_message(self, message_content: str, user_id: str = "default_user"):
            if not message_content: return
            self.add_message_to_context({ "role": "user", "content": message_content }, user_id)

        def add_assistant_response(self, response_content: str, user_id: str = "default_user"):
            if not response_content: return
            self.add_message_to_context({ "role": "assistant", "content": response_content }, user_id)

        def clear_context(self, user_id: str = "default_user"):
            if user_id in self.user_contexts:
                del self.user_contexts[user_id]

    context_manager = ContextManager(max_context_length=CONTEXT_MAX_TURNS)
