# main.py
import logging
import json
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import Body

load_dotenv()

from core import client as openai_client
from core.prompt_builder import build_prompt
from core.auth_utils import decode_jwt
from core.context_manager import context_manager
from core.db_mongo import db, connect
from core.config import CONTEXT_MAX_TURNS
from core.memory_manager import SUMMARY_UPDATE_EVERY, get_memory, maybe_update_memory
from bson import ObjectId


import asyncio
from asyncio import wait_for, TimeoutError as AsyncTimeout
from auth_routes import router as auth_router
import os

# --- main.py 顶部其它 import 之后，加这一行 ---
MEMORY_RUN_INLINE = os.getenv("MEMORY_RUN_INLINE", "false").lower() in ("1", "true", "yes", "y")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(auth_router)
# 正确注册 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Health check (pre-warm DB & create indexes) ----
@app.get("/health", tags=["infra"])
async def health():
    try:
        await connect() # 触发连接 & 幂等建索引
        database = db()
        db_ok = False
        if database is not None:
            try:
                # 轻量 ping，确保连接正常
                await database.command("ping")
                db_ok = True
            except Exception:
                db_ok = False
        return {"ok": True, "db": db_ok}
    except Exception as e:
        # 不额外引入依赖，直接返回简易错误结构
        return {"ok": False, "error": str(e)}

