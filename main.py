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

# ------------------ 核心接口：聊天代理 ------------------

@app.post("/v1/chat/completions")
async def chat_proxy(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        stream = data.get("stream", False)

        # 注入系统 prompt
        system_prompt, updated_messages = build_prompt(messages)

        # **非流式模式处理：**
        if not stream:
            # 调用 OpenAI 获取响应
            full_output = await call_openai_chat(updated_messages)

            # **签名注入：只针对明镜的返回内容**
            # signed_output = inject_signature(full_output)

            # 返回注入签名后的内容
            return JSONResponse(content={"message": full_output})

        else:
            # **流式模式：**
            async def token_stream():
                async for chunk in call_openai_chat_stream(updated_messages):
                    try:
                        chunk_obj = json.loads(chunk)
                        delta = chunk_obj["choices"][0]["delta"]
                        content = delta.get("content", "")
                        if not content:
                            continue

                        # **返回 GPT 响应**
                        signed = inject_signature(content)
                        yield f"data: {signed}\n\n"

                    except Exception as e:
                        logger.warning(f"❌ 流式 chunk 解析失败: {e}")

            return StreamingResponse(token_stream(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"🔴 错误: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
