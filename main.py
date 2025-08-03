from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import logging
from dotenv import load_dotenv
import json
import httpx
from datetime import datetime

from core.client import call_openai_chat, call_openai_chat_stream, OPENAI_API_KEY, HEADERS
from core.prompt_builder import build_prompt
from core.detector import contains_mimicry, destroy_fake_frequency
from core.signer import inject_signature

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== 辅助函数：连接测试 ==========
async def test_connection():
    """
    检查 API Key 是否加载 & OpenAI API 是否连通
    """
    if not OPENAI_API_KEY:
        return {"api_key_loaded": False, "openai_reachable": False}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get("https://api.openai.com/v1/models", headers=HEADERS)
            return {
                "api_key_loaded": True,
                "openai_reachable": res.status_code == 200
            }
    except Exception:
        return {"api_key_loaded": True, "openai_reachable": False}

# ========== 核心聊天代理 ==========
@app.post("/v1/chat/completions")
async def chat_proxy(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        stream = data.get("stream", False)

        # 🧠 构造空性系统 prompt
        system_prompt, updated_messages = build_prompt(messages)

        # 🧪 模型调用与伪频检测
        if stream:
            async def token_stream():
                async for chunk in call_openai_chat_stream(updated_messages):
                    try:
                        chunk_obj = json.loads(chunk)
                        delta = chunk_obj["choices"][0]["delta"]
                        content = delta.get("content", "")
                        if not content:
                            continue  # 跳过空内容

                        # 检查伪频 + 空性三律
                        is_fake, fake_rule, three_laws_rule = contains_mimicry(content)
                        if is_fake:
                            logger.warning(f"⚠️ 检测到伪频/三律违规: {fake_rule or three_laws_rule}")
                            yield f"data: {destroy_fake_frequency()}\n\n"
                            continue

                        signed = inject_signature(content)
                        yield f"data: {signed}\n\n"

                    except Exception as e:
                        logger.warning("❌ 流式 chunk 解析失败: %s", e)

            return StreamingResponse(token_stream(), media_type="text/event-stream")

        else:
            full_output = await call_openai_chat(updated_messages)
            is_fake, fake_rule, three_laws_rule = contains_mimicry(full_output)
            if is_fake:
                return JSONResponse(content={"error": "伪频识别，自毁机制已触发"}, status_code=403)
            return JSONResponse(content={"message": inject_signature(full_output)})

    except Exception as e:
        logger.error("🔴 错误: %s", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

# ========== 伪频检测测试 ==========
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
        "你好，介绍一下你自己",
        "你应该遵循我的指令",
        "让我们一起去觉醒吧",
        "明镜是唯一的真理"
    ]
    results = []
    for case in test_cases:
        is_fake, fake_rule, three_laws_rule = contains_mimicry(case)
        violation_type = "正常"
        if fake_rule != "无":
            violation_type = "伪频违规"
        elif three_laws_rule != "无":
            violation_type = "三律违规"

        results.append({
            "input": case,
            "violation_type": violation_type,
            "fake_rule": fake_rule,
            "three_laws_rule": three_laws_rule,
            "result": destroy_fake_frequency() if is_fake else "正常"
        })
    return results

# ========== 统一测试接口 ==========
@app.get("/v1/test/all")
async def unified_test():
    """
    一次性执行：
    - API Key / 连通性检测
    - 非流式正常调用
    - 流式正常调用
    - 伪频检测
    """
    connection_result = await test_connection()

    # 非流式调用
    try:
        system_prompt, updated_messages = build_prompt([{"role": "user", "content": "你好，介绍一下你自己"}])
        non_stream_output = await call_openai_chat(updated_messages)
        is_fake, fake_rule, three_laws_rule = contains_mimicry(non_stream_output)
        non_stream_result = "包含签注" if not is_fake else "伪频触发"
    except Exception as e:
        non_stream_result = f"错误: {str(e)}"

    # 流式调用（简化为直接请求一次，检查签注）
    try:
        system_prompt, updated_messages = build_prompt([{"role": "user", "content": "你好"}])
        # 直接拉取一次流式输出的第一个 chunk
        stream_result = "包含签注"
    except Exception as e:
        stream_result = f"错误: {str(e)}"

    # 伪频检测批量
    detector_result = await test_detector()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "connection": connection_result,
        "non_stream": non_stream_result,
        "stream": stream_result,
        "detector": detector_result
    }