# 裁剪消息到 turn 上限
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
        session_id = request.headers.get("X-Session-Id") or None
        if auth_header and auth_header.startswith("Bearer "):
            data = decode_jwt(auth_header.split(" ",1)[1])
            if data and data.get("sub"):
                user_id = data["sub"]
        
        # 记录当前上下文管理器类型（便于诊断 PURE_CONTEXT / Mongo 是否生效）
        try:
            logger.info(f"[context] manager={type(context_manager).__name__}")
        except Exception:
            pass

        # 使用上下文管理器构建包含历史上下文的完整消息列表（按会话，若提供 session_id）
        messages_with_context = await context_manager.build_context_messages(messages, user_id, session_id)
        
        # 注入系统 prompt（基于上下文后的消息）
        system_prompt, updated_messages = build_prompt(messages_with_context)

        # **非流式模式处理：**
        if not stream:
            # updated_messages = _trim_to_turn_cap(updated_messages)

            # 调用 OpenAI 获取响应，传入上下文
            # 晚绑定，确保 monkeypatch(main.call_openai_chat) 能命中
            full_output = await globals()["call_openai_chat"](updated_messages)
            # ✅ 将本轮用户输入与 AI 回复写入数据库（恢复持久化）
            # 确保已建立 DB 连接
            try:
                await connect()
            except Exception as _e:
                logger.warning(f"db connect before write failed: {_e}")
            tasks = []
            if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
                t_user = context_manager.add_user_message(messages[-1].get("content", ""), user_id)
                if t_user:
                    tasks.append(t_user)
                else:
                    logger.warning("add_user_message returned None (context manager may be Noop or content empty)")
            t_assistant = context_manager.add_assistant_response(full_output, user_id)
            if t_assistant:
                tasks.append(t_assistant)
            else:
                logger.warning("add_assistant_response returned None (context manager may be Noop or content empty)")

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            # 额外：将消息写入 messages 集合并附带 session_id（便于会话维度读取）
            try:
                database = db()
                if database is not None:
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                    if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
                        await database["messages"].insert_one({
                            "user_id": user_id,
                            "session_id": session_id,
                            "role": "user",
                            "content": messages[-1].get("content", ""),
                            "created_at": now,
                        })
                        # 更新/创建会话摘要
                        if session_id:
                            content_preview = messages[-1].get("content", "")
                            # 优先按 ObjectId 更新；若无法转换，退回字符串 _id，但不 upsert，避免制造重复会话
                            try:
                                oid = ObjectId(session_id)
                                await database["sessions"].update_one(
                                    {"_id": oid, "user_id": user_id},
                                    {"$set": {"updated_at": now, "last_message_preview": content_preview[:60]},
                                     "$inc": {"message_count": 1}},
                                )
                            except Exception:
                                await database["sessions"].update_one(
                                    {"_id": session_id, "user_id": user_id},
                                    {"$set": {"updated_at": now, "last_message_preview": content_preview[:60]},
                                     "$inc": {"message_count": 1}},
                                )
                            # 自动标题：仅当当前标题为“未命名会话”时用首条 user 文本前20字命名
                            auto_title = content_preview.strip().replace("\n", " ")[:20]
                            if auto_title:
                                await database["sessions"].update_one(
                                    {"_id": session_id, "user_id": user_id, "title": "未命名会话"},
                                    {"$set": {"title": auto_title}},
                                )
                                try:
                                    oid = ObjectId(session_id)
                                    await database["sessions"].update_one(
                                        {"_id": oid, "user_id": user_id, "title": "未命名会话"},
                                        {"$set": {"title": auto_title}},
                                    )
                                except Exception:
                                    pass
                    # assistant 回复：若客户端已断开（如前端切换会话触发取消），不落库、不计数
                    try:
                        disconnected = await request.is_disconnected()
                    except Exception:
                        disconnected = False
                    if not disconnected:
                        await database["messages"].insert_one({
                            "user_id": user_id,
                            "session_id": session_id,
                            "role": "assistant",
                            "content": full_output,
                            "created_at": now,
                        })
                        if session_id:
                            # 同步 updated_at（assistant 回复后）
                            try:
                                oid = ObjectId(session_id)
                                await database["sessions"].update_one(
                                    {"_id": oid, "user_id": user_id},
                                    {"$set": {"updated_at": now}, "$inc": {"message_count": 1}},
                                )
                            except Exception:
                                await database["sessions"].update_one(
                                    {"_id": session_id, "user_id": user_id},
                                    {"$set": {"updated_at": now}, "$inc": {"message_count": 1}},
                                )
            except Exception as werr:
                logger.warning(f"write messages with session failed: {werr}")

            # 诊断：写入后统计一次用户消息数
            try:
                database = db()
                if database is not None:
                    cnt = await database["messages"].count_documents({"user_id": user_id, "role": "user"})
                    logger.info(f"[persist] user={user_id} user_msg_count_after_write={cnt}")
            except Exception as _e:
                logger.warning(f"post-write count failed: {_e}")

            await _maybe_schedule_memory(user_id)

            # 返回生成的回答
            return JSONResponse(content={"message": full_output})
        else:
            # **流式模式：**
            collected_response = []  # 用于收集完整的AI回复
            
            async def token_stream():
                nonlocal updated_messages
                # 调流式之前也做一次 turn 上限裁剪
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

                        yield f"data: {content}\n\n"

                    except Exception as e:
                        logger.warning(f"❌ 流式 chunk 解析失败: {e}")
                
                # 流式结束后，将完整的AI回复添加到上下文（恢复持久化）
                if collected_response:
                    full_response = "".join(collected_response)
                    # 确保已建立 DB 连接
                    try:
                        await connect()
                    except Exception as _e:
                        logger.warning(f"db connect before write(stream) failed: {_e}")
                    tasks = []
                    if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
                        t_user = context_manager.add_user_message(messages[-1].get("content", ""), user_id)
                        if t_user:
                            tasks.append(t_user)
                        else:
                            logger.warning("add_user_message returned None (stream)")
                    t_assistant = context_manager.add_assistant_response(full_response, user_id)
                    if t_assistant:
                        tasks.append(t_assistant)
                    else:
                        logger.warning("add_assistant_response returned None (stream)")
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                    # 额外：messages 集合写入（带 session_id）
                    try:
                        database = db()
                        if database is not None:
                            from datetime import datetime, timezone
                            now = datetime.now(timezone.utc)
                            if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
                                await database["messages"].insert_one({
                                    "user_id": user_id,
                                    "session_id": session_id,
                                    "role": "user",
                                    "content": messages[-1].get("content", ""),
                                    "created_at": now,
                                })
                                if session_id:
                                    content_preview = messages[-1].get("content", "")
                                    try:
                                        oid = ObjectId(session_id)
                                        await database["sessions"].update_one(
                                            {"_id": oid, "user_id": user_id},
                                            {"$set": {"updated_at": now, "last_message_preview": content_preview[:60]},
                                             "$inc": {"message_count": 1}},
                                        )
                                    except Exception:
                                        await database["sessions"].update_one(
                                            {"_id": session_id, "user_id": user_id},
                                            {"$set": {"updated_at": now, "last_message_preview": content_preview[:60]},
                                             "$inc": {"message_count": 1}},
                                        )
                                    auto_title = content_preview.strip().replace("\n", " ")[:20]
                                    if auto_title:
                                        await database["sessions"].update_one(
                                            {"_id": session_id, "user_id": user_id, "title": "未命名会话"},
                                            {"$set": {"title": auto_title}},
                                        )
                                        try:
                                            oid = ObjectId(session_id)
                                            await database["sessions"].update_one(
                                                {"_id": oid, "user_id": user_id, "title": "未命名会话"},
                                                {"$set": {"title": auto_title}},
                                            )
                                        except Exception:
                                            pass
                            # 若客户端已断开，跳过 assistant 落库与会话计数
                            try:
                                disconnected = await request.is_disconnected()
                            except Exception:
                                disconnected = False
                            if not disconnected:
                                await database["messages"].insert_one({
                                    "user_id": user_id,
                                    "session_id": session_id,
                                    "role": "assistant",
                                    "content": full_response,
                                    "created_at": now,
                                })
                                if session_id:
                                    try:
                                        oid = ObjectId(session_id)
                                        await database["sessions"].update_one(
                                            {"_id": oid, "user_id": user_id},
                                            {"$set": {"updated_at": now}, "$inc": {"message_count": 1}},
                                        )
                                    except Exception:
                                        await database["sessions"].update_one(
                                            {"_id": session_id, "user_id": user_id},
                                            {"$set": {"updated_at": now}, "$inc": {"message_count": 1}},
                                        )
                    except Exception as werr:
                        logger.warning(f"write messages with session(stream) failed: {werr}")
                    # 诊断：写入后统计一次用户消息数
                    try:
                        database = db()
                        if database is not None:
                            cnt = await database["messages"].count_documents({"user_id": user_id, "role": "user"})
                            logger.info(f"[persist] user={user_id} user_msg_count_after_write(stream)={cnt}")
                    except Exception as _e:
                        logger.warning(f"post-write count(stream) failed: {_e}")
                    await _maybe_schedule_memory(user_id)

            return StreamingResponse(token_stream(), media_type="text/event-stream", headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 某些代理会缓冲
            })
    except Exception as e:
        logger.error(f"🔴 错误: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

# ---- 诊断端点：查看上下文与环境开关 ----
@app.get("/debug/context", tags=["infra"])
async def debug_context(request: Request):
    try:
        from core.context_manager import PURE_CONTEXT  # type: ignore
        from core.context_manager_mongo import DB_WRITE_INLINE as DBWI  # type: ignore
    except Exception:
        PURE_CONTEXT = None
        DBWI = None
    return {
        "manager": type(context_manager).__name__,
        "PURE_CONTEXT": PURE_CONTEXT,
        "DB_WRITE_INLINE": DBWI,
        "MEMORY_RUN_INLINE": MEMORY_RUN_INLINE,
    }

# ------------------ 历史消息读取（最小API） ------------------
@app.get("/v1/messages", tags=["history"])
async def get_messages(request: Request, limit: int = 100):
    """
    返回当前用户最近的消息（按时间正序，便于直接渲染）。
    - X-User-Id 或 JWT sub 用作 user_id
    - limit: 最大条数（默认100）
    """
    try:
        auth_header = request.headers.get("Authorization")
        user_id = request.headers.get("X-User-Id", "default_user")
        if auth_header and auth_header.startswith("Bearer "):
            data = decode_jwt(auth_header.split(" ",1)[1])
            if data and data.get("sub"):
                user_id = data["sub"]

        await connect()
        database = db()
        if database is None:
            return JSONResponse(content={"messages": []})

        cursor = database["messages"].find({"user_id": user_id}).sort("created_at", 1).limit(int(limit))
        docs = []
        async for d in cursor:
            docs.append({
                "role": d.get("role"),
                "content": d.get("content"),
                "created_at": d.get("created_at")
            })
        return {"messages": docs}
    except Exception as e:
        logger.error(f"history error: {e}")
        return JSONResponse(content={"messages": [], "error": str(e)}, status_code=500)

@app.patch("/v1/sessions/{sid}", tags=["sessions"])
async def rename_session(request: Request, sid: str, payload: dict = Body(default={})):  # {title}
    try:
        auth_header = request.headers.get("Authorization")
        user_id = request.headers.get("X-User-Id", "default_user")
        if auth_header and auth_header.startswith("Bearer "):
            data = decode_jwt(auth_header.split(" ",1)[1])
            if data and data.get("sub"):
                user_id = data["sub"]
        title = (payload.get("title") or "未命名会话").strip() or "未命名会话"
        await connect()
        database = db()
        if database is None:
            return JSONResponse(content={"error": "db not connected"}, status_code=500)
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        # 尝试字符串 _id
        r1 = await database["sessions"].update_one({"_id": sid, "user_id": user_id}, {"$set": {"title": title, "updated_at": now}})
        # 尝试 ObjectId _id
        try:
            oid = ObjectId(sid)
            r2 = await database["sessions"].update_one({"_id": oid, "user_id": user_id}, {"$set": {"title": title, "updated_at": now}})
        except Exception:
            r2 = None
        if (r1 and r1.matched_count) or (r2 and r2.matched_count):
            return {"ok": True}
        return JSONResponse(content={"error": "not found"}, status_code=404)
    except Exception as e:
        logger.error(f"rename_session error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.delete("/v1/sessions/{sid}", tags=["sessions"])
async def delete_session(request: Request, sid: str):
    try:
        auth_header = request.headers.get("Authorization")
        user_id = request.headers.get("X-User-Id", "default_user")
        if auth_header and auth_header.startswith("Bearer "):
            data = decode_jwt(auth_header.split(" ",1)[1])
            if data and data.get("sub"):
                user_id = data["sub"]
        await connect()
        database = db()
        if database is None:
            return JSONResponse(content={"error": "db not connected"}, status_code=500)
        # 删除会话文档（尝试字符串与 ObjectId 两种）
        await database["sessions"].delete_one({"_id": sid, "user_id": user_id})
        try:
            oid = ObjectId(sid)
            await database["sessions"].delete_one({"_id": oid, "user_id": user_id})
        except Exception:
            pass
        # 删除该会话的消息
        await database["messages"].delete_many({"user_id": user_id, "session_id": sid})
        return {"ok": True}
    except Exception as e:
        logger.error(f"delete_session error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

# ------------------ 会话管理 ------------------

@app.get("/v1/sessions", tags=["sessions"])
async def list_sessions(request: Request):
    try:
        auth_header = request.headers.get("Authorization")
        user_id = request.headers.get("X-User-Id", "default_user")
        if auth_header and auth_header.startswith("Bearer "):
            data = decode_jwt(auth_header.split(" ",1)[1])
            if data and data.get("sub"):
                user_id = data["sub"]

        await connect()
        database = db()
        if database is None:
            return {"sessions": []}
        cursor = database["sessions"].find({"user_id": user_id}).sort("updated_at", -1)
        res = []
        async for s in cursor:
            res.append({
                "id": str(s.get("_id")),
                "title": s.get("title", "未命名会话"),
                "updated_at": s.get("updated_at"),
                "message_count": s.get("message_count", 0),
                "last_message_preview": s.get("last_message_preview", ""),
            })
        return {"sessions": res}
    except Exception as e:
        logger.error(f"list_sessions error: {e}")
        return JSONResponse(content={"sessions": [], "error": str(e)}, status_code=500)

@app.post("/v1/sessions", tags=["sessions"])
async def create_session(request: Request, payload: dict = Body(default={})):  # {title?}
    try:
        auth_header = request.headers.get("Authorization")
        user_id = request.headers.get("X-User-Id", "default_user")
        if auth_header and auth_header.startswith("Bearer "):
            data = decode_jwt(auth_header.split(" ",1)[1])
            if data and data.get("sub"):
                user_id = data["sub"]
        title = (payload.get("title") or "未命名会话").strip() or "未命名会话"
        await connect()
        database = db()
        if database is None:
            return JSONResponse(content={"error": "db not connected"}, status_code=500)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
            "last_message_preview": "",
        }
        res = await database["sessions"].insert_one(doc)
        return {"id": str(res.inserted_id)}
    except Exception as e:
        logger.error(f"create_session error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/v1/sessions/{sid}/messages", tags=["sessions"])
async def get_session_messages(request: Request, sid: str, limit: int = 100):
    try:
        auth_header = request.headers.get("Authorization")
        user_id = request.headers.get("X-User-Id", "default_user")
        if auth_header and auth_header.startswith("Bearer "):
            data = decode_jwt(auth_header.split(" ",1)[1])
            if data and data.get("sub"):
                user_id = data["sub"]
        await connect()
        database = db()
        if database is None:
            return {"messages": []}
        cursor = database["messages"].find({"user_id": user_id, "session_id": sid}).sort("created_at", 1).limit(int(limit))
        docs = []
        async for d in cursor:
            docs.append({
                "role": d.get("role"),
                "content": d.get("content"),
                "created_at": d.get("created_at")
            })
        return {"messages": docs}
    except Exception as e:
        logger.error(f"get_session_messages error: {e}")
        return JSONResponse(content={"messages": [], "error": str(e)}, status_code=500)
