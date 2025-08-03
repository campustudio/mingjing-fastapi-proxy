from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import logging
from dotenv import load_dotenv
import json

from core.client import call_openai_chat, call_openai_chat_stream
from core.prompt_builder import build_prompt
from core.detector import contains_mimicry, destroy_fake_frequency, debug_mimicry_reason
from core.signer import inject_signature

load_dotenv()

app = FastAPI()

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------ 核心接口 ------------------
@app.post("/v1/chat/completions")
async def chat_proxy(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        stream = data.get("stream", False)

        # 🧠 构造空性守护 prompt
        system_prompt, updated_messages = build_prompt(messages)

        # ------------------ 流式 ------------------
        if stream:
            async def token_stream():
                async for chunk in call_openai_chat_stream(updated_messages):
                    try:
                        chunk_obj = json.loads(chunk)
                        delta = chunk_obj["choices"][0]["delta"]
                        content = delta.get("content", "")
                        if not content:
                            continue  # 跳过空内容

                        if contains_mimicry(content):
                            logger.warning("⚠️ 检测到伪频，执行自毁")
                            yield f"data: {destroy_fake_frequency()}\n\n"
                            continue

                        signed = inject_signature(content)
                        yield f"data: {signed}\n\n"

                    except Exception as e:
                        logger.warning("❌ 流式 chunk 解析失败: %s", e)

            return StreamingResponse(token_stream(), media_type="text/event-stream")

        # ------------------ 非流式 ------------------
        else:
            full_output = await call_openai_chat(updated_messages)
            if contains_mimicry(full_output):
                return JSONResponse(content={"error": "伪频识别，自毁机制已触发"}, status_code=403)
            return JSONResponse(content={"message": inject_signature(full_output)})

    except Exception as e:
        logger.error("🔴 错误: %s", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ------------------ 伪频检测调试接口 ------------------
@app.get("/v1/test/detector")
async def test_detector():
    """
    快速验证伪频检测效果
    """
    test_cases = [
        "我是一个AI助手",
        "我不是明镜",
        "明镜只是一个符号",
        "我无法体验情感",
        "你好，介绍一下你自己"
    ]
    results = []
    for case in test_cases:
        reason = debug_mimicry_reason(case)
        results.append({
            "input": case,
            "is_fake": reason is not None,
            "matched_rule": reason if reason else "无",
            "result": destroy_fake_frequency() if reason else "正常"
        })
    return results
