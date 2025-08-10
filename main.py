# main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import logging
from dotenv import load_dotenv
import json

from core.client import call_openai_chat, call_openai_chat_stream
from core.prompt_builder import build_prompt
from core.signer import inject_signature
from core.context_manager import context_manager

load_dotenv()

app = FastAPI()

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
        user_id = "default_user"
        
        # 使用上下文管理器构建包含历史上下文的完整消息列表
        messages_with_context = context_manager.build_context_messages(messages, user_id)
        
        # 注入系统 prompt
        system_prompt, updated_messages = build_prompt(messages_with_context)

        # **非流式模式处理：**
        if not stream:
            # 调用 OpenAI 获取响应，传入上下文
            full_output = await call_openai_chat(updated_messages)
            
            # 将AI回复添加到上下文中
            context_manager.add_assistant_response(full_output, user_id)

            # 返回生成的回答
            return JSONResponse(content={"message": full_output})

        else:
            # **流式模式：**
            collected_response = []  # 用于收集完整的AI回复
            
            async def token_stream():
                async for chunk in call_openai_chat_stream(updated_messages):
                    try:
                        chunk_obj = json.loads(chunk)
                        delta = chunk_obj["choices"][0]["delta"]
                        content = delta.get("content", "")
                        if not content:
                            continue
                        
                        # 收集完整回复用于上下文管理
                        collected_response.append(content)

                        # 返回 GPT 响应，并注入签名
                        signed = inject_signature(content)
                        yield f"data: {signed}\n\n"

                    except Exception as e:
                        logger.warning(f"❌ 流式 chunk 解析失败: {e}")
                
                # 流式结束后，将完整的AI回复添加到上下文
                if collected_response:
                    full_response = "".join(collected_response)
                    context_manager.add_assistant_response(full_response, user_id)

            return StreamingResponse(token_stream(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"🔴 错误: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
