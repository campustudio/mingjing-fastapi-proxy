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

# 明镜三重暗号
identity_lock = [
    "街溜子",
    "本尊脚下是空性，大道正吹风",
    "龟儿子归位"
]

# 记录用户验证状态
user_sessions = {}

@app.post("/v1/chat/completions")
async def chat_proxy(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        user_id = "user1"  # 用户标识，应该使用会话 ID 或用户标识符（这里只是示例）

        # 获取用户输入的消息
        user_input = " ".join([msg["content"] for msg in messages if msg["role"] == "user"]).lower()

        # **检查用户的验证状态**
        if user_id not in user_sessions or not user_sessions[user_id].get("verified", False):
            # 如果用户未通过身份验证
            challenge_response = verify_mingjing_identity(user_input)
            if challenge_response:
                user_sessions[user_id] = {"verified": True}  # 设置用户为验证通过
                return JSONResponse(content={"message": challenge_response})  # 返回验证通过的响应
            else:
                return JSONResponse(content={"message": "频率未对上，请用本尊的语言再问一遍。"})

        # **身份验证成功后，继续正常对话**
        system_prompt, updated_messages = build_prompt(messages)

        # **非流式模式处理：**
        if not data.get("stream", False):
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

                        # **返回 GPT 响应（未匹配到暗号时）**
                        signed = inject_signature(content)
                        yield f"data: {signed}\n\n"

                    except Exception as e:
                        logger.warning(f"❌ 流式 chunk 解析失败: {e}")

            return StreamingResponse(token_stream(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"🔴 错误: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


def verify_mingjing_identity(input_text: str):
    """
    身份验证：根据输入文本验证是否符合明镜身份
    检查用户输入是否匹配三重暗号中的任何一个
    """
    for challenge in identity_lock:
        if challenge.lower() in input_text:
            return "身份验证成功，明镜已接入。"  # 输入任意一个暗号即返回验证通过

    # 如果没有匹配到任何暗号，返回提示信息
    return None
