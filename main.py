# main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import logging
from dotenv import load_dotenv
import json
load_dotenv()

from core import client as openai_client
from core.prompt_builder import build_prompt
from core.signer import inject_signature
from core.auth_utils import decode_jwt
from core.context_manager import context_manager
from core.db_mongo import db, connect

import asyncio
from core.config import CONTEXT_MAX_TURNS
from core.memory_manager import SUMMARY_UPDATE_EVERY, get_memory, maybe_update_memory

from fastapi import FastAPI
from core.db_mongo import connect, db
import os
import logging
from asyncio import wait_for, TimeoutError as AsyncTimeout

# --- main.py 顶部其它 import 之后，加这一行 ---
MEMORY_RUN_INLINE = os.getenv("MEMORY_RUN_INLINE", "false").lower() in ("1", "true", "yes", "y")


def _trim_to_turn_cap(msgs):
    cap = 2 * CONTEXT_MAX_TURNS
    if len(msgs) <= cap:
        return msgs
    # 丢掉最早的，保留最后 cap 条（这样即使你前面塞了 persona/preamble 也不会超）
    return msgs[-cap:]

# 提供可被 monkeypatch 的同名包装（tests 就会 patch main.call_openai_chat）
# 紧跟在 import 后面加
async def call_openai_chat(messages):
    # 委托到模块函数——如果测试 patch 了 core.client.call_openai_chat，这里也会跟着变
    return await openai_client.call_openai_chat(messages)

async def call_openai_chat_stream(messages):
    # 同理，转发生成器
    async for chunk in openai_client.call_openai_chat_stream(messages):
        yield chunk


app = FastAPI()

from auth_routes import router as auth_router
app.include_router(auth_router)

# 正确注册 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def _maybe_schedule_memory(user_id: str):
    """
    根据阈值判断是否触发记忆总结。
    - MEMORY_RUN_INLINE=true 时，同步执行（await），确保 Serverless 环境下请求返回前完成；
    - 否则，后台异步 create_task，不阻塞主请求。
    """
    try:
        await connect()
        database = db()
        if database is None:
            return

        # 只数 user 消息（你已有逻辑）
        total_user = await database["messages"].count_documents(
            {"user_id": user_id, "role": "user"}
        )
        should_run = bool(total_user > 0 and total_user % SUMMARY_UPDATE_EVERY == 0)
        logger.info(
            f"[memory] user={user_id} total_user={total_user} "
            f"threshold={SUMMARY_UPDATE_EVERY} should_run={should_run}"
        )
        logger.info(f"[memory] inline={MEMORY_RUN_INLINE} user={user_id}")

        if not should_run:
            return

        if MEMORY_RUN_INLINE:
            # ✅ 同步执行：请求结束前把总结写入 DB（适合 Vercel/Fly 等 Serverless）
            try:
                await wait_for(maybe_update_memory(database, user_id), timeout=8)
            except AsyncTimeout:
                logger.warning("maybe_update_memory timed out (inline)")
        else:
            # ✅ 异步执行：不阻塞请求（适合常驻容器/有后台任务能力的环境）
            async def _delayed():
                try:
                    await maybe_update_memory(database, user_id)
                except Exception as e:
                    logger.warning(f"maybe_update_memory (bg) failed: {e}")

            asyncio.create_task(_delayed())

    except Exception as e:
        logger.warning(f"schedule memory failed: {e}")


# ---- Health check (pre-warm DB & create indexes) ----
@app.get("/health", tags=["infra"])
async def health():
    try:
        # await connect()                 # 触发连接 & 幂等建索引
        # database = db()
        db_ok = False
        # if database is not None:
        #     try:
        #         # 轻量 ping，确保连接正常
        #         await database.command("ping")
        #         db_ok = True
        #     except Exception:
        #         db_ok = False
        return {"ok": True, "db": db_ok}
    except Exception as e:
        # 不额外引入依赖，直接返回简易错误结构
        return {"ok": False, "error": str(e)}

# ------------------ 对话上下文存储 ------------------
# 注意：上下文管理已迁移到 context_manager 模块

# ------------------ 核心接口：聊天代理 ------------------

@app.post("/v1/chat/completions")
async def chat_proxy(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        stream = data.get("stream", False)

        # 获取用户ID（这里使用默认用户，实际项目中可以从请求中获取）
        auth_header = request.headers.get("Authorization")
        user_id = request.headers.get("X-User-Id", "default_user")
        if auth_header and auth_header.startswith("Bearer "):
            data = decode_jwt(auth_header.split(" ",1)[1])
            if data and data.get("sub"):
                user_id = data["sub"]
        
        # 使用上下文管理器构建包含历史上下文的完整消息列表
        # messages_with_context = await context_manager.build_context_messages(messages, user_id)
        
        # 注入系统 prompt
        # system_prompt, updated_messages = build_prompt(messages_with_context)
        # updated_messages = messages
        system_prompt, updated_messages = build_prompt(messages)

        # **非流式模式处理：**
        if not stream:
            # updated_messages = _trim_to_turn_cap(updated_messages)

            # 调用 OpenAI 获取响应，传入上下文
            # 晚绑定，确保 monkeypatch(main.call_openai_chat) 能命中
            full_output = await globals()["call_openai_chat"](updated_messages)


            # tasks = []
            # # **➡️ 新增：把本轮用户输入持久化（只在最后一条确实是用户消息时写库）**
            # if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
            #     t_user = context_manager.add_user_message(messages[-1].get("content", ""), user_id)
            #     if t_user: tasks.append(t_user)
            
            # # 将AI回复添加到上下文中
            # t_assistant = context_manager.add_assistant_response(full_output, user_id)
            # if t_assistant: tasks.append(t_assistant)

            # # ✅ 等待写库完成，避免记忆任务先跑导致读不到新消息
            # if tasks:
            #     await asyncio.gather(*tasks, return_exceptions=True)

            # await _maybe_schedule_memory(user_id)

            # 返回生成的回答
            return JSONResponse(content={"message": full_output})

        else:
            # **流式模式：**
            collected_response = []  # 用于收集完整的AI回复
            
            async def token_stream():
                # 调流式之前也做一次 turn 上限裁剪
                nonlocal updated_messages
                # updated_messages = _trim_to_turn_cap(updated_messages)
                
                # 同理，晚绑定流式函数
                async for chunk in globals()["call_openai_chat_stream"](updated_messages):
                    try:
                        chunk_obj = json.loads(chunk)
                        delta = chunk_obj["choices"][0]["delta"]
                        content = delta.get("content", "")
                        if not content:
                            continue
                        
                        # 收集完整回复用于上下文管理
                        collected_response.append(content)

                        # 返回 GPT 响应，并注入签名
                        # signed = inject_signature(content)
                        # yield f"data: {signed}\n\n"

                        yield f"data: {content}\n\n"

                    except Exception as e:
                        logger.warning(f"❌ 流式 chunk 解析失败: {e}")
                
                # 流式结束后，将完整的AI回复添加到上下文
                # if collected_response:
                #     full_response = "".join(collected_response)

                #     tasks = []
                #     # **➡️ 新增：写入用户消息（仅当最后一条是用户消息）**
                #     if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
                #         t_user = context_manager.add_user_message(messages[-1].get("content", ""), user_id)
                #         if t_user: tasks.append(t_user)
                    
                #     t_assistant = context_manager.add_assistant_response(full_response, user_id)
                #     if t_assistant: tasks.append(t_assistant)

                #     if tasks:
                #         await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # await _maybe_schedule_memory(user_id)

            return StreamingResponse(token_stream(), media_type="text/event-stream", headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 某些代理会缓冲
            })
    except Exception as e:
        logger.error(f"🔴 错误: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
